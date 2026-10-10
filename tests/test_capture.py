"""Retain transient and repeated messages while bounding memory and payloads."""

from pathlib import Path
import runpy
import unittest

PacketCapture = runpy.run_path(str(
    Path(__file__).parents[1] / "custom_components/veloretti_ace_ble/capture.py"
))["PacketCapture"]


class CaptureTests(unittest.TestCase):
    def test_transient_and_duplicate_packets_keep_order(self):
        c = PacketCapture(limit=4)
        for packet in (b"a", b"b", b"a", b"a"):
            c.record(packet, "time")
        result = c.snapshot()
        self.assertEqual([p["hex"] for p in result["packets"]], ["61", "62", "61", "61"])
        self.assertEqual([p["sequence"] for p in result["packets"]], [1, 2, 3, 4])

    def test_capacity_and_sequence_expose_loss(self):
        c = PacketCapture(limit=2)
        for _ in range(5):
            c.record(bytes(100), "time")
        result = c.snapshot()
        self.assertEqual(result["evicted"], 3)
        self.assertEqual([p["sequence"] for p in result["packets"]], [4, 5])
        self.assertEqual(result["packets"][0]["length"], 100)
        self.assertEqual(len(bytes.fromhex(result["packets"][0]["hex"])), 64)
        self.assertEqual(PacketCapture().snapshot()["packets"], [])
