import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

SEARCH_CH_ROUTE_URL = "https://search.ch/timetable/api/route.json"

DEFAULT_PREFILTER_KM = 100
DEFAULT_THRESHOLD_SECONDS = 3600
DEFAULT_CHUNK_SIZE = 80
DEFAULT_PAUSE_SECONDS = 2.0
DEFAULT_TIMEOUT = 45
DEFAULT_MAX_RETRIES = 5


def parse_args():
    p = argparse.ArgumentParser(description="Build reachability JSON with 100km prefilter + API verification")
    p.add_argument("--input", default="places_master.csv")
    p.add_argument("--output", default="reachable_within_60m.json")
    p.add_argument("--prefilter-km", type=float, default=DEFAULT_PREFILTER_KM)
    p.add_argument("--threshold-seconds", type=int, default=DEFAULT_THRESHOLD_SECONDS)
    p.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    p.add_argument("--pause-seconds", type=float, default=DEFAULT_PAUSE_SECONDS)
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    p.add_argument("--date", default=None, help="Optional MM/DD/YYYY")
    p.add_argument("--time", dest="time_of_day", default=None, help="Optional HH:MM")
    p.add_argument("--interest-duration", type=int, default=1440)
    p.add_argument("--transportation-types", default=None)
    p.add_argument("--only-active", action="store_true")
    p.add_argument("--self-include", action="store_true")
    return p.parse_args()


def norm(x: Any) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()


def truthy(x: Any) -> bool:
    return norm(x).lower() in {"1", "true", "yes", "y"}


def slugify(text: str) -> str:
    text = norm(text).lower()
    repl = {
        "ä": "ae", "ö": "oe", "ü": "ue",
        "é": "e", "è": "e", "ê": "e",
        "à": "a", "á": "a", "â": "a",
        "î": "i", "ï": "i",
        "ô": "o", "û": "u",
        "ç": "c",
        "'": "", "’": "",
    }
    for k, v in repl.items():
        text = text.replace(k, v)

    out = []
    prev_dash = False
    for ch in text:
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        else:
            if not prev_dash:
                out.append("-")
                prev_dash = True
    return "".join(out).strip("-")


