import csv
import json
import math
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# ============================================================
# Configuration
# ============================================================
PLACES_MASTER_PATH = Path(r"C:\Users\stc-cbartlome\OneDrive - STC Switzerland Travel Centre AG\12_Development\SmartTourismIndex\metadata\places_master.csv")
RADIUS_KM = 10.0
REQUEST_DELAY_SECONDS = 1.1  # polite delay for Nominatim
USER_AGENT = "STC-SmartTourismIndex-TopActivitiesRange/1.0 (contact: reservation@stc.ch)"

# Save outputs next to this script by default
SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_PATH = SCRIPT_DIR / "top_activities_geocache.json"
OUTPUT_ALL_PATH = SCRIPT_DIR / "top_activities_range_report.csv"
OUTPUT_NOT_COVERED_PATH = SCRIPT_DIR / "top_activities_not_within_10km.csv"
OUTPUT_SUMMARY_PATH = SCRIPT_DIR / "top_activities_range_summary.json"

# ============================================================
# Curated source lists
# Source rationale:
# - mountain excursions: Switzerland Tourism mountain railways / mountains pages
# - museums: Switzerland Tourism top museums page
# - other activities: Switzerland Tourism top attractions page + major fixed attractions
# ============================================================
TOP_MOUNTAIN_EXCURSIONS: List[Dict[str, str]] = [
    {"name": "Glacier 3000", "query": "Glacier 3000, Les Diablerets, Switzerland", "category": "mountain_excursion"},
    {"name": "Gornergrat", "query": "Gornergrat, Zermatt, Switzerland", "category": "mountain_excursion"},
    {"name": "Jungfraujoch", "query": "Jungfraujoch, Switzerland", "category": "mountain_excursion"},
    {"name": "Mount Rigi", "query": "Rigi Kulm, Switzerland", "category": "mountain_excursion"},
    {"name": "Brienz Rothorn", "query": "Brienz Rothorn, Brienz, Switzerland", "category": "mountain_excursion"},
    {"name": "CabriO Stanserhorn", "query": "Stanserhorn, Stans, Switzerland", "category": "mountain_excursion"},
    {"name": "Grindelwald-First", "query": "First Cliff Walk, Grindelwald, Switzerland", "category": "mountain_excursion"},
    {"name": "Harder Kulm", "query": "Harder Kulm, Interlaken, Switzerland", "category": "mountain_excursion"},
    {"name": "Matterhorn Glacier Paradise", "query": "Matterhorn Glacier Paradise, Zermatt, Switzerland", "category": "mountain_excursion"},
    {"name": "Pilatus", "query": "Pilatus Kulm, Switzerland", "category": "mountain_excursion"},
    {"name": "Moléson", "query": "Moléson-sur-Gruyères, Switzerland", "category": "mountain_excursion"},
    {"name": "Rochers-de-Naye", "query": "Rochers-de-Naye, Montreux, Switzerland", "category": "mountain_excursion"},
    {"name": "Säntis", "query": "Säntis, Schwägalp, Switzerland", "category": "mountain_excursion"},
    {"name": "Stoos", "query": "Stoos, Schwyz, Switzerland", "category": "mountain_excursion"},
    {"name": "Titlis", "query": "Titlis, Engelberg, Switzerland", "category": "mountain_excursion"},
    {"name": "Niesen", "query": "Niesen Kulm, Mülenen, Switzerland", "category": "mountain_excursion"},
    {"name": "Cardada-Cimetta", "query": "Cardada Cimetta, Orselina, Switzerland", "category": "mountain_excursion"},
    {"name": "Schilthorn - Piz Gloria", "query": "Schilthorn Piz Gloria, Mürren, Switzerland", "category": "mountain_excursion"},
    {"name": "Schynige Platte", "query": "Schynige Platte, Wilderswil, Switzerland", "category": "mountain_excursion"},
    {"name": "Parsenn", "query": "Weissfluhjoch, Davos, Switzerland", "category": "mountain_excursion"},
    {"name": "Corvatsch", "query": "Corvatsch, Silvaplana, Switzerland", "category": "mountain_excursion"},
    {"name": "Muottas Muragl", "query": "Muottas Muragl, Samedan, Switzerland", "category": "mountain_excursion"},
    {"name": "Eggishorn", "query": "Eggishorn, Fiesch, Switzerland", "category": "mountain_excursion"},
    {"name": "Bettmerhorn", "query": "Bettmerhorn, Bettmeralp, Switzerland", "category": "mountain_excursion"},
    {"name": "Diavolezza", "query": "Diavolezza, Pontresina, Switzerland", "category": "mountain_excursion"},
    {"name": "Monte Generoso", "query": "Monte Generoso, Capolago, Switzerland", "category": "mountain_excursion"},
    {"name": "Monte Tamaro", "query": "Monte Tamaro, Rivera, Switzerland", "category": "mountain_excursion"},
    {"name": "Kronberg", "query": "Kronberg, Jakobsbad, Switzerland", "category": "mountain_excursion"},
    {"name": "Pizol", "query": "Pizol, Bad Ragaz, Switzerland", "category": "mountain_excursion"},
    {"name": "Stockhorn", "query": "Stockhorn, Erlenbach im Simmental, Switzerland", "category": "mountain_excursion"},
]

