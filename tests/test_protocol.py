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
        for index, value in ((4, 101), (5, 1), (0, 3)):
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
