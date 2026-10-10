"""Summarize nRF Connect CSV without publishing device identities."""

import argparse
import csv
from collections import Counter
import re
from pathlib import Path
import runpy

Telemetry = runpy.run_path(
    str(Path(__file__).parents[1] / "custom_components/veloretti_ace_ble/protocol.py")
)["Telemetry"]
p = argparse.ArgumentParser()
p.add_argument("csv")
args = p.parse_args()
t = Telemetry()
values = Counter()
with open(args.csv, newline="") as f:
    for row in csv.DictReader(f):
        m = re.search(r"to ([0-9A-F ]+)\.", row["Line"])
        if m and "Updated Value of Characteristic" in row["Line"]:
            if t.receive(bytes.fromhex(m[1])):
                values[t.battery_soc] += 1
print(
    {
        "packets": t.packets_received,
        "candidate_soc_counts": dict(values),
        "raw_types": t.raw,
    }
)
