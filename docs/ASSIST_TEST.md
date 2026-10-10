# Controlled assist-level comparison, 2026-10-10

User set assistance levels one at a time; charger disconnected, SOC 93%, live BLE stream.

| Display assist level | Battery packet | Bytes 10–11, uint16 LE |
| --- | --- | --- |
| 1 | `02 F8 32 00 5D 00 00 00 2A 04 78 37` | 14200 |
| 2 | `02 F8 32 00 5D 00 00 00 2A 04 AC 26` | 9900 |
| 3 | `02 F8 32 00 5D 00 00 00 2A 04 A4 1F` | 8100 |

Hypothesis: these values are remaining estimated range in hundredths of km (142, 99, 81 km), responding to assistance changes. The user confirmed 81 km on the display at level 3, identifying this field as range. No direct support-level field has been identified, and assistance must NOT be inferred from this range because battery/conditions also affect it.

Other observed changes: 02 F8 32 01 tail fluctuates between approximately 0FF0/0FFA etc.; 04 F8 34 03 appears to carry a running timestamp; 02 F8 30 00 carries a rising counter. These are not sufficient evidence of support level.
