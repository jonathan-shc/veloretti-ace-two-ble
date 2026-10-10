"""Experimental decoder. No command writes; unknown fields stay unknown."""

from dataclasses import dataclass, field

BATTERY_HEADER = bytes.fromhex("02 f8 32 00")


@dataclass
class Telemetry:
    battery_soc: int | None = None
    raw: dict[str, str] = field(default_factory=dict)
    packets_received: int = 0
    battery_packets: int = 0

    def receive(self, packet: bytes) -> bool:
        """Record bounded raw samples; return whether a valid battery frame arrived."""
        self.packets_received += 1
        if packet:
            # Prefix plus length distinguishes observed multiplexed packet types.
            key = f"{packet[:4].hex()}:{len(packet)}"
            if key in self.raw or len(self.raw) < 64:
                self.raw[key] = packet[:64].hex(" ")
        if len(packet) != 12 or not packet.startswith(BATTERY_HEADER):
            return False
        # Observed 5B 00 matches 91%. uint16 LE is provisional; the zero high
        # byte prevents accidental acceptance of wider/out-of-range values.
        soc = int.from_bytes(packet[4:6], "little")
        if not 0 <= soc <= 100:
            return False
        self.battery_soc = soc
        self.battery_packets += 1
        return True
