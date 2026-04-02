"""
05b_tourism_intensity_seasonality.py
=====================================
Produces two new metrics per commune, sourced from the 2024 BFS data:

  1. Tourism intensity  = annual hotel overnights / resident population
     - The EU Commission / BFS / Watson indicator for overtourism pressure
     - Used in the Anti-overtourism dimension of 11_merge_score.py
       (replaces / supplements the raw overnight count)

  2. Seasonality profile = 12 monthly values indexed to the annual average
     - Index 100 = exactly average month
     - Peak-to-trough ratio + volatility label
     - Written to export JSON for the place detail widget (NOT used in score)

Input files (place in data_raw/bfs/):
  px-x-1003020000_101_*.csv   — monthly overnights by commune (English, 2024+2025)
  px-x-0102010000_101_*.csv   — STATPOP resident population by commune (2024)

Output (written to data_processed/):
  tourism_intensity_seasonality.csv

Columns in output:
  slug, gemeinde, population, annual_overnights, tourism_intensity,
  nights_jan … nights_dec,           (raw overnights per month)
  idx_jan … idx_dec,                 (indexed to avg month = 100)
  peak_month, trough_month, peak_trough_ratio, volatility_label
"""

import json
import re
import pandas as pd
import numpy as np
from pathlib import Path

# ── Paths (relative to project root — script must be run from project root) ──
RAW_BFS   = Path("data_raw/bfs")
PROCESSED = Path("data_processed")
PROCESSED.mkdir(exist_ok=True)

FILE_101    = next(RAW_BFS.glob("px-x-1003020000_101_*.csv"))
FILE_POP    = next(RAW_BFS.glob("px-x-0102010000_101_*.csv"))
MAPPING_JSON = Path("metadata/place_mapping.json")

print(f"Using 101 file : {FILE_101.name}")
print(f"Using POP file : {FILE_POP.name}")

# ── Month ordering ──────────────────────────────────────────────────────────
# File is English but "July" appears as "Juli" — handle both
MONTH_ORDER = [
    "January", "February", "March", "April", "May", "June",
    "Juli",     # ← mixed German/English quirk in BFS export
    "July",     # include both so re-sort works regardless
    "August", "September", "October", "November", "December"
]
# Canonical short names for output columns (always English)
MONTH_COLS = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]

# BFS month name → canonical index 0..11
MONTH_INDEX = {
    "January":0, "February":1, "March":2, "April":3, "May":4,
    "June":5, "Juli":6, "July":6,
    "August":7, "September":8, "October":9, "November":10, "December":11,
}

# ── Load place mapping — BFS commune name → slug ────────────────────────────
_commune_to_slug: dict = {}
if MAPPING_JSON.exists():
    _raw_mapping = json.loads(MAPPING_JSON.read_text(encoding="utf-8"))
    _commune_to_slug = {bfs_name: v["slug"] for bfs_name, v in _raw_mapping.items() if "slug" in v}
    print(f"Loaded {len(_commune_to_slug)} commune→slug entries from {MAPPING_JSON.name}")
else:
    print(f"WARNING: {MAPPING_JSON} not found — slug column will be empty")

# ── Manual commune name overrides ───────────────────────────────────────────
# These 3 communes appear differently in the two source files
NAME_OVERRIDES = {
    "Moutier (BE)": "Moutier",   # STATPOP uses plain "Moutier" for the BE version
    "Moutier (JU)": "Moutier",   # same raw STATPOP name — handled by slug below
    "Laténa":       "Laténa",    # check if STATPOP has accent variant
}

# ── 1. Load STATPOP — resident population per commune (2024) ────────────────
print("\nLoading STATPOP …")
dfpop_raw = pd.read_csv(FILE_POP, encoding="ISO-8859-1")

pop = dfpop_raw[
    (dfpop_raw["Bevölkerungstyp"] == "Ständige Wohnbevölkerung") &
    (dfpop_raw["Staatsangehörigkeit (Kategorie)"] == "Staatsangehörigkeit (Kategorie) - Total") &
    (dfpop_raw["Geschlecht"] == "Geschlecht - Total") &
    (dfpop_raw["Jahr"] == 2024) &
    (dfpop_raw["Kanton (-) / Bezirk (>>) / Gemeinde (......)"].str.startswith("......"))
].copy()

# Strip BFS prefix "......XXXX " to get plain commune name
pop["gemeinde"] = (
    pop["Kanton (-) / Bezirk (>>) / Gemeinde (......)"]
    .str.replace(r"^\.\.\.\.\.\.\d{4}\s+", "", regex=True)
    .str.strip()
)
pop = pop[["gemeinde", "Alter - Total"]].rename(columns={"Alter - Total": "population"})
pop_lookup = pop.set_index("gemeinde")["population"].to_dict()
print(f"  STATPOP communes loaded: {len(pop_lookup)}")

