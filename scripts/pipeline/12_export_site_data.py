#!/usr/bin/env python3
"""
12_export_site_data.py

Exports final processed place data into website-ready JSON files.

Input:
  - data_processed/final/place_scores.json

Outputs:
  - data_export/places-index.json
  - data_export/places/<slug>.json
  - data_export/version.json
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

INPUT_JSON = Path("data_processed/final/place_scores.json")
EXPORT_DIR = Path("data_export")
INDEX_JSON = EXPORT_DIR / "places-index.json"
PLACES_DIR = EXPORT_DIR / "places"
VERSION_JSON = EXPORT_DIR / "version.json"


def load_json(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    if not INPUT_JSON.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_JSON}")

    rows = load_json(INPUT_JSON)

    index_rows = []
    for row in rows:
        index_rows.append(
            {
                "slug": row["slug"],
                "name": row["name"],
                "canton": row.get("canton", ""),
                "score_total": row["score_total"],
                "subscores": row["subscores"],
                "reachable_tags": row["reachable_tags"],
            }
        )

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    PLACES_DIR.mkdir(parents=True, exist_ok=True)

    with INDEX_JSON.open("w", encoding="utf-8") as f:
        json.dump(index_rows, f, ensure_ascii=False, indent=2)

    for row in rows:
        with (PLACES_DIR / f'{row["slug"]}.json').open("w", encoding="utf-8") as f:
            json.dump(row, f, ensure_ascii=False, indent=2)

    with VERSION_JSON.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "site_data_version": f"{date.today().isoformat()}-mvp",
                "updated_at": date.today().isoformat(),
                "place_count": len(rows),
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