TOP_MUSEUMS: List[Dict[str, str]] = [
    {"name": "Fotostiftung Schweiz", "query": "Fotostiftung Schweiz, Winterthur, Switzerland", "category": "museum"},
    {"name": "Museum Tinguely", "query": "Museum Tinguely, Basel, Switzerland", "category": "museum"},
    {"name": "Kunsthaus Zürich", "query": "Kunsthaus Zurich, Switzerland", "category": "museum"},
    {"name": "MAMCO", "query": "MAMCO Geneva, Switzerland", "category": "museum"},
    {"name": "Museum für Gestaltung Zürich, Toni-Areal", "query": "Museum für Gestaltung Toni-Areal, Zurich, Switzerland", "category": "museum"},
    {"name": "Zentrum Paul Klee", "query": "Zentrum Paul Klee, Bern, Switzerland", "category": "museum"},
    {"name": "Museum Rietberg", "query": "Museum Rietberg, Zurich, Switzerland", "category": "museum"},
    {"name": "Kunstmuseum Basel", "query": "Kunstmuseum Basel, Switzerland", "category": "museum"},
    {"name": "Plateforme 10", "query": "Plateforme 10, Lausanne, Switzerland", "category": "museum"},
    {"name": "Fondation Beyeler", "query": "Fondation Beyeler, Riehen, Switzerland", "category": "museum"},
    {"name": "MASI Lugano", "query": "MASI Lugano LAC, Lugano, Switzerland", "category": "museum"},
    {"name": "Fortress of Bellinzona", "query": "Castelgrande, Bellinzona, Switzerland", "category": "museum"},
    {"name": "Alimentarium", "query": "Alimentarium, Vevey, Switzerland", "category": "museum"},
    {"name": "Maison Cailler", "query": "Maison Cailler, Broc, Switzerland", "category": "museum"},
    {"name": "Museum für Kommunikation", "query": "Museum für Kommunikation, Bern, Switzerland", "category": "museum"},
    {"name": "Lindt Home of Chocolate", "query": "Lindt Home of Chocolate, Kilchberg, Switzerland", "category": "museum"},
    {"name": "Fondation Pierre Gianadda", "query": "Fondation Pierre Gianadda, Martigny, Switzerland", "category": "museum"},
    {"name": "National Museum Zurich", "query": "Landesmuseum Zurich, Switzerland", "category": "museum"},
    {"name": "Bourbaki Panorama Lucerne", "query": "Bourbaki Panorama, Lucerne, Switzerland", "category": "museum"},
    {"name": "Kunstmuseum Bern", "query": "Kunstmuseum Bern, Switzerland", "category": "museum"},
]

