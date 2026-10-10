"""Experimental decoder. No command writes; unknown fields stay unknown."""

from dataclasses import dataclass, field

BATTERY_HEADER = bytes.fromhex("02 f8 32 00")
CHARGING_HEADER = bytes.fromhex("04 f8 34 02")
SPEED_HEADER = bytes.fromhex("02 f8 32 01")
LIGHT_HEADERS = (bytes.fromhex("14 a8 00 41"), bytes.fromhex("15 a2 00 41"))


@dataclass
class Telemetry:
    battery_soc: int | None = None
    range_km: float | None = None
    trip_km: float | None = None
    charging: bool | None = None
    lights: bool | None = None
    speed_kmh: float | None = None
    voltage_v: float | None = None
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
        if len(packet) == 12 and packet.startswith(SPEED_HEADER):
            speed = int.from_bytes(packet[4:6], "little") / 100
            self.speed_kmh = speed if speed <= 100 else None
            # Experimental voltage: rises during charging, falls after unplugging.
            voltage = int.from_bytes(packet[8:10], "little") / 100
            self.voltage_v = voltage if 0 < voltage <= 60 else None
            return False
        if len(packet) == 5 and packet[:4] in LIGHT_HEADERS:
            # Observed 06 -> 07 -> 06 follows lights on -> off -> on.
            # Other event codes may belong to other actions and are ignored.
            if packet[4] in (6, 7):
                self.lights = packet[4] == 6
            return False
        if len(packet) == 5 and packet.startswith(CHARGING_HEADER):
            # Only the reversible 00 -> 06 -> 00 test is known. Other codes
            # remain unknown, rather than interpreting undocumented bits.
            self.charging = {0: False, 6: True}.get(packet[4])
            return False
        if len(packet) != 12 or not packet.startswith(BATTERY_HEADER):
            return False
        # Byte 4 matched display SOC 91%; a later frame has 5C 01. Byte 5
        # varies independently and is not part of the SOC value.
        soc = packet[4]
        if not 0 <= soc <= 100:
            return False
        self.battery_soc = soc
        # Experimental: display Trip=1 with raw 123; wheel movement raised it
        # to 125. A second displayed distance is still needed to confirm scale.
        self.trip_km = int.from_bytes(packet[5:7], "little") / 100
        # Confirmed against display: 142 / 99 / 81 km at assistance 1 / 2 / 3.
        self.range_km = int.from_bytes(packet[10:12], "little") / 100
        self.battery_packets += 1
        return True
