#!/usr/bin/env python3
"""
12_export_site_data.py

Exports final processed place data into website-ready JSON files.

Inputs:
  - data_processed/final/place_scores.json
  - data_processed/tourism_intensity_seasonality.csv  (from 05b)

Outputs:
  - data_export/places-index.json          (lightweight index, no seasonality)
  - data_export/places/<slug>.json         (full detail + seasonality + tourism_intensity)
  - data_export/version.json
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple

INPUT_JSON    = Path("data_processed/final/place_scores.json")
INTENSITY_CSV = Path("data_processed/tourism_intensity_seasonality.csv")
EXPORT_DIR    = Path("data_export")
INDEX_JSON    = EXPORT_DIR / "places-index.json"
PLACES_DIR    = EXPORT_DIR / "places"
VERSION_JSON  = EXPORT_DIR / "version.json"

MONTH_COLS = ["jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "oct", "nov", "dec"]


def load_json(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_seasonality(
    path: Path,
    name_to_slug: Dict[str, str],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, float]]:
    """
    Load tourism_intensity_seasonality.csv.

    Returns:
      seasonality_by_slug  – slug -> seasonality object for place JSON
      intensity_by_slug    – slug -> tourism_intensity float
    """
    if not path.exists():
        print(f"WARNING: {path} not found — seasonality fields will be omitted from export")
        return {}, {}

    seasonality: Dict[str, Dict[str, Any]] = {}
    intensity: Dict[str, float] = {}

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gemeinde = row.get("gemeinde", "").strip()
            slug = name_to_slug.get(gemeinde)
            if slug is None:
                continue

            # Monthly index: 12 integers (Jan-Dec), avg month = 100
            try:
                monthly_index = [round(float(row[f"idx_{m}"])) for m in MONTH_COLS]
            except (KeyError, ValueError):
                continue

            seasonality[slug] = {
                "volatility_label":  row.get("volatility_label", ""),
                "peak_month":        row.get("peak_month", ""),
                "trough_month":      row.get("trough_month", ""),
                "peak_trough_ratio": round(float(row.get("peak_trough_ratio") or 0), 2),
                "monthly_index":     monthly_index,
            }

            raw_ti = row.get("tourism_intensity", "").strip()
            if raw_ti and raw_ti not in ("None", "nan"):
                try:
                    intensity[slug] = round(float(raw_ti), 1)
                except ValueError:
                    pass

    print(f"  Seasonality data: {len(seasonality)} communes matched to slugs")
    return seasonality, intensity


def main() -> None:
    if not INPUT_JSON.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_JSON}")

    rows = load_json(INPUT_JSON)

    # Build name -> slug from the scores data for joining the intensity CSV
    name_to_slug: Dict[str, str] = {row["name"]: row["slug"] for row in rows}

    seasonality_data, intensity_data = load_seasonality(INTENSITY_CSV, name_to_slug)

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    PLACES_DIR.mkdir(parents=True, exist_ok=True)

    # ── Lightweight index (no seasonality — keeps index.json small) ────────
    index_rows = [
        {
            "slug":          row["slug"],
            "name":          row["name"],
            "canton":        row.get("canton", ""),
            "score_total":   row["score_total"],
            "subscores":     row["subscores"],
            "reachable_tags": row["reachable_tags"],
        }
        for row in rows
    ]

    with INDEX_JSON.open("w", encoding="utf-8") as f:
        json.dump(index_rows, f, ensure_ascii=False, indent=2)

    # ── Full place detail files ────────────────────────────────────────────
    for row in rows:
        slug = row["slug"]
        detail = dict(row)  # shallow copy

        if slug in seasonality_data:
            detail["seasonality"] = seasonality_data[slug]
        if slug in intensity_data:
            detail["tourism_intensity"] = intensity_data[slug]

        with (PLACES_DIR / f"{slug}.json").open("w", encoding="utf-8") as f:
            json.dump(detail, f, ensure_ascii=False, indent=2)

    # ── Version file ───────────────────────────────────────────────────────
    with VERSION_JSON.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "site_data_version": f"{date.today().isoformat()}-mvp",
                "updated_at":        date.today().isoformat(),
                "place_count":       len(rows),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Wrote {INDEX_JSON}")
    print(f"Wrote {VERSION_JSON}")
    print(f"Wrote {len(rows)} place detail files to {PLACES_DIR}")


if __name__ == "__main__":
    main()
