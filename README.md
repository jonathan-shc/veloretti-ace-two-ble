# Veloretti Ace Two BLE (experimental)

Local Home Assistant integration for the Ace Two V-S/V-R Bluetooth profile. Uses active ESPHome proxies (including NanoC6) or a connectable local adapter. Separate domain `veloretti_ace_ble`, so it can coexist with `veloretti_ble` and the cloud integration.

## Current status
Notification subscription and the candidate battery decoder are implemented and **tested live on Home Assistant 2026.10.0 through an active NanoC6 proxy**, reporting 91% with live connectivity. One user capture at a display SOC of 91% contains 423 matching battery packets. Controlled tests additionally mapped display range and reversible charging/light statuses. The user subsequently confirmed display SOC 92% against a second live frame; the decoder now treats its following byte as a separate unknown field. Other models, address stability, restart/reconnect behavior and charging with the bike switched off remain unverified.

Battery (explicitly experimental), remaining estimated range in km, experimental charging status, experimental lights, experimental live speed, experimental trip distance, last battery measurement and live connectivity are exposed. Range is the bike display estimate, not a separately calculated prediction. Last-known battery, range, trip distance and the measurement timestamp survive a Home Assistant restart. Charging is not restored: it becomes unavailable without a recent charging-status frame. Unknown status codes are not decoded. Lights are event-derived: after reconnect they remain unavailable until a recognized on/off event arrives; toggle the lights once using the bike controls to establish a new reading. Live means a connection plus a recognized battery frame in the last 30 seconds; advertising alone is insufficient.

## Installation
1. Add `jonathan-shc/veloretti-ace-two-ble` as a custom repository in HACS, category Integration; alternatively copy `custom_components/veloretti_ace_ble` to HA's `config/custom_components/`.
2. Restart HA. Enable active scanning and active connections on the ESPHome proxy near the bike.
3. Keep the bike on. Disconnect nRF Connect and close the official app so the connection is available.
4. Add **Veloretti Ace Two BLE** under Settings → Devices & services and select the V-S/V-R device. Discovery is only a candidate match; setup checks the full proprietary GATT service before subscribing.
5. Compare the experimental battery sensor with the display at multiple percentages before using it for charging decisions.

The integration subscribes to the read/notify characteristic. It does **not** write commands to the bike's command characteristic. Enabling notifications writes the standard CCCD descriptor. No account, cloud API, telemetry authentication handshake or shared key is used.

Do not assume charger connection wakes the bike or that the older Comodule sleeping behavior applies to this profile. Our on/off test did not stop this candidate from advertising. Charging status was tested using a charger-disconnected → charging → disconnected cycle (codes 00 → 06 → 00). A connected charger at full battery and other codes remain untested; this sensor does not claim to detect every charger-connected condition.

## Research and development
See [protocol findings](docs/PROTOCOL.md). Raw packet diagnostics are bounded and exclude device name/address, but unknown payloads may contain identifiers; inspect before sharing. Original CSV logs stay outside Git. Run `python -m unittest discover -s tests -v` and `python tools/analyze_capture.py /path/to/log.csv`.

Discovery flow adapted from [tieskuh/veloretti-ble-ha](https://github.com/tieskuh/veloretti-ble-ha), MIT licensed. This repository implements a different protocol; older Comodule register offsets are not reused.

Speed was compared with the display by rotating the wheel near the proxy (about 4–8 km/h plus standstill). It is unavailable without fresh speed packets; Bluetooth cannot report speed while the bike is out of range. Trip is exposed as an explicitly experimental sensor at the user’s request: battery-frame offsets 5–6, uint16 LE /100. The observed 1.23–1.25 km is compatible with display Trip=1, but a second displayed trip distance is still required to confirm scaling and reset behavior. AVG remains undecoded.

Experimental battery voltage uses speed-frame offsets 8–9, uint16 LE /100 V. A controlled charging cycle produced 40.90 → 41.30 → 41.00 V, then 40.80–40.90 V; later unplugged readings were 40.50 V. This is compatible with the Electric Two specification (36 V nominal battery, 42 V charger), but the field and scaling are not independently measured. Voltage is not restored and is unavailable without a fresh telemetry frame. Current, power and lifetime odometer remain undecoded. See [electrical and odometer findings](docs/ELECTRICAL_TEST.md).

Diagnostics include a rolling, memory-only capture of the last 6000 notifications, preserving repeated and transient packets with sequence numbers and UTC timestamps. Payloads are capped at 64 bytes, with original length retained. Eviction counts make missing history visible. The buffer spans reconnects but clears on integration unload/restart; nothing is saved to disk or sent externally automatically. Unknown payloads may contain identifiers: inspect before sharing diagnostic captures. This history supports controlled screen-switch research and is not an odometer decoder.

## Observed display power

The experimental power binary sensor decodes only the observed `02 f8 32 04` five-byte on (`01`) / off (`00`) event. It retains the event with an `observed_at` timestamp; Bluetooth loss alone does not mean the display is off. Unknown codes remain unknown. No Bluetooth commands are sent to wake the bike.
