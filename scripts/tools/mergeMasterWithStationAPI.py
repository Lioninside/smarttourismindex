import pandas as pd
import requests
import time
from pathlib import Path

MASTER_FILE = "places_master.csv"
REVIEW_FILE = "doublecheck_full.csv"
OUTPUT_FILE = "places_master_merged.csv"
OUTPUT_ISSUES_FILE = "places_master_merge_issues.csv"

SEARCH_CH_STATION_URL = "https://search.ch/timetable/api/station.json"

PAUSE_SECONDS = 1.5
TIMEOUT = 30
MAX_RETRIES = 5
USER_AGENT = "places-master-merge/1.0"


def load_csv(path: str) -> pd.DataFrame:
    for enc in ["utf-8", "cp1252", "latin1"]:
        for sep in [",", ";", "\t"]:
            try:
                df = pd.read_csv(path, encoding=enc, sep=sep)
                if "name" in df.columns:
                    print(f"Loaded {path} with encoding={enc}, sep={repr(sep)}")
                    return df
            except Exception:
                pass
    raise ValueError(f"Could not read file: {path}")


def norm(x) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()


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
    if not Path(MASTER_FILE).exists():
        raise FileNotFoundError(f"Missing file: {MASTER_FILE}")
    if not Path(REVIEW_FILE).exists():
        raise FileNotFoundError(f"Missing file: {REVIEW_FILE}")

    master = load_csv(MASTER_FILE).copy()
    review = load_csv(REVIEW_FILE).copy()

    required_master = {"name", "main_station_name"}
    required_review = {"name", "api_resolved_name"}

    missing_master = required_master - set(master.columns)
    missing_review = required_review - set(review.columns)

    if missing_master:
        raise ValueError(f"Master missing columns: {sorted(missing_master)}")
    if missing_review:
        raise ValueError(f"Review file missing columns: {sorted(missing_review)}")

    master["name"] = master["name"].map(norm)
    master["main_station_name"] = master["main_station_name"].map(norm)

    review["name"] = review["name"].map(norm)
    review["api_resolved_name"] = review["api_resolved_name"].map(norm)

    if "api_resolved_id" in review.columns:
        review["api_resolved_id"] = review["api_resolved_id"].map(norm)
    else:
        review["api_resolved_id"] = ""

    # keep one row per place
    review = review.drop_duplicates(subset=["name"], keep="first").copy()

    # merge approved station into master
    review_merge = review[["name", "api_resolved_name", "api_resolved_id"]].rename(
        columns={
            "api_resolved_name": "main_station_name_reviewed",
            "api_resolved_id": "station_id_reviewed",
        }
    )

    merged = master.copy()

    if "main_station_name_original" not in merged.columns:
        merged["main_station_name_original"] = merged["main_station_name"]

    merged = merged.merge(
        review_merge,
        on="name",
        how="left",
        validate="one_to_one",
    )

    # overwrite only where reviewed value exists
    merged["main_station_name"] = merged["main_station_name_reviewed"].where(
        merged["main_station_name_reviewed"].map(norm) != "",
        merged["main_station_name"],
    )

    # initial station_id from reviewed file if available
    merged["station_id"] = merged["station_id_reviewed"].map(norm)

    merged = merged.drop(columns=["main_station_name_reviewed", "station_id_reviewed"])

    # final API validation of the merged main_station_name
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
    )

    validated_names = []
    validated_ids = []
    validated_status = []

    print("\n=== VALIDATING FINAL main_station_name ===")
    total = len(merged)

    for i, row in merged.iterrows():
        place = row["name"]
        station = row["main_station_name"]

        api_name, api_id, api_status = request_station(session, station)

        validated_names.append(api_name)
        validated_ids.append(api_id)
        validated_status.append(api_status)

        print(f"[{i+1}/{total}] {place} | {station} -> {api_name} ({api_id}) | {api_status}")
        time.sleep(PAUSE_SECONDS)

    merged["station_api_name"] = validated_names
    merged["station_api_id"] = validated_ids
    merged["station_api_status"] = validated_status

    # prefer fresh validated station id
    merged["station_id"] = merged["station_api_id"].where(
        merged["station_api_id"].map(norm) != "",
        merged["station_id"],
    )

    # identify issues
    issues = merged[
        (merged["station_api_status"] != "OK") |
        (merged["main_station_name"].map(norm).str.lower() != merged["station_api_name"].map(norm).str.lower())
    ].copy()

    print("\n=== SUMMARY ===")
    print(f"Master rows: {len(master)}")
    print(f"Merged rows: {len(merged)}")
    print(f"Unique names: {merged['name'].nunique()}")
    print("\nstation_api_status counts:")
    print(merged["station_api_status"].value_counts(dropna=False).to_string())
    print(f"\nIssue rows: {len(issues)}")

    merged.to_csv(OUTPUT_FILE, index=False)
    issues.to_csv(OUTPUT_ISSUES_FILE, index=False)

    print("\nSaved:")
    print(f" - {OUTPUT_FILE}")
    print(f" - {OUTPUT_ISSUES_FILE}")


if __name__ == "__main__":
    main()