TOP_OTHER_ACTIVITIES: List[Dict[str, str]] = [
    {"name": "Rhine Falls", "query": "Rhine Falls, Neuhausen am Rheinfall, Switzerland", "category": "tourist_activity"},
    {"name": "Creux du Van", "query": "Creux du Van, Noiraigue, Switzerland", "category": "tourist_activity"},
    {"name": "Château de Chillon", "query": "Chateau de Chillon, Veytaux, Switzerland", "category": "tourist_activity"},
    {"name": "Lake Oeschinen", "query": "Oeschinensee, Kandersteg, Switzerland", "category": "tourist_activity"},
    {"name": "Trümmelbach Falls", "query": "Trummelbach Falls, Lauterbrunnen, Switzerland", "category": "tourist_activity"},
    {"name": "Swiss Museum of Transport", "query": "Swiss Museum of Transport, Lucerne, Switzerland", "category": "tourist_activity"},
    {"name": "BearPark Bern", "query": "BearPark, Bern, Switzerland", "category": "tourist_activity"},
    {"name": "Zoo Zurich", "query": "Zoo Zurich, Switzerland", "category": "tourist_activity"},
    {"name": "Chapel Bridge", "query": "Kapellbrucke, Lucerne, Switzerland", "category": "tourist_activity"},
    {"name": "Swissminiatur", "query": "Swissminiatur, Melide, Switzerland", "category": "tourist_activity"},
    {"name": "Ballenberg Swiss Open-Air Museum", "query": "Ballenberg, Brienzwiler, Switzerland", "category": "tourist_activity"},
    {"name": "Aare Gorge", "query": "Aare Gorge, Meiringen, Switzerland", "category": "tourist_activity"},
    {"name": "St. Beatus Caves", "query": "St. Beatus Caves, Beatenberg, Switzerland", "category": "tourist_activity"},
    {"name": "Verzasca Dam", "query": "Verzasca Dam, Gordola, Switzerland", "category": "tourist_activity"},
    {"name": "Lavaux Vineyard Terraces", "query": "Lavaux, Chexbres, Switzerland", "category": "tourist_activity"},
    {"name": "Blausee Nature Park", "query": "Blausee, Kandergrund, Switzerland", "category": "tourist_activity"},
    {"name": "Jet d'Eau", "query": "Jet d'Eau, Geneva, Switzerland", "category": "tourist_activity"},
    {"name": "Old Town Bern", "query": "Old City of Bern, Switzerland", "category": "tourist_activity"},
    {"name": "Lion Monument", "query": "Lion Monument, Lucerne, Switzerland", "category": "tourist_activity"},
    {"name": "Tamina Therme", "query": "Tamina Therme, Bad Ragaz, Switzerland", "category": "tourist_activity"},
]

ALL_ACTIVITIES: List[Dict[str, str]] = TOP_MOUNTAIN_EXCURSIONS + TOP_MUSEUMS + TOP_OTHER_ACTIVITIES


