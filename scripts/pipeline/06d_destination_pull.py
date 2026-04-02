#!/usr/bin/env python3
"""
06d_destination_pull.py

Score each place on the total tourist destination weight of its reachable
commune set (excluding the base place itself).

Inputs:
  - metadata/places_master.csv
  - data_processed/gtfs/gtfs_reachability.json
  - data_processed/tourism_intensity_seasonality.csv  (has annual_overnights)

Output:
  - data_processed/destination_pull_metrics.json

Columns:
  slug, reachable_overnights_sum, destination_pull_score (0-1 normalised)

Method:
  Sum annual_overnights of all reachable communes, log1p-transform, then min-max.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List

PLACES_CSV       = Path("metadata/places_master.csv")
REACHABILITY_JSON = Path("data_processed/sbbapi/sbbAPI_reachability.json")
INTENSITY_CSV    = Path("data_processed/tourism_intensity_seasonality.csv")
OUTPUT_JSON      = Path("data_processed/destination_pull_metrics.json")


def read_places(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [
            {"slug": r["slug"].strip(), "name": r["name"].strip()}
            for r in reader
            if str(r.get("active", "")).strip().lower() == "true"
        ]


def load_overnights(path: Path, places: List[Dict[str, Any]]) -> Dict[str, float]:
    """Return slug -> annual_overnights mapping. Uses slug column if present, else name lookup."""
    name_to_slug = {p["name"]: p["slug"] for p in places}

    overnights: Dict[str, float] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            slug = row.get("slug", "").strip() or name_to_slug.get(row.get("gemeinde", "").strip())
            if not slug:
                continue
            raw = row.get("annual_overnights", "").strip()
            if raw and raw not in ("None", "nan", ""):
                try:
                    overnights[slug] = float(raw)
                except ValueError:
                    pass
    return overnights


def minmax_normalise(values: List[float]) -> List[float]:
    v_min = min(values)
    v_max = max(values)
    v_range = v_max - v_min if v_max > v_min else 1.0
    return [round((v - v_min) / v_range, 4) for v in values]


def main() -> None:
    for p in [PLACES_CSV, REACHABILITY_JSON, INTENSITY_CSV]:
        if not p.exists():
            raise FileNotFoundError(f"Missing: {p}")

    places = read_places(PLACES_CSV)
    reachability: Dict[str, List[str]] = json.loads(REACHABILITY_JSON.read_text(encoding="utf-8"))
    overnights = load_overnights(INTENSITY_CSV, places)

    rows: List[Dict[str, Any]] = []
    for place in places:
        slug = place["slug"]
        reachable = reachability.get(slug, [])

        total_overnights = sum(
            overnights.get(rslt, 0.0)
            for rslt in reachable
            if rslt != slug
        )

        rows.append({
            "slug":                    slug,
            "name":                    place["name"],
            "reachable_overnights_sum": round(total_overnights, 0),
            "_log_overnights":         math.log1p(total_overnights),
        })

    # Min-max normalise the log-transformed values
    log_norm = minmax_normalise([r["_log_overnights"] for r in rows])
    for i, row in enumerate(rows):
        row["destination_pull_score"] = log_norm[i]
        del row["_log_overnights"]

    rows.sort(key=lambda x: x["slug"])

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(rows)} rows")
    print(f"  destination_pull_score range: {min(r['destination_pull_score'] for r in rows):.3f}–{max(r['destination_pull_score'] for r in rows):.3f}")


if __name__ == "__main__":
    main()
