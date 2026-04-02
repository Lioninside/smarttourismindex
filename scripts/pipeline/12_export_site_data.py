#!/usr/bin/env python3
"""
12_export_site_data.py

Exports final scored place data into website-ready JSON files.

Inputs:
  - data_processed/final/place_scores.json
  - data_processed/tourism_intensity_seasonality.csv  (seasonality + tourism_intensity)
  - data_processed/osm/osm_poi_metrics.json           (restaurant_count)
  - data_processed/heritage/heritage_metrics.json     (isos_name)

Outputs:
  - data_export/places-index.json          (lightweight index for list view)
  - data_export/places/<slug>.json         (full detail per place)
  - data_export/version.json
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple

INPUT_JSON     = Path("data_processed/final/place_scores.json")
INTENSITY_CSV  = Path("data_processed/tourism_intensity_seasonality.csv")
OSM_JSON       = Path("data_processed/osm/osm_poi_metrics.json")
HERITAGE_JSON  = Path("data_processed/heritage/heritage_metrics.json")
EXPORT_DIR     = Path("data_export")
INDEX_JSON     = EXPORT_DIR / "places-index.json"
PLACES_DIR     = EXPORT_DIR / "places"
VERSION_JSON   = EXPORT_DIR / "version.json"

MONTH_COLS = ["jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "oct", "nov", "dec"]


def load_json(path: Path) -> Any:
    if not path.exists():
        print(f"  WARNING: {path} not found")
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def index_by_slug(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {r["slug"]: r for r in rows if r.get("slug")}


def load_seasonality(
    path: Path,
    name_to_slug: Dict[str, str],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, float]]:
    """Return (seasonality_by_slug, intensity_by_slug)."""
    if not path.exists():
        print(f"  WARNING: {path} not found — seasonality omitted")
        return {}, {}

    seasonality: Dict[str, Dict[str, Any]] = {}
    intensity:   Dict[str, float] = {}

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            slug = row.get("slug", "").strip() or name_to_slug.get(row.get("gemeinde", "").strip())
            if not slug:
                continue

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

    print(f"  Seasonality: {len(seasonality)} communes matched")
    return seasonality, intensity


EXCLUDE_JSON   = Path("metadata/exclude.json")


def load_exclude() -> set:
    if not EXCLUDE_JSON.exists():
        return set()
    with EXCLUDE_JSON.open(encoding="utf-8") as f:
        return set(json.load(f))


def main() -> None:
    if not INPUT_JSON.exists():
        raise FileNotFoundError(f"Missing: {INPUT_JSON}")

    rows = load_json(INPUT_JSON)
    exclude = load_exclude()
    if exclude:
        before = len(rows)
        rows = [r for r in rows if r.get("slug") not in exclude]
        print(f"Excluded {before - len(rows)} places: {sorted(exclude)}")

    # Lookup tables
    name_to_slug: Dict[str, str] = {r["name"]: r["slug"] for r in rows}
    osm_by_slug     = index_by_slug(load_json(OSM_JSON))
    heritage_by_slug = index_by_slug(load_json(HERITAGE_JSON))
    seasonality_data, intensity_data = load_seasonality(INTENSITY_CSV, name_to_slug)

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    PLACES_DIR.mkdir(parents=True, exist_ok=True)

    # ── Lightweight index ────────────────────────────────────────────────
    index_rows = []
    for row in rows:
        slug = row["slug"]
        index_rows.append({
            "slug":          slug,
            "name":          row["name"],
            "canton":        row.get("canton", ""),
            "rank":          row.get("rank"),
            "score_total":   row["score_total"],
            "scores":        row.get("scores", {}),
            "subscores":     row.get("subscores", {}),
            "reachable_tags": row.get("reachable_tags", []),
        })

    with INDEX_JSON.open("w", encoding="utf-8") as f:
        json.dump(index_rows, f, ensure_ascii=False, indent=2)

    # ── Full place detail files ──────────────────────────────────────────
    for row in rows:
        slug   = row["slug"]
        detail = dict(row)   # shallow copy — already has scores, metrics, etc.

        # Seasonality (from 05b CSV)
        if slug in seasonality_data:
            detail["seasonality"] = seasonality_data[slug]

        # Tourism intensity raw value
        if slug in intensity_data:
            detail["tourism_intensity"] = intensity_data[slug]

        # Restaurant count from OSM (info only, not scored)
        osm = osm_by_slug.get(slug, {})
        detail["restaurant_count"] = osm.get("restaurant_count_2km", 0)

        # ISOS name from heritage metrics
        he = heritage_by_slug.get(slug, {})
        detail["isos_name"] = he.get("isos_name", "")

        # Ensure scores object uses new structure if present
        # (already written by 11_merge_score.py — pass through unchanged)

        # Remove any legacy UNESCO fields that may exist in old place files
        detail.pop("local_unesco", None)
        detail.pop("heritage_label", None)
        detail.pop("isos_score_placeholder", None)

        with (PLACES_DIR / f"{slug}.json").open("w", encoding="utf-8") as f:
            json.dump(detail, f, ensure_ascii=False, indent=2)

    # ── Version file ─────────────────────────────────────────────────────
    with VERSION_JSON.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "site_data_version": f"{date.today().isoformat()}-v2",
                "updated_at":        date.today().isoformat(),
                "place_count":       len(rows),
                "model_version":     "2.0",
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
