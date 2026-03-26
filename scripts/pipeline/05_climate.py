#!/usr/bin/env python3
"""
05_climate.py

Reads MeteoSwiss climate-normal NetCDF files and exports one normalized climate
record per place using nearest-point lookup.

Inputs:
  - places_master.csv
  - data_raw/climate/klimanormwerte-temperatur_aktuelle_periode_monthly_2056.nc
  - data_raw/climate/klimanormwerte-niederschlag_aktuelle_periode_monthly_2056.nc
  - data_raw/climate/klimanormwerte-sonnenscheindauer_aktuelle_periode_monthly_2056.nc

Output:
  - data_processed/climate/climate_metrics_jja.json
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import xarray as xr
from pyproj import Transformer

PLACES_CSV = Path("metadata/places_master.csv")
TEMP_NC = Path("data_raw/climate/klimanormwerte-temperatur_aktuelle_periode_monthly_2056.nc")
PRECIP_NC = Path("data_raw/climate/klimanormwerte-niederschlag_aktuelle_periode_monthly_2056.nc")
SUN_NC = Path("data_raw/climate/klimanormwerte-sonnenscheindauer_aktuelle_periode_monthly_2056.nc")
OUTPUT_JSON = Path("data_processed/climate/climate_metrics_jja.json")

SUMMER_MONTHS = {6, 7, 8}

# WGS84 -> LV95
TRANSFORMER = Transformer.from_crs("EPSG:4326", "EPSG:2056", always_xy=True)


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
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                }
            )
        return rows


def pick_data_var(ds: xr.Dataset) -> str:
    candidates = [v for v in ds.data_vars if v not in {"swiss_lv95_coordinates", "climatology_bounds"}]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError(f"No usable climate data variable found in dataset: {list(ds.data_vars)}")
    return candidates[0]


def normalize_month_value(v: Any) -> int:
    month_num = int(v)
    if month_num == 0:
        return 1
    if 0 <= month_num <= 11:
        return month_num + 1
    return month_num


def summer_mean_for_place(ds: xr.Dataset, lat_wgs84: float, lon_wgs84: float) -> float:
    var_name = pick_data_var(ds)

    # Convert WGS84 lon/lat to LV95 E/N
    e_lv95, n_lv95 = TRANSFORMER.transform(lon_wgs84, lat_wgs84)

    sub = ds[var_name].sel(N=n_lv95, E=e_lv95, method="nearest")

    time_values = sub["time"].values
    month_mask = [normalize_month_value(v) in SUMMER_MONTHS for v in time_values]

    summer = sub.isel(time=month_mask)
    return round(float(summer.mean(skipna=True).values), 2)


def main() -> None:
    for p in [PLACES_CSV, TEMP_NC, PRECIP_NC, SUN_NC]:
        if not p.exists():
            raise FileNotFoundError(f"Missing input file: {p}")

    places = read_places(PLACES_CSV)

    ds_temp = xr.open_dataset(TEMP_NC, decode_times=False)
    ds_precip = xr.open_dataset(PRECIP_NC, decode_times=False)
    ds_sun = xr.open_dataset(SUN_NC, decode_times=False)

    rows: List[Dict[str, Any]] = []

    for place in places:
        rows.append(
            {
                "slug": place["slug"],
                "name": place["name"],
                "summer_temp_avg": summer_mean_for_place(ds_temp, place["lat"], place["lon"]),
                "summer_precip_avg": summer_mean_for_place(ds_precip, place["lat"], place["lon"]),
                "summer_sunshine_avg": summer_mean_for_place(ds_sun, place["lat"], place["lon"]),
            }
        )

    rows.sort(key=lambda x: x["slug"])

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    ds_temp.close()
    ds_precip.close()
    ds_sun.close()

    print(f"Wrote {OUTPUT_JSON} with {len(rows)} rows")


if __name__ == "__main__":
    main()