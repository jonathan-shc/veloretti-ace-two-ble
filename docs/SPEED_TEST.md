# Controlled wheel-speed test, 2026-10-10

Bike remains near the NanoC6. User manually rotated the wheel, reporting an initial 4 km/h, then 6, 8, 7, 6, 0 km/h on the display. A 60-second diagnostic capture sampled the live stream roughly every 1.5 seconds (39 samples).

Packet `02 F8 32 01` (12 bytes) offsets 4–5, uint16 little-endian /100:

| Captured bytes | Decoded km/h |
| --- | --- |
| C1 01 | 4.49 |
| 11 03 | 7.85 |
| 14 03 | 7.88 |
| 94 02 | 6.60 |
| 00 00 | 0 |

This matches the observed low-speed wheel test, including return to zero. Sparse diagnostic sampling cannot match every displayed intermediate speed precisely. Speed sensor is experimental, unavailable without a fresh speed frame in the current connection, and is not restored from a previous ride. It does not provide speed when the bike leaves Bluetooth range.

Trip candidate: offsets 5–6 of the battery packet rose 123 -> 124 -> 125 during the second wheel rotation. A /100 scale would mean 1.23 -> 1.25 km, compatible with the displayed rounded Trip=1 and roughly 20m from wheel rotation, but a second displayed trip distance is still needed. Trip was subsequently added as explicitly experimental at the user’s request, with the above scaling still awaiting a second displayed distance.

AVG remains unconfirmed: packet `02 F8 32 05 0B 00` stayed at 11 while the user reported AVG 9, then 12, then 11. It must not be labeled average speed from the final coincidence alone.
