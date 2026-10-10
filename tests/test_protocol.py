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


class SpeedTests(unittest.TestCase):
    def test_wheel_capture_speeds(self):
        for payload, expected in (
            ("c1 01", 4.49),
            ("11 03", 7.85),
            ("14 03", 7.88),
            ("94 02", 6.60),
            ("00 00", 0),
        ):
            t = Telemetry(battery_soc=92, range_km=79)
            self.assertFalse(
                t.receive(
                    bytes.fromhex("02 f8 32 01 " + payload + " 00 00 dc 0f 3b ff")
                )
            )
            self.assertAlmostEqual(t.speed_kmh, expected)
            self.assertEqual(t.battery_soc, 92)
            self.assertEqual(t.range_km, 79)

    def test_bad_speed_frames(self):
        t = Telemetry()
        for frame in ("02 f8 32 01 11 03", "02 f8 32 00 5c 00 00 00 2a 04 dc 1e"):
            t.receive(bytes.fromhex(frame))
            self.assertIsNone(t.speed_kmh)
        t.receive(bytes.fromhex("02 f8 32 01 ff ff 00 00 dc 0f 3b ff"))
        self.assertIsNone(t.speed_kmh)


class TripTests(unittest.TestCase):
    def test_captured_trip_candidate_changes(self):
        t = Telemetry()
        for value, expected in (("7b 00", 1.23), ("7c 00", 1.24), ("7d 00", 1.25)):
            self.assertTrue(
                t.receive(bytes.fromhex("02 f8 32 00 5c " + value + " 00 2a 04 dc 1e"))
            )
            self.assertAlmostEqual(t.trip_km, expected)
            self.assertEqual(t.battery_soc, 92)
            self.assertEqual(t.range_km, 79)

    def test_trip_zero_reset_and_high_byte(self):
        t = Telemetry(trip_km=1.25)
        t.receive(bytes.fromhex("02 f8 32 00 5c 00 00 00 2a 04 dc 1e"))
        self.assertEqual(t.trip_km, 0)
        t.receive(bytes.fromhex("02 f8 32 00 5c 2c 01 00 2a 04 dc 1e"))
        self.assertEqual(t.trip_km, 3)

    def test_non_battery_frames_do_not_overwrite_trip(self):
        t = Telemetry(trip_km=1.25)
        for packet in (
            "02 f8 32 01 14 03 00 00 dc 0f 3b ff",
            "04 f8 34 02 06",
            "14 a8 00 41 06",
        ):
            t.receive(bytes.fromhex(packet))
            self.assertEqual(t.trip_km, 1.25)


class VoltageTests(unittest.TestCase):
    def test_charger_cycle_and_latest_reading(self):
        t = Telemetry(battery_soc=89)
        for value, expected in (
            ("fa 0f", 40.90), ("22 10", 41.30),
            ("04 10", 41.00), ("d2 0f", 40.50),
        ):
            self.assertFalse(t.receive(bytes.fromhex(
                "02 f8 32 01 00 00 00 00 " + value + " 3c ff"
            )))
            self.assertAlmostEqual(t.voltage_v, expected)
            self.assertEqual(t.battery_soc, 89)

    def test_invalid_voltage_and_unrelated_frames(self):
        t = Telemetry(voltage_v=40.5)
        t.receive(bytes.fromhex("02 f8 32 00 59 40 00 00 2e 04 0c 17"))
        self.assertEqual(t.voltage_v, 40.5)
        for voltage in ("00 00", "ff ff"):
            t.receive(bytes.fromhex("02 f8 32 01 00 00 00 00 " + voltage + " 3c ff"))
            self.assertIsNone(t.voltage_v)


class PowerEventTests(unittest.TestCase):
    def test_observed_on_off_and_unknown_codes(self):
        t = Telemetry()
        self.assertIsNone(t.powered)
        self.assertFalse(t.receive(bytes.fromhex("02 f8 32 04 01")))
        self.assertTrue(t.powered)
        self.assertFalse(t.receive(bytes.fromhex("02 f8 32 04 00")))
        self.assertFalse(t.powered)
        t.receive(bytes.fromhex("02 f8 32 04 02"))
        self.assertIsNone(t.powered)

    def test_truncated_shutdown_does_not_mean_off(self):
        t = Telemetry(powered=True)
        t.receive(bytes.fromhex("02 f8 32 04"))
        self.assertTrue(t.powered)
