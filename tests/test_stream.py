"""Check notification-only behavior and cleanup without Bluetooth hardware."""

import asyncio
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).parents[1] / "custom_components/veloretti_ace_ble"


class CoordinatorBase:
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, hass, logger, name):
        self.hass = hass

    def async_set_updated_data(self, data):
        self.data = data


class StreamTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        modules = {}

        def fake(name, **attrs):
            m = ModuleType(name)
            m.__dict__.update(attrs)
            modules[name] = m

        fake("ace_test", __path__=[str(ROOT)])
        fake(
            "bleak_retry_connector",
            BleakClientWithServiceCache=object,
            establish_connection=AsyncMock(),
        )
        fake("homeassistant")
        fake("homeassistant.components")
        fake(
            "homeassistant.components.bluetooth",
            async_ble_device_from_address=Mock(),
            async_last_service_info=Mock(),
            async_register_callback=Mock(),
            BluetoothCallbackMatcher=dict,
            BluetoothScanningMode=SimpleNamespace(ACTIVE="active"),
        )
        fake("homeassistant.core", HomeAssistant=object, callback=lambda f: f)
        fake("homeassistant.helpers")
        fake("homeassistant.helpers.event", async_track_time_interval=Mock())
        fake(
            "homeassistant.helpers.update_coordinator",
            DataUpdateCoordinator=CoordinatorBase,
        )
        fake("homeassistant.util", dt=SimpleNamespace(utcnow=lambda: datetime.now(timezone.utc)))
        self.patch = patch.dict(sys.modules, modules)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        for name in ("const", "protocol", "capture", "coordinator"):
            spec = importlib.util.spec_from_file_location(
                "ace_test." + name, ROOT / (name + ".py")
            )
            m = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = m
            self.addCleanup(sys.modules.pop, spec.name, None)
            spec.loader.exec_module(m)
        self.module = sys.modules["ace_test.coordinator"]
        self.c = self.module.AceCoordinator(
            SimpleNamespace(), SimpleNamespace(data={"address": "test"}, title="test")
        )

    async def test_subscribe_without_command_writes(self):
        client = SimpleNamespace(
            services=SimpleNamespace(get_service=lambda _: object()),
            start_notify=AsyncMock(),
            disconnect=AsyncMock(),
            write_gatt_char=AsyncMock(),
            is_connected=False,
        )
        self.module.establish_connection.return_value = client
        await self.c._stream(object())
        client.start_notify.assert_awaited_once()
        client.write_gatt_char.assert_not_awaited()
        client.disconnect.assert_awaited_once()
        self.assertFalse(self.c.connected)

    async def test_wrong_profile_is_disconnected_without_subscribing(self):
        client = SimpleNamespace(
            services=SimpleNamespace(get_service=lambda _: None),
            start_notify=AsyncMock(),
            disconnect=AsyncMock(),
        )
        self.module.establish_connection.return_value = client
        await self.c._stream(object())
        client.start_notify.assert_not_awaited()
        client.disconnect.assert_awaited_once()
        self.assertEqual(self.c.last_error, "ValueError")

    async def test_trip_timestamp_only_advances_for_valid_trip_packet(self):
        self.assertIsNone(self.c.trip_observed_at)
        self.c._notify(None, bytearray.fromhex("02 F8 32 00 5B 40 00 00 2A 04 D4 17"))
        observed = self.c.trip_observed_at
        self.assertIsNotNone(observed)
        self.assertEqual(self.c.data.trip_km, 0.64)
        self.c._notify(None, bytearray.fromhex("04 FF 14 00 00"))
        self.assertEqual(self.c.trip_observed_at, observed)
        self.c._notify(None, bytearray.fromhex("02 F8 32 00 FF 40 00 00 2A 04 D4 17"))
        self.assertEqual(self.c.trip_observed_at, observed)

    async def test_unknown_packet_does_not_mark_battery_live(self):
        self.c.connected = True
        self.c._notify(None, bytearray.fromhex("04 FF 14 00 00"))
        self.assertFalse(self.c.live)
        self.assertIsNone(self.c.last_seen)
        self.c._notify(None, bytearray.fromhex("02 F8 32 00 5B 00 00 00 2A 04 D4 17"))
        self.assertTrue(self.c.live)

    async def test_stop_cancels_and_disconnects_active_stream(self):
        subscribed = asyncio.Event()

        async def notify(*_):
            subscribed.set()

        client = SimpleNamespace(
            services=SimpleNamespace(get_service=lambda _: object()),
            start_notify=notify,
            disconnect=AsyncMock(),
            is_connected=True,
        )
        self.module.establish_connection.return_value = client
        self.c._remove_callback = Mock()
        self.c._task = asyncio.create_task(self.c._stream(object()))
        await subscribed.wait()
        await self.c.stop()
        self.c._remove_callback.assert_called_once()
        client.disconnect.assert_awaited_once()
        self.assertFalse(self.c.connected)

    async def test_retry_uses_fresh_unchanged_advertisement(self):
        self.module.async_last_service_info.return_value = SimpleNamespace(
            time=self.module.time.monotonic()
        )
        self.module.async_ble_device_from_address.return_value = object()
        self.c.hass.async_create_background_task = Mock(
            side_effect=lambda coro, name: asyncio.create_task(coro)
        )
        self.c._stream = AsyncMock()
        self.c._retry(None)
        await self.c._task
        self.c._stream.assert_awaited_once()

    async def test_retry_skips_stale_advertisements_and_stopped_entry(self):
        self.module.async_last_service_info.return_value = SimpleNamespace(
            time=self.module.time.monotonic() - 60
        )
        self.c._retry(None)
        self.assertIsNone(self.c._task)
        self.c._stopping = True
        self.module.async_last_service_info.return_value = SimpleNamespace(
            time=self.module.time.monotonic()
        )
        self.c._retry(None)
        self.assertIsNone(self.c._task)

    async def test_retry_does_not_duplicate_running_stream(self):
        self.module.async_last_service_info.return_value = SimpleNamespace(
            time=self.module.time.monotonic()
        )
        self.c.hass.async_create_background_task = Mock(
            side_effect=lambda coro, name: asyncio.create_task(coro)
        )
        self.c._stream = AsyncMock()
        self.c._retry(None)
        task = self.c._task
        self.c._retry(None)
        self.assertIs(self.c._task, task)
        await task
        self.c._stream.assert_awaited_once()

    async def test_charging_freshness_is_independent_of_battery(self):
        self.c.connected = True
        self.c._notify(None, bytearray.fromhex("04 f8 34 02 06"))
        self.assertTrue(self.c.charging_available)
        self.assertTrue(self.c.data.charging)
        self.assertFalse(self.c.live)
        self.c._last_charging = self.module.time.monotonic() - 40
        self.c._notify(None, bytearray.fromhex("02 f8 32 00 5D 00 00 00 2A 04 A4 1F"))
        self.assertTrue(self.c.live)
        self.assertFalse(self.c.charging_available)

    async def test_reconnect_clears_event_derived_light_status(self):
        self.c.data.lights = True
        self.c.data.charging = True
        client = SimpleNamespace(
            services=SimpleNamespace(get_service=lambda _: object()),
            start_notify=AsyncMock(),
            disconnect=AsyncMock(),
            is_connected=False,
        )
        self.module.establish_connection.return_value = client
        await self.c._stream(object())
        self.assertIsNone(self.c.data.lights)
        self.assertIsNone(self.c.data.charging)

    async def test_speed_freshness_does_not_use_battery_timestamp(self):
        self.c.connected = True
        self.c._notify(None, bytearray.fromhex("02 f8 32 01 14 03 00 00 dc 0f 3b ff"))
        self.assertTrue(self.c.speed_available)
        self.assertAlmostEqual(self.c.data.speed_kmh, 7.88)
        self.assertFalse(self.c.live)
        self.c._last_speed = self.module.time.monotonic() - 40
        self.c._notify(None, bytearray.fromhex("02 f8 32 00 5c 00 00 00 2a 04 dc 1e"))
        self.assertFalse(self.c.speed_available)

    async def test_speed_updates_are_throttled_to_one_second(self):
        self.c.async_set_updated_data = Mock()
        with patch.object(
            self.module.time, "monotonic", side_effect=[100, 100.1, 101.1]
        ):
            for value in ("11 03", "14 03", "94 02"):
                self.c._notify(
                    None,
                    bytearray.fromhex("02 f8 32 01 " + value + " 00 00 dc 0f 3b ff"),
                )
        self.assertEqual(self.c.async_set_updated_data.call_count, 2)
        self.assertAlmostEqual(self.c.data.speed_kmh, 6.6)

    async def test_voltage_requires_fresh_valid_frame_and_connection(self):
        self.c.connected = True
        self.c._notify(None, bytearray.fromhex("02 f8 32 01 00 00 00 00 d2 0f 3c ff"))
        self.assertTrue(self.c.voltage_available)
        self.assertAlmostEqual(self.c.data.voltage_v, 40.5)
        self.c._last_speed = self.module.time.monotonic() - 40
        self.c._notify(None, bytearray.fromhex("02 f8 32 00 59 40 00 00 2e 04 0c 17"))
        self.assertFalse(self.c.voltage_available)
        self.c._notify(None, bytearray.fromhex("02 f8 32 01 00 00 00 00 ff ff 3c ff"))
        self.assertFalse(self.c.voltage_available)
        self.c._notify(None, bytearray.fromhex("02 f8 32 01 00 00 00 00 d2 0f 3c ff"))
        self.c.connected = False
        self.assertFalse(self.c.voltage_available)

    async def test_reconnect_clears_voltage(self):
        self.c.data.voltage_v = 40.5
        client = SimpleNamespace(
            services=SimpleNamespace(get_service=lambda _: object()),
            start_notify=AsyncMock(), disconnect=AsyncMock(), is_connected=False,
        )
        self.module.establish_connection.return_value = client
        await self.c._stream(object())
        self.assertIsNone(self.c.data.voltage_v)
        self.assertFalse(self.c.voltage_available)

    async def test_shutdown_keeps_its_actual_observation_timestamp(self):
        self.c._notify(None, bytearray.fromhex("02 f8 32 04 01"))
        self.assertTrue(self.c.data.powered)
        self.assertIsNotNone(self.c.power_observed_at)
        self.c._notify(None, bytearray.fromhex("02 f8 32 04 00"))
        self.assertFalse(self.c.data.powered)
        observed = self.c.power_observed_at
        self.c.connected = False
        self.c._notify(None, bytearray.fromhex("00 00 02 50 00 07 00 9f 00 00 e0 00"))
        self.assertEqual(self.c.power_observed_at, observed)
