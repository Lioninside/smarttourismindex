"""
InspectZeroPlaces.py
====================
For a list of places that show zero scenic stops at 14km,
shows ALL scenic stops within 20km so we can judge:
- are there relevant attractions just outside the radius?
- are the stops mostly ski lifts / winter-only?
- are there missing keywords (e.g. Bernina Express)?

Run from: project root OR scripts/tools/
"""

import csv, io, math, zipfile
from pathlib import Path

BASE = Path(__file__).parent
for candidate in [BASE, BASE.parent, BASE.parent.parent]:
    if (candidate / "data_raw").exists():
        ROOT = candidate
        break
else:
    raise FileNotFoundError("Cannot find data_raw/")

GTFS_ZIP   = ROOT / "data_raw" / "gtfs" / "gtfs_fp2025_20251211.zip"
PLACES_CSV = ROOT / "metadata" / "places_master.csv"

RADIUS_KM = 20.0  # wider net to see what's just outside 14km

TARGET_PLACES = {
    "herzogenbuchsee", "langenthal", "langnau-im-emmental", "geneve", "lancy",
    "soglio", "poschiavo", "spluegen", "samnaun", "scuol", "zernez",
    "clos-du-doubs", "delemont", "porrentruy", "sursee", "la-grande-beroche",
    "uzwil", "feusisberg", "lausanne", "le-chenit", "morges", "nyon",
    # also try alternate slug forms
    "langnau", "genf", "splügen", "splügen", "splugen",
}

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
    # extra for this inspection — broader net
    "bernina","tirano","alp grüm","cavaglia","brüsio",
    "oberalp","andermatt","sedrun",
    "disentis","mustér",
    "ski","piste","snow",  # to spot winter-only
    "winter","sommer","ganzjährig",
]

def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1-a))

def is_scenic(name):
    return any(kw in name.lower() for kw in SCENIC_KEYWORDS)

# ── Load target places ────────────────────────────────────────────────────────
places = []
with open(PLACES_CSV, encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f, delimiter=";"):
        slug = row["slug"].strip().lower()
        name = row["name"].strip()
        # match by slug or by name (fuzzy)
        name_slug = name.lower().replace(" ", "-").replace("/","").replace("ü","u").replace("ä","a").replace("é","e").replace("è","e")
        if slug in TARGET_PLACES or name_slug in TARGET_PLACES or any(t in slug for t in TARGET_PLACES) or any(t in name.lower() for t in ["herzogenbuchsee","langenthal","langnau","genève","geneve","lancy","soglio","poschiavo","splügen","splugen","samnaun","scuol","zernez","clos du doubs","delémont","delemont","porrentruy","sursee","grande béroche","uzwil","feusisberg","lausanne","chenit","morges","nyon"]):
            try:
                places.append({
                    "slug": slug,
                    "name": name,
                    "lat":  float(row["lat"]),
                    "lon":  float(row["lon"]),
                })
            except ValueError:
                pass

print(f"Target places found: {len(places)}")
for p in places:
    print(f"  {p['name']} ({p['slug']})")
print()

# ── Load GTFS scenic stops ────────────────────────────────────────────────────
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

print(f"Scenic stops loaded: {len(stops):,}")
print()

# ── For each target place show all stops within 20km ─────────────────────────
for place in sorted(places, key=lambda x: x["name"]):
    nearby = []
    for s in stops:
        dist = haversine_km(place["lat"], place["lon"], s["lat"], s["lon"])
        if dist <= RADIUS_KM:
            nearby.append({"name": s["stop_name"], "dist": round(dist, 1)})
    nearby.sort(key=lambda x: x["dist"])

    print(f"{'─'*60}")
    print(f"{place['name'].upper()}  ({len(nearby)} stops within {RADIUS_KM}km)")
    if not nearby:
        print("  → NONE — genuinely no scenic transport infrastructure nearby")
    else:
        for s in nearby:
            marker = "  ✓" if s["dist"] <= 14 else " ⚠" # within 14km vs outside
            print(f"  {marker} {s['dist']:>5}km  {s['name']}")
    print()

print("Legend: ✓ = within 14km  ⚠ = 14–20km (just outside current radius)")
