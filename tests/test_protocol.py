"""Check captured packet discrimination and corrupted data handling."""

import importlib.util
from pathlib import Path
import sys
import unittest

spec = importlib.util.spec_from_file_location(
    "ace_protocol",
    Path(__file__).parents[1] / "custom_components/veloretti_ace_ble/protocol.py",
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
Telemetry = module.Telemetry


class ProtocolTests(unittest.TestCase):
    def test_captured_battery(self):
        t = Telemetry()
        self.assertTrue(t.receive(bytes.fromhex("02 F8 32 00 5B 00 00 00 2A 04 D4 17")))
        self.assertEqual(t.battery_soc, 91)

    def test_other_captured_packets_do_not_overwrite_soc(self):
        t = Telemetry(battery_soc=91)
        for hex_data in (
            "04 FF 14 00 00",
            "00 00 02 50 00 07 00 9F 00 00 E0 00",
            "02 F8 32 04 01",
            "02 F8 32 01 00 00 00 00 F0 0F 39 FF",
        ):
            self.assertFalse(t.receive(bytes.fromhex(hex_data)))
            self.assertEqual(t.battery_soc, 91)

    def test_invalid_soc_length_and_header(self):
        frame = bytearray.fromhex("02 F8 32 00 5B 00 00 00 2A 04 D4 17")
        for index, value in ((4, 101), (0, 3)):
            p = frame.copy()
            p[index] = value
            self.assertFalse(Telemetry().receive(bytes(p)))
        for length in range(12):
            self.assertFalse(Telemetry().receive(bytes(frame[:length])))
        self.assertFalse(Telemetry().receive(bytes(frame) + b"x"))

    def test_zero_and_hundred(self):
        for soc in (0, 100):
            t = Telemetry()
            p = bytes.fromhex("02 F8 32 00") + bytes([soc, 0]) + bytes(6)
            self.assertTrue(t.receive(p))
            self.assertEqual(t.battery_soc, soc)

    def test_unknown_samples_bounded(self):
        t = Telemetry()
        for i in range(200):
            t.receive(bytes([i]) + bytes(90))
        self.assertEqual(len(t.raw), 64)
        self.assertTrue(all(len(bytes.fromhex(v)) <= 64 for v in t.raw.values()))


if __name__ == "__main__":
    unittest.main()


class BatteryStatusTests(unittest.TestCase):
    def test_changed_following_field_does_not_reject_soc(self):
        t = Telemetry()
        self.assertTrue(t.receive(bytes.fromhex("02 F8 32 00 5C 01 00 00 2A 04 D4 17")))
        self.assertEqual(t.battery_soc, 92)


class RangeAndChargingTests(unittest.TestCase):
    def test_display_confirmed_ranges(self):
        for tail, expected in (("78 37", 142), ("ac 26", 99), ("a4 1f", 81)):
            t = Telemetry()
            self.assertTrue(
                t.receive(bytes.fromhex("02 f8 32 00 5d 00 00 00 2a 04 " + tail))
            )
            self.assertEqual(t.range_km, expected)
            self.assertEqual(t.battery_soc, 93)

    def test_reversible_charging_status_preserves_battery_and_range(self):
        t = Telemetry(battery_soc=93, range_km=81)
        for status, expected in ((0, False), (6, True), (0, False)):
            self.assertFalse(t.receive(bytes.fromhex("04 f8 34 02") + bytes([status])))
            self.assertIs(t.charging, expected)
            self.assertEqual(t.battery_soc, 93)
            self.assertEqual(t.range_km, 81)

    def test_unknown_charging_codes_are_unknown(self):
        t = Telemetry(charging=True)
        t.receive(bytes.fromhex("04 f8 34 02 01"))
        self.assertIsNone(t.charging)


class LightTests(unittest.TestCase):
    def test_observed_light_cycle(self):
        for header in ("14 a8 00 41", "15 a2 00 41"):
            t = Telemetry(battery_soc=93, range_km=81)
            for code, expected in ((6, True), (7, False), (6, True)):
                self.assertFalse(t.receive(bytes.fromhex(header) + bytes([code])))
                self.assertIs(t.lights, expected)
                self.assertEqual(t.battery_soc, 93)
                self.assertEqual(t.range_km, 81)

    def test_other_event_codes_and_prefixes_do_not_set_lights(self):
        t = Telemetry()
        for packet in (
            "14 a8 00 41 04",
            "14 a8 00 42 06",
            "15 a2 00 41",
            "15 a2 00 41 06 00",
        ):
            t.receive(bytes.fromhex(packet))
            self.assertIsNone(t.lights)
