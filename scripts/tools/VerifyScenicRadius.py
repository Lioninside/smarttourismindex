"""
VerifyScenicRadius.py
=====================
Extracts scenic/tourist transport stops from Swiss GTFS within
12km of each base place and prints a summary to verify coverage.

No API calls — reads directly from the local GTFS zip.

Run from: project root OR scripts/tools/
Output:   prints to console + saves scripts/tools/scenic_radius_check.csv
"""

import csv, io, math, zipfile
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
for candidate in [BASE, BASE.parent, BASE.parent.parent]:
    if (candidate / "data_raw").exists():
        ROOT = candidate
        break
else:
    raise FileNotFoundError("Cannot find data_raw/")

GTFS_ZIP   = ROOT / "data_raw" / "gtfs" / "gtfs_fp2025_20251211.zip"
PLACES_CSV = ROOT / "metadata" / "places_master.csv"
OUT_CSV    = BASE / "scenic_radius_check.csv"
RADIUS_KM  = 13.0

# ── Scenic keywords ───────────────────────────────────────────────────────────
SCENIC_KEYWORDS = [
    "gondel","luftseil","seilbahn","standseil","zahnrad","kabinen","sesselbahn",
    "schiff","fähre","dampf","bootsanlegest",
    "jungfrau","joch","eismeer","eigergletscher","kleine scheidegg",
    "gornergrat","riffelberg","riffelalp","rotenboden",
    "titlis","trübsee","kleintitlis",
    "rigi","kulm","staffel","kaltbad",
    "pilatus","fräkmüntegg","tomlishorn",
    "schilthorn","birg","mürren","gimmelwald","stechelberg",
    "männlichen","grindelwald, grund",
    "stockhorn","niederhorn","beatenberg","niesen","mülenen",
    "harder","brienzer rothorn","bürgenstock","hammetschwand",
    "säntis","schwägalp","kronberg","ebenalp",
    "pizol","flumserberg","hoher kasten",
    "cardada","cimetta","monte generoso","monte san salvatore",
    "monte lema","monte tamaro","monte bar",
    "funicolare","funivia","cabinovia","seggiovia",
    "telecabine","téléphérique","télécabine","télésiège","crémaillère","funiculaire",
    "bergstation","talstation","mittelstation",
]

def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1-a))

def is_scenic(name):
    n = name.lower()
    return any(kw in n for kw in SCENIC_KEYWORDS)

# ── Load places ───────────────────────────────────────────────────────────────
places = []
with open(PLACES_CSV, encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f, delimiter=";"):
        if str(row.get("active","")).strip().upper() not in ("WAHR","TRUE","1","YES"):
            continue
        try:
            places.append({
                "slug": row["slug"].strip(),
                "name": row["name"].strip(),
                "lat":  float(row["lat"]),
                "lon":  float(row["lon"]),
            })
        except (ValueError, KeyError):
            continue
print(f"Places loaded: {len(places)}")

# ── Load GTFS stops ───────────────────────────────────────────────────────────
print("Loading GTFS stops…")
stops = []
with zipfile.ZipFile(GTFS_ZIP, "r") as zf:
    with zf.open("stops.txt") as f:
        for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")):
            try:
                lat = float(row["stop_lat"])
                lon = float(row["stop_lon"])
            except (ValueError, KeyError):
                continue
            name = (row.get("stop_name") or "").strip()
            if name and is_scenic(name):
                stops.append({"stop_name": name, "lat": lat, "lon": lon})

print(f"Scenic stops (keyword match): {len(stops):,}")
print()

# ── Check radius ──────────────────────────────────────────────────────────────
print(f"Checking {RADIUS_KM}km radius…")
results = []
zero_places = []

for place in places:
    nearby = sorted(
        [{"stop_name": s["stop_name"], "dist_km": round(haversine_km(place["lat"], place["lon"], s["lat"], s["lon"]), 2)}
         for s in stops if haversine_km(place["lat"], place["lon"], s["lat"], s["lon"]) <= RADIUS_KM],
        key=lambda x: x["dist_km"]
    )
    if not nearby:
        zero_places.append(place["name"])
    results.append({
        "slug":         place["slug"],
        "name":         place["name"],
        "scenic_count": len(nearby),
        "closest":      nearby[0]["stop_name"] if nearby else "",
        "closest_km":   nearby[0]["dist_km"] if nearby else "",
        "top5":         " | ".join(f"{s['stop_name']} ({s['dist_km']}km)" for s in nearby[:5]),
    })

# ── Print summary ─────────────────────────────────────────────────────────────
results.sort(key=lambda x: -x["scenic_count"])

print(f"\n{'='*65}")
print(f"RADIUS: {RADIUS_KM}km  |  Places: {len(places)}  |  Scenic stops: {len(stops)}")
print(f"{'='*65}")
print(f"\nTop 20 by scenic stop count:")
print(f"  {'Place':<28} {'Count':>5}  Closest")
print(f"  {'-'*60}")
for r in results[:20]:
    print(f"  {r['name']:<28} {r['scenic_count']:>5}  {r['closest']} ({r['closest_km']}km)")

print(f"\nBottom 10 (lowest coverage):")
print(f"  {'Place':<28} {'Count':>5}  Closest")
print(f"  {'-'*60}")
for r in results[-10:]:
    cl = f"{r['closest']} ({r['closest_km']}km)" if r['closest'] else "NONE"
    print(f"  {r['name']:<28} {r['scenic_count']:>5}  {cl}")

print(f"\nPlaces with ZERO scenic stops: {len(zero_places)}")
if zero_places:
    print("  " + ", ".join(zero_places))

print(f"\nDistribution:")
for lo, hi in [(0,0),(1,2),(3,5),(6,10),(11,20),(21,999)]:
    count = sum(1 for r in results if lo <= r["scenic_count"] <= hi)
    label = f"{lo}" if lo==hi else (f"{lo}–{hi}" if hi<999 else f"{lo}+")
    print(f"  {label:>6} stops: {count:>4} places  {'█'*min(count,40)}")

# ── Save CSV ──────────────────────────────────────────────────────────────────
with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["slug","name","scenic_count","closest","closest_km","top5"])
    w.writeheader()
    w.writerows(results)
print(f"\nSaved → {OUT_CSV}")