# Controlled charger test, 2026-10-10

One observed Ace Two, display on, phone app disconnected. No setting changes requested besides charger connection.

| User-observed state | Telemetry packet | SOC |
| --- | --- | --- |
| Charger disconnected (baseline) | `04 F8 34 02 00` | 92% |
| Charger connected, display indicates charging | `04 F8 34 02 06` | 93% |
| Charger disconnected again, display still on | `04 F8 34 02 00` | 93% |

The connection briefly stopped during unplugging, then automatically reconnected and provided a fresh 00 packet. Cached values were not used to confirm the final transition.

This reversible 00 -> 06 -> 00 sequence supports an experimental charging-status interpretation. Do not yet claim a universal charger-connected flag or decode individual bits: only states 00 (not charging in this test) and 06 (charging in this test) are observed. Full battery with charger attached, faults, other models and intermediate states are untested. Unknown state values should remain unknown. Current/voltage fields are not mapped.
