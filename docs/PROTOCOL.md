# Observations and decoding limits

## Sources
Original repository investigated at commit `8edf1bc14d98f53cfb96ca65f1e5d2906f4eb0d3`:
- [const.py](https://github.com/tieskuh/veloretti-ble-ha/blob/8edf1bc14d98f53cfb96ca65f1e5d2906f4eb0d3/custom_components/veloretti_ble/const.py): Nordic-style metrics/security GATT services.
- [comodule.py](https://github.com/tieskuh/veloretti-ble-ha/blob/8edf1bc14d98f53cfb96ca65f1e5d2906f4eb0d3/custom_components/veloretti_ble/comodule.py): old 10-byte register framing. SOC = register 00 C1, byte 7; assist/lights = 00 C0 bytes 2/3; speed = 02 50 byte 2; motion = 00 C3, big-endian uint16.
- `proto/`: authentication, register sweeps and CSV decoding. These are research scripts for the older profile, not definitions for 92914Bxx. No matching GATT UUIDs or a decoder for the observed Ace Two frame header were found.

User capture: 2704 characteristic updates, 17:03:40–17:05:38 notification stream. 423 identical battery candidate frames at display SOC 91%. No command writes recorded, just notification subscription. Repetition establishes a stable packet type, not independent SOC validation.

## Observed GATT
Service `92914b00-bfde-4176-b275-09a9e1e2c691`; command characteristic `92914b01-...` (Write); telemetry `92914b02-...` (Read/Notify). Advertising lists 16-bit 4B00/4B01/4B02, which are **not** the full GATT UUIDs.

## Candidate battery frame
`02 F8 32 00 5B 00 00 00 2A 04 D4 17` (12 bytes).
- Offset 0–3: observed discriminator, meaning unknown.
- Offset 4: 0x5B = 91, matches display. A later live frame contains `5C 01` at offsets 4/5. Decode byte 4 alone (candidate 92%); byte 5 is a separate unknown field. Accept only 0..100.
- Offset 10–11: uint16 little-endian /100 = estimated range in km. Controlled assistance changes produced 142, 99 and 81; user confirmed the displayed range.
- Other fields unknown; no voltage/current interpretation.

Other observed messages include `00 00 02 50 ...` and `00 00 02 51 ...`. Their resemblance to older registers is insufficient: framing and placement differ. Decode only the exact battery header/length; retain other packets as raw diagnostics. Speed, assist and current have not been mapped. Lights follow `14 A8 00 41 06/07` and `15 A2 00 41 06/07` in a reversible on/off/on test; see LIGHT_TEST.md. Controlled charger testing identified `04 F8 34 02 00/06` as experimental charging status; see CHARGING_TEST.md.

Live HA validation: 2026-10-10, Home Assistant 2026.10.0 with active NanoC6 proxy, subscription succeeded, decoded SOC 91%, live true, no integration system-log errors. This validates the real proxy path at one percentage.

Next: verify device identity and battery at a changed percentage; test reconnect, unload cleanup on real hardware and timestamp persistence. Compare controlled assist/light changes in future captures to infer additional fields. No command probing or speculative writes.

Second live comparison: user confirmed 92% on the display, charger NOT connected, matching `02 F8 32 00 5C 01 00 00 2A 04 D4 17`. This supports byte 4 as SOC and rules out interpreting byte 5=1 as sufficient evidence of charging. v0.1.2 decodes SOC as uint8. v0.1.1 added timed reconnect using fresh advertisements because HA change callbacks may suppress unchanged packets.
