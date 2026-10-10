"""Bounded, in-memory notification history for controlled protocol research."""

from collections import deque


class PacketCapture:
    def __init__(self, limit=6000):
        self.packets = deque(maxlen=limit)
        self.total = 0

    def record(self, packet: bytes, timestamp: str) -> None:
        self.total += 1
        self.packets.append({
            "sequence": self.total,
            "timestamp": timestamp,
            "length": len(packet),
            "hex": packet[:64].hex(" "),
        })

    def snapshot(self):
        return {
            "capacity": self.packets.maxlen,
            "total_received": self.total,
            "evicted": self.total - len(self.packets),
            "packets": list(self.packets),
        }
