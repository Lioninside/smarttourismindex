#!/usr/bin/env python3
"""
06b_gtfs_reachability.py

For each of the 193 base places, compute which communes are reachable within
60 minutes of PT travel from the anchor stop.

Inputs:
  - metadata/places_master.csv
  - data_processed/gtfs/gtfs_access_metrics.json  (anchor stop per place)
  - data_raw/gtfs/gtfs_fp2025_20251211.zip

Output:
  - data_processed/gtfs/gtfs_reachability.json
    { "bellinzona": ["locarno", "biasca", ...], ... }

Algorithm:
  - Tuesday departures 08:00–10:00 (representative daytime tourist travel)
  - Forward BFS/Dijkstra from anchor stop; max elapsed time 60 min
  - Minimum transfer time 3 min
  - Cap reachable communes at 30 per base place
  - Fallback: if anchor stop has no departures in window, use 40 km haversine radius
"""

from __future__ import annotations

import csv
import io
import json
import math
import zipfile
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

PLACES_CSV   = Path("metadata/places_master.csv")
GTFS_ACCESS  = Path("data_processed/gtfs/gtfs_access_metrics.json")
GTFS_ZIP     = Path("data_raw/gtfs/gtfs_fp2025_20251211.zip")
OUTPUT_JSON  = Path("data_processed/gtfs/gtfs_reachability.json")

MAX_TRAVEL_MIN  = 60
MIN_TRANSFER_MIN = 3
MAX_REACH_COMMUNES = 30
FALLBACK_KM     = 40.0
STOP_COMMUNE_KM = 2.0
WINDOW_START    = 8 * 60   # 08:00 in minutes
WINDOW_END      = 10 * 60  # 10:00 in minutes


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_time(t: str) -> int:
    """Parse HH:MM:SS → minutes. GTFS allows hours ≥ 24 for after-midnight trips."""
    parts = t.strip().split(":")
    return int(parts[0]) * 60 + int(parts[1])


