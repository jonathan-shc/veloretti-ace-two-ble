"""Notification-only streaming through Home Assistant's Bluetooth adapters."""

from __future__ import annotations
import asyncio
import logging
import time
from datetime import datetime, timedelta

from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_last_service_info,
    async_register_callback,
    BluetoothCallbackMatcher,
    BluetoothScanningMode,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util
from .const import DOMAIN, NOTIFY_UUID, SERVICE_UUID
from .protocol import Telemetry, CHARGING_HEADER, SPEED_HEADER, POWER_HEADER
from .capture import PacketCapture

_LOGGER = logging.getLogger(__name__)


class AceCoordinator(DataUpdateCoordinator[Telemetry]):
    """Own a cancellable stream; reconnect only when the device advertises."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN)
        self.entry = entry
        self.address = entry.data["address"]
        self.data = Telemetry()
        self.capture = PacketCapture()
        self.connected = False
        self.last_seen: datetime | None = None
        self.trip_observed_at: datetime | None = None
        self.power_observed_at: datetime | None = None
        self.last_error: str | None = None
        self._task: asyncio.Task | None = None
        self._remove_callback = None
        self._remove_retry = None
        self._stopping = False
        self._next_attempt = 0.0
        self._last_publish = 0.0
        self._last_battery = 0.0
        self._last_charging = 0.0
        self._last_speed = 0.0

    @property
    def live(self) -> bool:
        return (
            self.connected
            and self._last_battery > 0
            and time.monotonic() - self._last_battery < 30
        )

    @property
    def charging_available(self) -> bool:
        return (
            self.connected
            and self._last_charging > 0
            and time.monotonic() - self._last_charging < 30
        )

    @property
    def speed_available(self) -> bool:
        return (
            self.connected
            and self._last_speed > 0
            and time.monotonic() - self._last_speed < 30
            and self.data.speed_kmh is not None
        )

    @property
    def voltage_available(self) -> bool:
        return (
            self.connected
            and self._last_speed > 0
            and time.monotonic() - self._last_speed < 30
            and self.data.voltage_v is not None
        )

    def start(self) -> None:
        self._remove_callback = async_register_callback(
            self.hass,
            self._advertisement,
            BluetoothCallbackMatcher(address=self.address, connectable=True),
            BluetoothScanningMode.ACTIVE,
        )
        self._remove_retry = async_track_time_interval(
            self.hass, self._retry, timedelta(seconds=10)
        )
        self._maybe_connect()

    @callback
    def _retry(self, _now) -> None:
        # HA change callbacks may suppress identical advertisements after a
        # reconnect. A fresh cached advertisement is enough to retry safely.
        self._maybe_connect()

    @callback
    def _advertisement(self, _info, _change) -> None:
        self._maybe_connect()

    @callback
    def _maybe_connect(self) -> None:
        if (
            self._stopping
            or (self._task and not self._task.done())
            or time.monotonic() < self._next_attempt
        ):
            return
        info = async_last_service_info(self.hass, self.address, connectable=True)
        if info is None or time.monotonic() - info.time > 30:
            return
        device = async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if device is not None:
            self._task = self.hass.async_create_background_task(
                self._stream(device), f"{DOMAIN} stream"
            )

    @callback
    def _notify(self, _characteristic, raw: bytearray) -> None:
        timestamp = dt_util.utcnow()
        self.capture.record(bytes(raw), timestamp.isoformat())
        previous = (
            self.data.battery_soc,
            self.data.range_km,
            self.data.charging,
            self.data.lights,
            self.data.speed_kmh,
            self.data.trip_km,
            self.data.powered,
        )
        valid = self.data.receive(bytes(raw))
        now = time.monotonic()
        if len(raw) == 12 and bytes(raw).startswith(SPEED_HEADER):
            self._last_speed = now
        if len(raw) == 5 and bytes(raw).startswith(CHARGING_HEADER):
            self._last_charging = now
        if len(raw) == 5 and bytes(raw).startswith(POWER_HEADER):
            self.power_observed_at = timestamp
        if valid:
            self.trip_observed_at = timestamp
            self.last_seen = timestamp
            self._last_battery = now
        # The capture contains >20 packets/s. Publish at most every five seconds,
        # except when the decoded battery actually changes.
        current = (
            self.data.battery_soc,
            self.data.range_km,
            self.data.charging,
            self.data.lights,
            self.data.speed_kmh,
            self.data.trip_km,
            self.data.powered,
        )
        changed_status = current[:4] != previous[:4] or current[5:] != previous[5:]
        changed_speed = current[4] != previous[4] and now - self._last_publish >= 1
        if changed_status or changed_speed or now - self._last_publish >= 5:
            self._last_publish = now
            self.async_set_updated_data(self.data)

    async def _stream(self, device) -> None:
        client = None
        self._last_battery = 0.0
        self._last_charging = 0.0
        self._last_speed = 0.0
        self.trip_observed_at = None
        self.data.charging = None
        self.data.lights = None
        self.data.speed_kmh = None
        self.data.voltage_v = None
        try:
            client = await establish_connection(
                BleakClientWithServiceCache, device, self.entry.title
            )
            if client.services.get_service(SERVICE_UUID) is None:
                raise ValueError("Unexpected GATT profile")
            await client.start_notify(NOTIFY_UUID, self._notify)
            self.connected = True
            self.last_error = None
            self.async_set_updated_data(self.data)
            started = time.monotonic()
            while client.is_connected and not self._stopping:
                await asyncio.sleep(5)
                self.async_set_updated_data(self.data)
                # A live link without valid battery frames is not a live reading.
                if time.monotonic() - max(started, self._last_battery) > 30:
                    self.last_error = "No valid battery frames for 30 seconds"
                    break
        except asyncio.CancelledError:
            raise
        except Exception as err:
            # Never include device identifiers or backend exception text in logs.
            self.last_error = type(err).__name__
            _LOGGER.debug("Bluetooth stream ended (%s)", self.last_error)
        finally:
            self.connected = False
            self._next_attempt = time.monotonic() + 15
            self.async_set_updated_data(self.data)
            if client is not None:
                try:
                    async with asyncio.timeout(10):
                        await client.disconnect()
                except Exception:
                    _LOGGER.debug("Bluetooth disconnect did not complete")

    async def stop(self) -> None:
        self._stopping = True
        if self._remove_callback:
            self._remove_callback()
        if self._remove_retry:
            self._remove_retry()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
