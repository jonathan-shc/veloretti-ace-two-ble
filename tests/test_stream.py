"""Check notification-only behavior and cleanup without Bluetooth hardware."""

import asyncio
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
            async_register_callback=Mock(),
            BluetoothCallbackMatcher=dict,
            BluetoothScanningMode=SimpleNamespace(ACTIVE="active"),
        )
        fake("homeassistant.core", HomeAssistant=object, callback=lambda f: f)
        fake("homeassistant.helpers")
        fake(
            "homeassistant.helpers.update_coordinator",
            DataUpdateCoordinator=CoordinatorBase,
        )
        fake("homeassistant.util", dt=SimpleNamespace(utcnow=lambda: "now"))
        self.patch = patch.dict(sys.modules, modules)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        for name in ("const", "protocol", "coordinator"):
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