# ── 2. Load 101 — monthly overnights, 2024 ─────────────────────────────────
print("Loading 101 monthly overnights …")
df = pd.read_csv(FILE_101, encoding="ISO-8859-1")
df = df[df["Year"] == 2024].copy()

NIGHT_COL = "Visitors' country of residence - total Overnight stays"

# Replace BFS placeholder values with 0
df[NIGHT_COL] = (
    pd.to_numeric(df[NIGHT_COL].replace({"...": 0, "-": 0}), errors="coerce")
    .fillna(0)
    .astype(int)
)

# Map month names to 0-based index
df["month_idx"] = df["Month"].map(MONTH_INDEX)
missing_months = df[df["month_idx"].isna()]["Month"].unique()
if len(missing_months):
    print(f"  WARNING: unrecognised month names: {missing_months}")

communes = sorted(df["Commune"].unique())
print(f"  Communes with 2024 monthly data: {len(communes)}")

# ── 3. Build per-commune metrics ────────────────────────────────────────────
print("Computing metrics …")
records = []

for commune in communes:
    sub = df[df["Commune"] == commune].copy()
    sub = sub.sort_values("month_idx")

    # Monthly raw overnights (12 values, in Jan-Dec order)
    monthly = np.zeros(12, dtype=float)
    for _, row in sub.iterrows():
        idx = row["month_idx"]
        if not pd.isna(idx):
            monthly[int(idx)] = row[NIGHT_COL]

    annual = monthly.sum()

    # Population lookup — try exact name, then override map
    pop_name = NAME_OVERRIDES.get(commune, commune)
    population = pop_lookup.get(pop_name) or pop_lookup.get(commune)

    if population is None or population == 0:
        print(f"  WARNING: no population for '{commune}' — skipping intensity")
        tourism_intensity = None
    else:
        tourism_intensity = round(annual / population, 1)

    # Indexed seasonality (avg month = 100)
    avg = annual / 12 if annual > 0 else 1
    indexed = (monthly / avg * 100).round(1)

    # Peak / trough
    peak_idx   = int(np.argmax(indexed))
    trough_idx = int(np.argmin(indexed))
    trough_val = indexed[trough_idx]
    ratio = round(indexed[peak_idx] / max(trough_val, 1), 2)

    # Volatility label
    if ratio < 2.5:
        label = "Year-round"
    elif ratio < 5.0:
        label = "Mildly seasonal"
    elif ratio < 8.0:
        label = "Strongly seasonal"
    else:
        label = "Highly seasonal"

    record = {
        "slug":              _commune_to_slug.get(commune, ""),
        "gemeinde":          commune,
        "population":        population,
        "annual_overnights": int(annual),
        "tourism_intensity": tourism_intensity,
    }
    # Raw monthly overnights
    for i, col in enumerate(MONTH_COLS):
        record[f"nights_{col}"] = int(monthly[i])
    # Indexed monthly values
    for i, col in enumerate(MONTH_COLS):
        record[f"idx_{col}"] = float(indexed[i])

    record["peak_month"]        = MONTH_COLS[peak_idx]
    record["trough_month"]      = MONTH_COLS[trough_idx]
    record["peak_trough_ratio"] = ratio
    record["volatility_label"]  = label

    records.append(record)

result = pd.DataFrame(records)
print(f"\nResult shape: {result.shape}")

# ── 4. Summary stats ─────────────────────────────────────────────────────────
ti = result["tourism_intensity"].dropna()
print(f"\nTourism intensity (overnights per resident):")
print(f"  min    : {ti.min():.1f}")
print(f"  median : {ti.median():.1f}")
print(f"  max    : {ti.max():.1f}")
print(f"  mean   : {ti.mean():.1f}")

print(f"\nVolatility distribution:")
print(result["volatility_label"].value_counts().to_string())

print(f"\nTop 15 by tourism intensity:")
top = result.nlargest(15, "tourism_intensity")[
    ["gemeinde","population","annual_overnights","tourism_intensity","peak_month","peak_trough_ratio","volatility_label"]
]
print(top.to_string(index=False))

# ── 5. Save ──────────────────────────────────────────────────────────────────
out_path = PROCESSED / "tourism_intensity_seasonality.csv"
result.to_csv(out_path, index=False)
print(f"\nSaved → {out_path}")
print("Done.")
