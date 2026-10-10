# Controlled light test, 2026-10-10

Bike on, assistance level 3, charger disconnected, SOC 93%, live notifications.

| User-observed state | 14 A8 00 41 packet | 15 A2 00 41 packet |
| --- | --- | --- |
| Lights on | 14 A8 00 41 06 | 15 A2 00 41 06 |
| Lights off | 14 A8 00 41 07 | 15 A2 00 41 07 |
| Lights on again | 14 A8 00 41 06 | 15 A2 00 41 06 |

The reversal supports a light-state event interpretation, rather than an increasing press counter. These messages may be acknowledgements/events rather than periodic snapshots; the sensor is explicitly experimental and unknown at each new connection until a known event arrives. Other event codes and prefixes remain undecoded. No commands are sent to the bike.
