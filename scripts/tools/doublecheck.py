import pandas as pd
import requests
import time
import re
from pathlib import Path

INPUT_FILE = "ManuallyReviewed_manualReviewDone.CSV"
OUTPUT_FULL = "doublecheck_full.csv"
OUTPUT_FLAGGED = "doublecheck_flagged.csv"

SEARCH_CH_STATION_URL = "https://search.ch/timetable/api/station.json"

PAUSE_SECONDS = 2.0
TIMEOUT = 30
USER_AGENT = "doublecheck-validator/4.0"
MAX_RETRIES = 5


def load_file(path: str) -> pd.DataFrame:
    for enc in ["utf-8", "cp1252", "latin1"]:
        for sep in [",", ";", "\t"]:
            try:
                df = pd.read_csv(path, encoding=enc, sep=sep)
                cols = {c.strip().lower(): c for c in df.columns}
                needed = {"name", "main_station_name", "api_resolved_name"}
                if needed.issubset(set(cols.keys())):
                    df = df.rename(columns={
                        cols["name"]: "name",
                        cols["main_station_name"]: "main_station_name",
                        cols["api_resolved_name"]: "api_resolved_name",
                        **({cols["api_resolved_id"]: "api_resolved_id"} if "api_resolved_id" in cols else {}),
                        **({cols["api_status"]: "api_status"} if "api_status" in cols else {}),
                        **({cols["api_flag"]: "api_flag"} if "api_flag" in cols else {}),
                    })
                    print(f"Loaded with encoding={enc}, sep={repr(sep)}")
                    return df
            except Exception:
                pass
    raise ValueError("Could not read input file with common encodings/separators.")


def norm(x) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-zÀ-ÿ0-9]+", text.lower()))


def classify_station(place: str, station: str) -> str:
    s = norm(station).lower()
    p = norm(place).lower()
    flags = []

    bad_keywords = {
        "talstation": "BAD_talstation",
        "bergbahn": "BAD_bergbahn",
        "gondel": "BAD_gondola",
        "luftseil": "BAD_cablecar",
        "funi": "BAD_funicular",
        "funicolare": "BAD_funicular",
        "heimwehfluh": "BAD_tourist_stop",
        "hannig": "BAD_tourist_stop",
        "hohsaas": "BAD_tourist_stop",
        "pendicularas": "BAD_tourist_stop",
        "schiff": "BAD_boat_stop",
        "lago": "BAD_lake_stop",
        "station aval": "BAD_lower_station",
    }

    weak_keywords = {
        "post": "WEAK_post_stop",
        "dorf": "WEAK_village_stop",
        "platz": "WEAK_local_stop",
        "zentrum": "WEAK_local_stop",
        "gemeindehaus": "WEAK_local_stop",
        "hotel de ville": "WEAK_local_stop",
        "schule": "WEAK_school_stop",
        "scoula": "WEAK_school_stop",
        "kirchbühl": "WEAK_local_stop",
        "zum wilden mann": "WEAK_local_stop",
        "unterwilen": "WEAK_local_stop",
        "sonnenhof": "WEAK_local_stop",
        "telmoos": "WEAK_local_stop",
        "endorf": "WEAK_local_stop",
        "stein": "WEAK_local_stop",
        "fellital": "WEAK_local_stop",
        "kraftwerk": "WEAK_industrial_stop",
        "am lauener": "WEAK_local_stop",
        "eichbergerstr": "WEAK_local_stop",
        "klosterstrasse": "WEAK_local_stop",
        "blandonnet": "WEAK_local_stop",
        "emmenfeld": "WEAK_local_stop",
        "al parco": "WEAK_local_stop",
        "zorten": "WEAK_local_stop",
        "abzw": "WEAK_junction_stop",
    }

    for k, label in bad_keywords.items():
        if k in s:
            flags.append(label)

    for k, label in weak_keywords.items():
        if k in s:
            flags.append(label)

    place_tokens = tokens(p)
    station_tokens = tokens(s)
    if s and place_tokens and not (place_tokens & station_tokens):
        flags.append("CHECK_name_mismatch")

    if not s or s == "none":
        flags.append("NOT_FOUND")

    seen = set()
    out = []
    for f in flags:
        if f not in seen:
            out.append(f)
            seen.add(f)
    return "; ".join(out)


