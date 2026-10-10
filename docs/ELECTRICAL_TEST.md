# Experimental voltage and odometer search

## Voltage

Packet `02 F8 32 01`, length 12; zero-based offsets 8–9, uint16 little-endian /100 V.

| Controlled state | Candidate V |
| --- | --- |
| Unplugged, SOC 92% | 40.90 |
| Charging, SOC 93% | 41.30 |
| Unplugged, fresh connection | 41.00 |
| Later unplugged | 40.80–40.90 |
| After ride, SOC 92% | 40.50 |
| Later live reading, SOC 89% | 40.50 |

Cached packets during the disconnect at unplugging are excluded from state validation. These are latest-message snapshots, not synchronized continuous captures.

The Electric Two [specification](https://d21buns5ku92am.cloudfront.net/69780/documents/53966-1706871941-2024-Veloretti-Electric%20Two-Specifications-7a9698.pdf) lists 36 Vdc nominal / 540 Wh and a 42 V 3 A charger. Observed behavior and magnitude support voltage, but independent measurement is still needed. Values zero or above 60 V are treated as invalid; this broad decoder guard is not an operating-limit specification. Voltage is live-only, shares freshness with the speed frame, and is cleared on reconnect.

Offsets 6–7 of the same packet stay zero throughout charging and the manual wheel test. Offsets 10–11 interpreted as signed LE remain -198 during the charge cycle. Neither establishes battery current or charging power. Battery-frame offsets 8–9 also stay 1066 during the charge cycle. No current or power sensors are enabled.

## Lifetime odometer search

The user expects approximately 4000–5000 km. An exploratory search of 2/3/4-byte windows after the four-byte discriminators, both endiannesses and decimal scales 1/10/100/1000, finds numeric matches. Their large number shows why magnitude alone is weak evidence.

- The obvious LE 4050–4130 values are the voltage candidate: they rise during charging and fall after unplugging/riding, so they are not a lifetime odometer.
- `00 00 02 50` has overlapping interpretations around 4070.4 -> 4121.6 -> 4070.4 -> 4044.8, following charging and decreasing, excluding those interpretations as cumulative distance.
- Static `01 F8 31 01`, `01 F8 31 02` and `02 F8 32 03` payloads produce various 4000–5000 matches, often only by combining neighboring bytes or changing endianness/scale. They do not change across the saved before/after ride snapshots; no specific candidate is supported.
- `04 F8 34 03` produces matches by combining probable clock/date bytes. These cannot establish distance.
- The known trip field changes and resets (1.23–1.25 previously, latest 0.64); it is not a lifetime total.

No convincing odometer mapping has been identified. An exact displayed total distance and a later reading after a known ride would allow better discrimination; a coarse 4000–5000 expectation cannot select among coincidental matches. No odometer sensor or speculative command writes were added.
