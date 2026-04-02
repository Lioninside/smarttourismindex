"""
NormalizePlacesMaster.py
========================
Converts the updated places_master.csv (semicolon-delimited, active=WAHR)
to the format expected by all pipeline scripts (comma-delimited, active=true).

Keeps ALL existing columns from the new file — just changes:
  - delimiter: ; → ,
  - active value: WAHR → true (and FALSCH → false if any)
  - encoding: utf-8-sig → utf-8

The new columns (main_station_name, station_id, station_api_name etc.)
are preserved so nothing is lost.

Input:  metadata/places_master.csv       (new format, semicolon)
Output: metadata/places_master.csv       (overwrite with pipeline-compatible format)
Backup: metadata/places_master_raw.csv   (original new format preserved)

Run from: project root OR scripts/tools/
"""

import csv
import shutil
from pathlib import Path

BASE = Path(__file__).parent
for candidate in [BASE, BASE.parent, BASE.parent.parent]:
    if (candidate / "metadata").exists():
        ROOT = candidate
        break
else:
    raise FileNotFoundError("Cannot find metadata/ folder")

SRC  = ROOT / "metadata" / "places_master.csv"
BKP  = ROOT / "metadata" / "places_master_raw.csv"
OUT  = ROOT / "metadata" / "places_master.csv"

# ── Read new format ───────────────────────────────────────────────────────────
print(f"Reading: {SRC}")
with open(SRC, encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f, delimiter=";")
    rows = list(reader)
    fieldnames = reader.fieldnames

print(f"  Rows: {len(rows)}")
print(f"  Columns: {fieldnames}")
print(f"  Delimiter: semicolon")
print(f"  Active values: {set(r.get('active','') for r in rows)}")

# ── Backup original ───────────────────────────────────────────────────────────
shutil.copy(SRC, BKP)
print(f"\nBackup saved → {BKP}")

# ── Normalise active values ───────────────────────────────────────────────────
ACTIVE_MAP = {
    "WAHR":  "true",
    "TRUE":  "true",
    "1":     "true",
    "YES":   "true",
    "FALSCH": "false",
    "FALSE": "false",
    "0":     "false",
    "NO":    "false",
}

converted = 0
for row in rows:
    original = row.get("active", "").strip().upper()
    row["active"] = ACTIVE_MAP.get(original, row["active"].lower())
    if original != row["active"].upper():
        converted += 1

print(f"Active values converted: {converted}")
print(f"Active values after: {set(r.get('active','') for r in rows)}")

# ── Write comma-delimited, utf-8 ─────────────────────────────────────────────
with open(OUT, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"\nWritten → {OUT}")
print(f"  Rows: {len(rows)}")
print(f"  Delimiter: comma")
print(f"  Encoding: utf-8")

# ── Verify ────────────────────────────────────────────────────────────────────
print("\nVerifying output…")
with open(OUT, encoding="utf-8", newline="") as f:
    verify = list(csv.DictReader(f))
print(f"  Rows readable: {len(verify)}")
print(f"  Active values: {set(r.get('active','') for r in verify)}")
print(f"  Sample: slug={verify[0]['slug']} active={verify[0]['active']} lat={verify[0]['lat']}")
print("\nDone. All pipeline scripts should now read places_master.csv correctly.")
