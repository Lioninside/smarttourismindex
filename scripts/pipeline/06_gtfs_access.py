#!/usr/bin/env python3
"""
06_gtfs_access.py

Reads the Swiss GTFS feed and exports lightweight place-level public transport
base metrics for MVP use.

MVP scope:
- find nearest GTFS stop/station to each place
- prefer station-like stops where possible
- count nearby stops within 1 km
- count unique routes serving the anchor stop
- output a simple PT base-strength proxy

Inputs:
  - places_master.csv
  - data_raw/gtfs/gtfs_fp2025_20251211.zip

Output:
  - data_processed/gtfs/gtfs_access_metrics.json
"""

from __future__ import annotations

import csv
import io
import json
import math
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

PLACES_CSV = Path("metadata/places_master.csv")
GTFS_ZIP = Path("data_raw/gtfs/gtfs_fp2025_20251211.zip")
OUTPUT_JSON = Path("data_processed/gtfs/gtfs_access_metrics.json")

NEARBY_STOP_RADIUS_KM = 1.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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


def read_gtfs_csv(zf: zipfile.ZipFile, name: str) -> List[Dict[str, str]]:
    with zf.open(name) as f:
        text = io.TextIOWrapper(f, encoding="utf-8-sig", newline="")
        return list(csv.DictReader(text))


def load_gtfs(zip_path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, set], Dict[str, str]]:
    with zipfile.ZipFile(zip_path, "r") as zf:
        stops_raw = read_gtfs_csv(zf, "stops.txt")
        stop_times = read_gtfs_csv(zf, "stop_times.txt")
        trips = read_gtfs_csv(zf, "trips.txt")

    trip_to_route = {row["trip_id"]: row["route_id"] for row in trips if row.get("trip_id") and row.get("route_id")}

    stop_routes: Dict[str, set] = defaultdict(set)
    for row in stop_times:
        stop_id = row.get("stop_id")
        trip_id = row.get("trip_id")
        if not stop_id or not trip_id:
            continue
        route_id = trip_to_route.get(trip_id)
        if route_id:
            stop_routes[stop_id].add(route_id)

    parent_map: Dict[str, str] = {}
    stops: List[Dict[str, Any]] = []
    for row in stops_raw:
        stop_id = row.get("stop_id", "").strip()
        if not stop_id:
            continue
        parent_station = (row.get("parent_station") or "").strip()
        if parent_station:
            parent_map[stop_id] = parent_station

        try:
            lat = float(row["stop_lat"])
            lon = float(row["stop_lon"])
        except Exception:
            continue

        stops.append(
            {
                "stop_id": stop_id,
                "stop_name": (row.get("stop_name") or "").strip(),
                "stop_lat": lat,
                "stop_lon": lon,
                "location_type": (row.get("location_type") or "").strip(),
                "parent_station": parent_station,
            }
        )

    return stops, stop_routes, parent_map


def is_station_like(stop: Dict[str, Any]) -> bool:
    return stop.get("location_type") == "1"


def choose_anchor_stop(place: Dict[str, Any], stops: List[Dict[str, Any]]) -> Dict[str, Any]:
    ranked = []
    for stop in stops:
        dist = haversine_km(place["lat"], place["lon"], stop["stop_lat"], stop["stop_lon"])
        station_bonus = 0 if is_station_like(stop) else 1
        ranked.append((station_bonus, dist, stop))
    ranked.sort(key=lambda x: (x[0], x[1]))
    return ranked[0][2]


def route_count_for_anchor(anchor_stop: Dict[str, Any], stop_routes: Dict[str, set], parent_map: Dict[str, str]) -> int:
    stop_id = anchor_stop["stop_id"]
    parent = parent_map.get(stop_id) or anchor_stop.get("parent_station") or ""

    routes = set()
    routes.update(stop_routes.get(stop_id, set()))
    if parent:
        routes.update(stop_routes.get(parent, set()))
    return len(routes)


def nearby_stop_count(place: Dict[str, Any], stops: List[Dict[str, Any]], radius_km: float = NEARBY_STOP_RADIUS_KM) -> int:
    count = 0
    for stop in stops:
        dist = haversine_km(place["lat"], place["lon"], stop["stop_lat"], stop["stop_lon"])
        if dist <= radius_km:
            count += 1
    return count


def pt_strength_label(route_count: int, nearby_stops: int, anchor_dist_km: float) -> str:
    score = 0
    if route_count >= 20:
        score += 2
    elif route_count >= 8:
        score += 1

    if nearby_stops >= 25:
        score += 2
    elif nearby_stops >= 8:
        score += 1

    if anchor_dist_km <= 0.5:
        score += 1

    if score >= 4:
        return "strong"
    if score >= 2:
        return "good"
    return "basic"


def main() -> None:
    if not PLACES_CSV.exists():
        raise FileNotFoundError(f"Missing places file: {PLACES_CSV}")
    if not GTFS_ZIP.exists():
        raise FileNotFoundError(f"Missing GTFS zip: {GTFS_ZIP}")

    places = read_places(PLACES_CSV)
    stops, stop_routes, parent_map = load_gtfs(GTFS_ZIP)

    rows: List[Dict[str, Any]] = []
    for place in places:
        anchor = choose_anchor_stop(place, stops)
        anchor_dist_km = round(haversine_km(place["lat"], place["lon"], anchor["stop_lat"], anchor["stop_lon"]), 3)
        nearby_stops = nearby_stop_count(place, stops)
        anchor_route_count = route_count_for_anchor(anchor, stop_routes, parent_map)

        rows.append(
            {
                "slug": place["slug"],
                "name": place["name"],
                "anchor_stop_name": anchor["stop_name"],
                "anchor_stop_id": anchor["stop_id"],
                "anchor_stop_distance_km": anchor_dist_km,
                "nearby_stop_count_1km": nearby_stops,
                "anchor_route_count": anchor_route_count,
                "pt_strength_label": pt_strength_label(anchor_route_count, nearby_stops, anchor_dist_km),
            }
        )

    rows.sort(key=lambda x: x["slug"])

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(rows)} rows")


if __name__ == "__main__":
    main()
