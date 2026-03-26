#!/usr/bin/env python3
"""
09_heritage.py

Combines UNESCO manual JSON with a simple local heritage signal.

Expected input:
  - places_master.csv
  - data_raw/heritage/swiss_unesco_sites.json
  - optional: a preprocessed ISOS CSV/JSON later

Output:
  - data_processed/heritage/heritage_metrics.json

MVP logic:
- use UNESCO JSON as curated source
- set local UNESCO flag if place name matches
- provide heritage placeholder field ready for ISOS enrichment later
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

PLACES_CSV = Path("metadata/places_master.csv")
UNESCO_JSON = Path("data_raw/heritage/swiss_unesco_sites.json")
OUTPUT_JSON = Path("data_processed/heritage/heritage_metrics.json")


def read_places(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            if str(row.get("active", "")).strip().lower() != "true":
                continue
            rows.append(
                {
                    "slug": row["slug"].strip(),
                    "name": row["name"].strip(),
                }
            )
        return rows


def load_unesco(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def names_from_unesco(data: Any) -> List[str]:
    names: List[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                for key in ("name", "title", "site_name"):
                    if key in item and item[key]:
                        names.append(str(item[key]))
                        break
            elif isinstance(item, str):
                names.append(item)
    elif isinstance(data, dict):
        if "sites" in data and isinstance(data["sites"], list):
            return names_from_unesco(data["sites"])
        for value in data.values():
            if isinstance(value, list):
                names.extend(names_from_unesco(value))
    return names


def main() -> None:
    places = read_places(PLACES_CSV)
    unesco = load_unesco(UNESCO_JSON)
    unesco_names = [n.lower() for n in names_from_unesco(unesco)]

    rows: List[Dict[str, Any]] = []
    for place in places:
        name_l = place["name"].lower()
        local_unesco = any(name_l in u or u in name_l for u in unesco_names)

        rows.append(
            {
                "slug": place["slug"],
                "name": place["name"],
                "local_unesco": local_unesco,
                "heritage_label": "strong" if local_unesco else "unknown",
                "isos_score_placeholder": None,
            }
        )

    rows.sort(key=lambda x: x["slug"])
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(rows)} rows")


if __name__ == "__main__":
    main()