# ============================================================
# Utilities
# ============================================================
def read_places_master(path: Path) -> List[Dict[str, object]]:
    if not path.exists():
        raise FileNotFoundError(f"places_master.csv not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)

    required = {"slug", "name", "lat", "lon", "center_lat", "center_lon"}
    missing = sorted(required - set(reader.fieldnames or []))
    if missing:
        raise ValueError(f"Missing required columns in places_master.csv: {', '.join(missing)}")

    places: List[Dict[str, object]] = []
    for row in rows:
        lat = parse_float(row.get("center_lat"))
        lon = parse_float(row.get("center_lon"))
        if lat is None or lon is None:
            lat = parse_float(row.get("lat"))
            lon = parse_float(row.get("lon"))
        if lat is None or lon is None:
            continue

        active_raw = (row.get("active") or "").strip().lower()
        is_active = active_raw in {"1", "true", "yes", "y", "wahr", "ja"}

        places.append(
            {
                "slug": (row.get("slug") or "").strip(),
                "name": (row.get("name") or "").strip(),
                "lat": lat,
                "lon": lon,
                "active": is_active,
            }
        )

    if not places:
        raise ValueError("No usable municipality coordinates found in places_master.csv")
    return places


def parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def load_cache(path: Path) -> Dict[str, Dict[str, object]]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_cache(path: Path, cache: Dict[str, Dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def geocode_nominatim(query: str) -> Optional[Dict[str, object]]:
    params = urlencode({"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "ch"})
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})

    try:
        with urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"[WARN] Geocoding failed for '{query}': {exc}")
        return None

    if not payload:
        return None

    first = payload[0]
    lat = parse_float(first.get("lat"))
    lon = parse_float(first.get("lon"))
    if lat is None or lon is None:
        return None

    return {
        "lat": lat,
        "lon": lon,
        "display_name": first.get("display_name", ""),
        "osm_type": first.get("osm_type", ""),
        "osm_id": first.get("osm_id", ""),
        "source": "nominatim",
    }


def resolve_activity_coordinates(activity: Dict[str, str], cache: Dict[str, Dict[str, object]]) -> Optional[Dict[str, object]]:
    cache_key = activity["query"]
    if cache_key in cache:
        cached = cache[cache_key]
        if isinstance(cached, dict) and parse_float(cached.get("lat")) is not None and parse_float(cached.get("lon")) is not None:
            return cached

    result = geocode_nominatim(activity["query"])
    if result is None:
        cache[cache_key] = {"lat": None, "lon": None, "display_name": "", "source": "nominatim", "failed": True}
        return None

    cache[cache_key] = result
    time.sleep(REQUEST_DELAY_SECONDS)
    return result


def find_nearest_place(activity_lat: float, activity_lon: float, places: List[Dict[str, object]]) -> Tuple[Dict[str, object], float]:
    best_place = None
    best_distance = None
    for place in places:
        dist = haversine_km(activity_lat, activity_lon, float(place["lat"]), float(place["lon"]))
        if best_distance is None or dist < best_distance:
            best_place = place
            best_distance = dist
    assert best_place is not None and best_distance is not None
    return best_place, best_distance


def build_report(places: List[Dict[str, object]]) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], Dict[str, object]]:
    cache = load_cache(CACHE_PATH)
    report_rows: List[Dict[str, object]] = []
    not_covered_rows: List[Dict[str, object]] = []

    for idx, activity in enumerate(ALL_ACTIVITIES, start=1):
        print(f"[{idx:02d}/{len(ALL_ACTIVITIES)}] Resolving {activity['name']}...")
        coords = resolve_activity_coordinates(activity, cache)

        if coords is None or coords.get("lat") is None or coords.get("lon") is None:
            row = {
                "category": activity["category"],
                "activity_name": activity["name"],
                "query": activity["query"],
                "activity_lat": "",
                "activity_lon": "",
                "nearest_slug": "",
                "nearest_name": "",
                "distance_km": "",
                "within_10km": False,
                "status": "GEOCODE_FAILED",
                "geocoder_display_name": "",
            }
            report_rows.append(row)
            not_covered_rows.append(row)
            continue

        activity_lat = float(coords["lat"])
        activity_lon = float(coords["lon"])
        nearest_place, nearest_distance = find_nearest_place(activity_lat, activity_lon, places)
        within_10km = nearest_distance <= RADIUS_KM

        row = {
            "category": activity["category"],
            "activity_name": activity["name"],
            "query": activity["query"],
            "activity_lat": round(activity_lat, 6),
            "activity_lon": round(activity_lon, 6),
            "nearest_slug": nearest_place["slug"],
            "nearest_name": nearest_place["name"],
            "distance_km": round(nearest_distance, 3),
            "within_10km": within_10km,
            "status": "OK" if within_10km else "OUTSIDE_10KM",
            "geocoder_display_name": coords.get("display_name", ""),
        }
        report_rows.append(row)
        if not within_10km:
            not_covered_rows.append(row)

    save_cache(CACHE_PATH, cache)

    summary = {
        "places_master_path": str(PLACES_MASTER_PATH),
        "radius_km": RADIUS_KM,
        "total_places": len(places),
        "active_places": sum(1 for p in places if bool(p.get("active"))),
        "total_activities": len(ALL_ACTIVITIES),
        "mountain_excursions": len(TOP_MOUNTAIN_EXCURSIONS),
        "museums": len(TOP_MUSEUMS),
        "other_activities": len(TOP_OTHER_ACTIVITIES),
        "covered_within_10km": sum(1 for r in report_rows if r["status"] == "OK"),
        "outside_10km": sum(1 for r in report_rows if r["status"] == "OUTSIDE_10KM"),
        "geocode_failed": sum(1 for r in report_rows if r["status"] == "GEOCODE_FAILED"),
        "generated_files": {
            "all_report_csv": str(OUTPUT_ALL_PATH),
            "not_covered_csv": str(OUTPUT_NOT_COVERED_PATH),
            "summary_json": str(OUTPUT_SUMMARY_PATH),
            "geocode_cache_json": str(CACHE_PATH),
        },
    }
    return report_rows, not_covered_rows, summary


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    fieldnames = [
        "category",
        "activity_name",
        "query",
        "activity_lat",
        "activity_lon",
        "nearest_slug",
        "nearest_name",
        "distance_km",
        "within_10km",
        "status",
        "geocoder_display_name",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, summary: Dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def main() -> int:
    try:
        places = read_places_master(PLACES_MASTER_PATH)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1

    print(f"Loaded {len(places)} places from: {PLACES_MASTER_PATH}")
    print(f"Checking {len(ALL_ACTIVITIES)} activities against a {RADIUS_KM:.1f} km radius...")

    report_rows, not_covered_rows, summary = build_report(places)
    write_csv(OUTPUT_ALL_PATH, report_rows)
    write_csv(OUTPUT_NOT_COVERED_PATH, not_covered_rows)
    write_summary(OUTPUT_SUMMARY_PATH, summary)

    print("\nDone.")
    print(f"All activities report:   {OUTPUT_ALL_PATH}")
    print(f"Outside 10 km report:    {OUTPUT_NOT_COVERED_PATH}")
    print(f"Summary JSON:            {OUTPUT_SUMMARY_PATH}")
    print(f"Geocode cache:           {CACHE_PATH}")
    print("\nSummary:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
