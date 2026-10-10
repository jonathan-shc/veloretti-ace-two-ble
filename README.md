# Veloretti Ace Two BLE (experimental)

Local Home Assistant integration for the Ace Two V-S/V-R Bluetooth profile. Uses active ESPHome proxies (including NanoC6) or a connectable local adapter. Separate domain `veloretti_ace_ble`, so it can coexist with `veloretti_ble` and the cloud integration.

## Current status
Notification subscription and the candidate battery decoder are implemented and **tested live on Home Assistant 2026.10.0 through an active NanoC6 proxy**, reporting 91% with live connectivity. One user capture at a display SOC of 91% contains 423 matching battery packets. The user subsequently confirmed display SOC 92% against a second live frame; the decoder now treats its following byte as a separate unknown field. Other models, address stability, restart/reconnect behavior and charging with the bike switched off remain unverified.

Only battery (explicitly experimental), last battery measurement and live connectivity are exposed. Last-known battery and its timestamp survive a Home Assistant restart. Live means a connection plus a recognized battery frame in the last 30 seconds; advertising alone is insufficient.

## Installation
1. Add `jonathan-shc/veloretti-ace-two-ble` as a custom repository in HACS, category Integration; alternatively copy `custom_components/veloretti_ace_ble` to HA's `config/custom_components/`.
2. Restart HA. Enable active scanning and active connections on the ESPHome proxy near the bike.
3. Keep the bike on. Disconnect nRF Connect and close the official app so the connection is available.
4. Add **Veloretti Ace Two BLE** under Settings → Devices & services and select the V-S/V-R device. Discovery is only a candidate match; setup checks the full proprietary GATT service before subscribing.
5. Compare the experimental battery sensor with the display at multiple percentages before using it for charging decisions.

The integration subscribes to the read/notify characteristic. It does **not** write commands to the bike's command characteristic. Enabling notifications writes the standard CCCD descriptor. No account, cloud API, telemetry authentication handshake or shared key is used.

Do not assume charger connection wakes the bike or that the older Comodule sleeping behavior applies to this profile. Our on/off test did not stop this candidate from advertising. No charging-status sensor is claimed.

## Research and development
See [protocol findings](docs/PROTOCOL.md). Raw packet diagnostics are bounded and exclude device name/address, but unknown payloads may contain identifiers; inspect before sharing. Original CSV logs stay outside Git. Run `python -m unittest discover -s tests -v` and `python tools/analyze_capture.py /path/to/log.csv`.

Discovery flow adapted from [tieskuh/veloretti-ble-ha](https://github.com/tieskuh/veloretti-ble-ha), MIT licensed. This repository implements a different protocol; older Comodule register offsets are not reused.