def load_places(path: str, only_active: bool) -> pd.DataFrame:
    df = None
    for enc in ["utf-8", "cp1252", "latin1"]:
        for sep in [";", ",", "\t"]:
            try:
                tmp = pd.read_csv(path, encoding=enc, sep=sep)
                if "name" in tmp.columns:
                    df = tmp
                    print(f"Loaded with encoding={enc}, sep={repr(sep)}")
                    break
            except Exception:
                pass
        if df is not None:
            break

    if df is None:
        raise ValueError(f"Could not read input file: {path}")

    required = {"name", "main_station_name", "lat", "lon"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df = df.copy()
    df["name"] = df["name"].map(norm)
    df["main_station_name"] = df["main_station_name"].map(norm)

    if "slug" not in df.columns:
        df["slug"] = df["name"].map(slugify)
    else:
        df["slug"] = df["slug"].map(norm)
        df.loc[df["slug"] == "", "slug"] = df.loc[df["slug"] == "", "name"].map(slugify)

    if "station_id" not in df.columns:
        df["station_id"] = ""
    else:
        df["station_id"] = df["station_id"].map(norm)

    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    if only_active and "active" in df.columns:
        df = df[df["active"].map(truthy)].copy()

    df = df.dropna(subset=["lat", "lon"]).reset_index(drop=True)

    if df["slug"].duplicated().any():
        dupes = df[df["slug"].duplicated(keep=False)][["name", "slug"]]
        raise ValueError("Duplicate slugs found:\n" + dupes.to_string(index=False))

    return df


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def make_query_key(row: dict[str, Any]) -> str:
    return row["station_id"] if norm(row.get("station_id", "")) else row["main_station_name"]


def chunked(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def request_json(session, url, params, timeout, max_retries, pause_seconds):
    last_error = ""
    for attempt in range(1, max_retries + 1):
        try:
            r = session.get(url, params=params, timeout=timeout)
            if r.status_code == 429:
                wait_s = max(5, attempt * 5)
                print(f"HTTP_429 -> sleeping {wait_s}s", file=sys.stderr)
                time.sleep(wait_s)
                last_error = "HTTP_429"
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                wait_s = max(3, attempt * pause_seconds * 2)
                print(f"Retry {attempt}/{max_retries}: {e}", file=sys.stderr)
                time.sleep(wait_s)
            else:
                break
    raise RuntimeError(f"Request failed after {max_retries} attempts: {last_error}")


def build_route_params(origin_key, destinations, date, time_of_day, interest_duration, transportation_types):
    params = {
        "from": origin_key,
        "one_to_many": 1,
        "time_type": "depart",
        "interest_duration": interest_duration,
    }
    if date:
        params["date"] = date
    if time_of_day:
        params["time"] = time_of_day
    if transportation_types:
        params["transportation_types"] = transportation_types

    for i, dest in enumerate(destinations):
        params[f"to[{i}]"] = dest["query_key"]
    return params


def fetch_batch_durations(
    session,
    origin,
    batch,
    timeout,
    max_retries,
    pause_seconds,
    date,
    time_of_day,
    interest_duration,
    transportation_types,
):
    params = build_route_params(
        origin["query_key"],
        batch,
        date,
        time_of_day,
        interest_duration,
        transportation_types,
    )
    data = request_json(session, SEARCH_CH_ROUTE_URL, params, timeout, max_retries, pause_seconds)
    results = data.get("results") or []

    durations = {dest["slug"]: None for dest in batch}

    if len(results) == len(batch):
        for result, dest in zip(results, batch):
            md = result.get("min_duration")
            if md is not None:
                durations[dest["slug"]] = int(md)
        return durations

    # fallback by order if mismatch not perfect but enough to inspect
    for i, result in enumerate(results[:len(batch)]):
        md = result.get("min_duration")
        if md is not None:
            durations[batch[i]["slug"]] = int(md)

    return durations


def build_reachability(args):
    df = load_places(args.input, args.only_active)
    records = df.to_dict("records")

    for row in records:
        row["query_key"] = make_query_key(row)

    result = {}
    total_api_batches = 0
    total_prefilter_pairs = 0

    # pre-calc candidate counts
    for origin in records:
        candidates = []
        for dest in records:
            if not args.self_include and origin["slug"] == dest["slug"]:
                continue
            dist = haversine_km(origin["lat"], origin["lon"], dest["lat"], dest["lon"])
            if dist <= args.prefilter_km:
                candidates.append(dest)
        total_prefilter_pairs += len(candidates)
        total_api_batches += math.ceil(len(candidates) / args.chunk_size) if candidates else 0

    print(f"Rows loaded: {len(records)}")
    print(f"Prefilter radius: {args.prefilter_km} km")
    print(f"Candidate OD pairs after prefilter: {total_prefilter_pairs}")
    print(f"Estimated API batches: {total_api_batches}")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "pt-reachability-prefilter/1.0",
        "Accept": "application/json",
    })

    batch_counter = 0

    for origin in records:
        origin_slug = origin["slug"]
        candidates = []

        for dest in records:
            if not args.self_include and origin["slug"] == dest["slug"]:
                continue
            dist = haversine_km(origin["lat"], origin["lon"], dest["lat"], dest["lon"])
            if dist <= args.prefilter_km:
                candidate = dict(dest)
                candidate["distance_km"] = dist
                candidates.append(candidate)

        reachable = set()
        if args.self_include:
            reachable.add(origin_slug)

        print(f"\nOrigin {origin_slug}: {len(candidates)} candidates within {args.prefilter_km} km")

        for batch in chunked(candidates, args.chunk_size):
            batch_counter += 1
            print(f"[{batch_counter}/{total_api_batches}] {origin_slug} -> {len(batch)} destinations")
            durations = fetch_batch_durations(
                session=session,
                origin=origin,
                batch=batch,
                timeout=args.timeout,
                max_retries=args.max_retries,
                pause_seconds=args.pause_seconds,
                date=args.date,
                time_of_day=args.time_of_day,
                interest_duration=args.interest_duration,
                transportation_types=args.transportation_types,
            )

            for dest_slug, seconds in durations.items():
                if seconds is not None and seconds <= args.threshold_seconds:
                    reachable.add(dest_slug)

            time.sleep(args.pause_seconds)

        result[origin_slug] = sorted(reachable)

    return result


def main():
    args = parse_args()
    result = build_reachability(args)

    output_path = Path(args.output)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nSaved:")
    print(f" - {output_path}")


if __name__ == "__main__":
    main()