def read_places(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [
            {
                "slug": r["slug"].strip(),
                "name": r["name"].strip(),
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
            }
            for r in reader
            if str(r.get("active", "")).strip().lower() == "true"
        ]


def read_gtfs_csv(zf: zipfile.ZipFile, name: str) -> List[Dict[str, str]]:
    with zf.open(name) as f:
        text = io.TextIOWrapper(f, encoding="utf-8-sig", newline="")
        return list(csv.DictReader(text))


def load_gtfs(zip_path: Path) -> Tuple[
    Dict[str, Tuple[float, float]],  # stop_id -> (lat, lon)
    Dict[str, str],                   # stop_id -> parent_stop_id
    # stop_id -> list of (dep_min, arr_min, next_stop_id)
    Dict[str, List[Tuple[int, int, str]]],
]:
    """Load stops and daytime stop_times edges. Returns stops, parent_map, edges."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        stops_raw   = read_gtfs_csv(zf, "stops.txt")
        trips_raw   = read_gtfs_csv(zf, "trips.txt")
        calendar    = read_gtfs_csv(zf, "calendar.txt") if "calendar.txt" in zf.namelist() else []
        cal_dates   = read_gtfs_csv(zf, "calendar_dates.txt") if "calendar_dates.txt" in zf.namelist() else []
        st_raw      = read_gtfs_csv(zf, "stop_times.txt")

    # Find service_ids that operate on Tuesday
    tuesday_services: Set[str] = set()
    for row in calendar:
        if row.get("tuesday", "0") == "1":
            tuesday_services.add(row["service_id"])

    # Fall back to all services if Tuesday filtering yields nothing.
    # Swiss GTFS often uses calendar_dates.txt exclusively or has no active
    # Tuesday services in calendar.txt — time-window filter is the real constraint.
    if not tuesday_services:
        tuesday_services = {r["service_id"] for r in trips_raw if r.get("service_id")}
        print(f"  No Tuesday services in calendar.txt — using all {len(tuesday_services)} services")

    tuesday_trips: Set[str] = {
        r["trip_id"] for r in trips_raw
        if r.get("service_id") in tuesday_services and r.get("trip_id")
    }

    # Stop positions and parent map
    stop_pos: Dict[str, Tuple[float, float]] = {}
    parent_map: Dict[str, str] = {}
    for row in stops_raw:
        sid = row.get("stop_id", "").strip()
        if not sid:
            continue
        try:
            stop_pos[sid] = (float(row["stop_lat"]), float(row["stop_lon"]))
        except (KeyError, ValueError):
            continue
        parent = (row.get("parent_station") or "").strip()
        if parent:
            parent_map[sid] = parent

    # Build adjacency: stop_id -> [(dep_min, arr_min, next_stop_id)]
    # Only Tuesday trips, departures in 08:00–10:00 window
    # Group stop_times by trip, then build consecutive-stop edges
    trip_stops: Dict[str, List[Tuple[int, int, str, int]]] = defaultdict(list)
    for row in st_raw:
        trip_id = row.get("trip_id", "").strip()
        if trip_id not in tuesday_trips:
            continue
        stop_id = row.get("stop_id", "").strip()
        dep_str = (row.get("departure_time") or row.get("arrival_time") or "").strip()
        arr_str = (row.get("arrival_time") or row.get("departure_time") or "").strip()
        if not dep_str or not arr_str or not stop_id:
            continue
        try:
            dep = parse_time(dep_str)
            arr = parse_time(arr_str)
            seq = int(row.get("stop_sequence", 0))
        except (ValueError, IndexError):
            continue
        trip_stops[trip_id].append((seq, dep, arr, stop_id))

    edges: Dict[str, List[Tuple[int, int, str]]] = defaultdict(list)
    for trip_id, stops_in_trip in trip_stops.items():
        stops_in_trip.sort(key=lambda x: x[0])
        for i in range(len(stops_in_trip) - 1):
            seq_a, dep_a, _, sid_a = stops_in_trip[i]
            seq_b, _, arr_b, sid_b = stops_in_trip[i + 1]
            # Only include edges where departure is in the travel window
            if WINDOW_START <= dep_a <= WINDOW_END:
                edges[sid_a].append((dep_a, arr_b, sid_b))
                # Also index by parent station so anchor stop lookups work
                # regardless of whether anchor is child or parent stop ID
                parent_a = parent_map.get(sid_a)
                if parent_a:
                    edges[parent_a].append((dep_a, arr_b, sid_b))

    return stop_pos, parent_map, dict(edges)


def canonical_stop(stop_id: str, parent_map: Dict[str, str]) -> str:
    """Return parent stop if available, otherwise return stop itself."""
    return parent_map.get(stop_id, stop_id)


def bfs_reachability(
    start_stop: str,
    stop_pos: Dict[str, Tuple[float, float]],
    parent_map: Dict[str, str],
    edges: Dict[str, List[Tuple[int, int, str]]],
) -> Set[str]:
    """
    BFS from start_stop. Returns set of reachable stop_ids within MAX_TRAVEL_MIN.

    State: (stop_id, earliest_arrival_min)
    We track best known arrival per stop and expand only if we can improve.
    """
    # Normalise start to canonical stop
    start = canonical_stop(start_stop, parent_map)

    # best_arrival[stop_id] = earliest minute we can be at that stop
    best_arrival: Dict[str, int] = {start: WINDOW_START}
    queue: deque[Tuple[str, int]] = deque([(start, WINDOW_START)])
    reachable: Set[str] = {start}

    while queue:
        cur_stop, cur_arr = queue.popleft()

        # All child stops from cur_stop (and its parent if different)
        candidate_stops = {cur_stop}
        parent = parent_map.get(cur_stop)
        if parent:
            candidate_stops.add(parent)

        for from_stop in candidate_stops:
            for dep_min, arr_min, next_stop in edges.get(from_stop, []):
                # Must wait at least MIN_TRANSFER_MIN after arrival before boarding
                if dep_min < cur_arr + MIN_TRANSFER_MIN:
                    continue
                # Total elapsed from WINDOW_START must be ≤ MAX_TRAVEL_MIN
                elapsed = arr_min - WINDOW_START
                if elapsed > MAX_TRAVEL_MIN:
                    continue
                # Normalise to canonical
                next_canon = canonical_stop(next_stop, parent_map)
                if elapsed < (arr_min - best_arrival.get(next_canon, 99999)):
                    pass
                if next_canon not in best_arrival or arr_min < best_arrival[next_canon]:
                    best_arrival[next_canon] = arr_min
                    reachable.add(next_canon)
                    queue.append((next_canon, arr_min))

    return reachable


def stops_to_communes(
    reachable_stops: Set[str],
    stop_pos: Dict[str, Tuple[float, float]],
    places: List[Dict[str, Any]],
    exclude_slug: str,
) -> List[str]:
    """Map reachable stops → nearest commune within STOP_COMMUNE_KM. Cap at 30."""
    found: Set[str] = set()
    for stop_id in reachable_stops:
        pos = stop_pos.get(stop_id)
        if pos is None:
            continue
        slat, slon = pos
        best_dist = STOP_COMMUNE_KM + 1
        best_slug = None
        for p in places:
            if p["slug"] == exclude_slug:
                continue
            d = haversine_km(slat, slon, p["lat"], p["lon"])
            if d < best_dist:
                best_dist = d
                best_slug = p["slug"]
        if best_slug:
            found.add(best_slug)

    result = sorted(found)[:MAX_REACH_COMMUNES]
    return result


def fallback_communes(
    place: Dict[str, Any],
    places: List[Dict[str, Any]],
) -> List[str]:
    """All places within FALLBACK_KM straight-line, capped at MAX_REACH_COMMUNES."""
    nearby = []
    for p in places:
        if p["slug"] == place["slug"]:
            continue
        d = haversine_km(place["lat"], place["lon"], p["lat"], p["lon"])
        if d <= FALLBACK_KM:
            nearby.append((d, p["slug"]))
    nearby.sort()
    return [s for _, s in nearby[:MAX_REACH_COMMUNES]]


def main() -> None:
    for p in [PLACES_CSV, GTFS_ACCESS, GTFS_ZIP]:
        if not p.exists():
            raise FileNotFoundError(f"Missing: {p}")

    places = read_places(PLACES_CSV)

    with GTFS_ACCESS.open("r", encoding="utf-8") as f:
        access_rows = json.load(f)
    anchor_stop: Dict[str, str] = {r["slug"]: r["anchor_stop_id"] for r in access_rows if r.get("anchor_stop_id")}

    print("Loading GTFS stop_times (this may take a moment)...")
    stop_pos, parent_map, edges = load_gtfs(GTFS_ZIP)
    print(f"  Stops: {len(stop_pos)}, edges from {len(edges)} stops")

    result: Dict[str, List[str]] = {}

    # ── DIAGNOSTIC: print info for first place to diagnose fallback root cause ──
    first = places[0]
    _slug = first["slug"]
    _anchor = anchor_stop.get(_slug)
    _canon = canonical_stop(_anchor, parent_map) if _anchor else None
    print(f"  DIAG {_slug}: anchor_id={_anchor!r}  canonical={_canon!r}")
    print(f"  DIAG   anchor in stop_pos: {_anchor in stop_pos if _anchor else 'n/a'}")
    print(f"  DIAG   canon  in stop_pos: {_canon  in stop_pos if _canon  else 'n/a'}")
    print(f"  DIAG   canon  in edges:    {_canon  in edges    if _canon  else 'n/a'}  (len={len(edges.get(_canon, []))})")
    _sample_parent_keys = [k for k in list(edges.keys())[:5000] if 'arent' in k or 'ARENT' in k][:5]
    print(f"  DIAG   sample 'Parent*' keys in edges: {_sample_parent_keys}")
    _sample_stop_keys = list(edges.keys())[:5]
    print(f"  DIAG   sample edge keys: {_sample_stop_keys}")
    # ── END DIAGNOSTIC ──────────────────────────────────────────────────────────

    for place in places:
        slug = place["slug"]
        start_stop = anchor_stop.get(slug)

        if start_stop and edges.get(canonical_stop(start_stop, parent_map)):
            reachable_stops = bfs_reachability(start_stop, stop_pos, parent_map, edges)
            communes = stops_to_communes(reachable_stops, stop_pos, places, slug)
            if not communes:
                communes = fallback_communes(place, places)
            mode = "gtfs"
        else:
            communes = fallback_communes(place, places)
            mode = "fallback"

        result[slug] = communes
        print(f"  {slug}: {len(communes)} reachable communes ({mode})")

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nWrote {OUTPUT_JSON} for {len(result)} places")


if __name__ == "__main__":
    main()