def request_station(session: requests.Session, stop_name: str) -> tuple[str, str, str]:
    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(
                SEARCH_CH_STATION_URL,
                params={"stop": stop_name},
                timeout=TIMEOUT,
            )

            if r.status_code == 429:
                wait_s = max(5, attempt * 5)
                print(f"HTTP_429 for '{stop_name}' -> sleeping {wait_s}s")
                time.sleep(wait_s)
                last_error = "HTTP_429"
                continue

            r.raise_for_status()
            data = r.json()

            resolved_name = norm(data.get("name"))
            resolved_id = norm(data.get("id"))

            if resolved_name or resolved_id:
                return resolved_name, resolved_id, "OK"

            return "", "", "NOT_FOUND"

        except Exception as e:
            last_error = str(e)
            if attempt < MAX_RETRIES:
                wait_s = max(3, attempt * 3)
                print(f"Retry {attempt}/{MAX_RETRIES} for '{stop_name}' after error: {e}")
                time.sleep(wait_s)
            else:
                break

    return "", "", f"ERROR: {last_error}"


def main() -> None:
    if not Path(INPUT_FILE).exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    df = load_file(INPUT_FILE).copy()

    df["name"] = df["name"].map(norm)
    df["main_station_name"] = df["main_station_name"].map(norm)
    df["api_resolved_name"] = df["api_resolved_name"].map(norm)

    # Drop old result columns, we recalculate them fresh
    for col in ["api_resolved_id", "api_status", "api_flag"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    print("\n=== BASIC CHECK ===")
    print(f"Rows: {len(df)}")
    print(f"Unique locations: {df['name'].nunique()}")

    empty_target = df[df["api_resolved_name"] == ""]
    print("\n=== EMPTY api_resolved_name ===")
    print(f"Count: {len(empty_target)}")
    if not empty_target.empty:
        print(empty_target[["name", "main_station_name"]].to_string(index=False))

    duplicates = df[df.duplicated("name", keep=False)].sort_values("name")
    print("\n=== DUPLICATE name ===")
    print(f"Count: {len(duplicates)}")
    if not duplicates.empty:
        print(duplicates[["name", "api_resolved_name"]].to_string(index=False))

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })

    results = []
    total = len(df)

    print("\n=== API DOUBLE CHECK ON api_resolved_name ===")
    for i, row in df.iterrows():
        name = row["name"]
        checked_station = row["api_resolved_name"]

        api_name, api_id, api_status = request_station(session, checked_station)

        flags = []

        if api_status != "OK":
            flags.append(api_status)

        if checked_station and api_name and checked_station.lower() != api_name.lower():
            flags.append("API_resolved_differs")

        if checked_station:
            heuristic_flags = classify_station(name, checked_station)
            if heuristic_flags:
                flags.append(heuristic_flags)

        if api_name:
            pt = tokens(name)
            rt = tokens(api_name)
            if pt and not (pt & rt):
                flags.append("API_name_mismatch")

        seen = set()
        deduped = []
        for f in flags:
            if f and f not in seen:
                deduped.append(f)
                seen.add(f)

        results.append({
            "name": name,
            "api_resolved_name": checked_station,
            "api_resolved_id": api_id,
            "api_status": api_status,
            "api_flag": "; ".join(deduped),
        })

        print(f"[{i+1}/{total}] {name} | {checked_station} -> {api_name} ({api_id}) | {api_status}")
        time.sleep(PAUSE_SECONDS)

    res_df = pd.DataFrame(results)

    merged = df.merge(
        res_df,
        on=["name", "api_resolved_name"],
        how="left",
        validate="one_to_one",
    )

    def final_status(row) -> str:
        api_status = norm(row.get("api_status", ""))
        api_flag = norm(row.get("api_flag", ""))
        if api_status.startswith("ERROR") or api_status == "NOT_FOUND":
            return "NOT_OK"
        if api_flag:
            return "REVIEW"
        return "OK"

    merged["final_status"] = merged.apply(final_status, axis=1)

    flagged = merged[merged["final_status"] != "OK"].copy()

    merged.to_csv(OUTPUT_FULL, index=False)
    flagged.to_csv(OUTPUT_FLAGGED, index=False)

    print("\n=== SUMMARY ===")
    print(merged["final_status"].value_counts(dropna=False).to_string())

    print("\nSaved:")
    print(f" - {OUTPUT_FULL}")
    print(f" - {OUTPUT_FLAGGED}")


if __name__ == "__main__":
    main()