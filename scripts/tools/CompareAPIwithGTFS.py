"""
CompareAPIwithGTFS.py
=====================
Compares two reachability JSON files:
  - gtfs_reachability.json   (computed from local GTFS feed)
  - sbbAPI_reachability.json (computed via SBB live API)

Both files have the format: { "slug": ["slug1", "slug2", ...], ... }

Outputs:
  - Per-place diff: what's in API but not GTFS, and vice versa
  - Summary statistics
  - Places with largest disagreement

Run from: project root OR scripts/tools/
"""

import json
from pathlib import Path

BASE = Path(__file__).parent
for candidate in [BASE, BASE.parent, BASE.parent.parent]:
    if (candidate / "data_processed").exists():
        ROOT = candidate
        break
else:
    raise FileNotFoundError("Cannot find data_processed/ folder")

GTFS_FILE = ROOT / "data_processed" / "gtfs" / "gtfs_reachability.json"
API_FILE  = ROOT / "data_processed" / "gtfs" / "sbbAPI_reachability.json"

print(f"GTFS file : {GTFS_FILE}")
print(f"API file  : {API_FILE}")
print()

# ── Load ──────────────────────────────────────────────────────────────────────
with open(GTFS_FILE, encoding="utf-8") as f:
    gtfs = json.load(f)
with open(API_FILE, encoding="utf-8") as f:
    api = json.load(f)

all_slugs = sorted(set(list(gtfs.keys()) + list(api.keys())))
print(f"Places in GTFS : {len(gtfs)}")
print(f"Places in API  : {len(api)}")
print(f"Total unique   : {len(all_slugs)}")
print()

# ── Compare ───────────────────────────────────────────────────────────────────
results = []

for slug in all_slugs:
    g = set(gtfs.get(slug, []))
    a = set(api.get(slug, []))

    only_gtfs = sorted(g - a)   # GTFS found but API didn't
    only_api  = sorted(a - g)   # API found but GTFS didn't
    both      = sorted(g & a)   # agreed by both
    total     = len(g | a)

    if total > 0:
        agreement_pct = round(len(both) / total * 100, 1)
    else:
        agreement_pct = 100.0

    results.append({
        "slug":         slug,
        "gtfs_count":   len(g),
        "api_count":    len(a),
        "both_count":   len(both),
        "only_gtfs":    only_gtfs,
        "only_api":     only_api,
        "agreement":    agreement_pct,
        "diff_size":    len(only_gtfs) + len(only_api),
    })

# ── Summary ───────────────────────────────────────────────────────────────────
perfect   = sum(1 for r in results if r["diff_size"] == 0)
minor     = sum(1 for r in results if 1 <= r["diff_size"] <= 3)
moderate  = sum(1 for r in results if 4 <= r["diff_size"] <= 8)
major     = sum(1 for r in results if r["diff_size"] > 8)

avg_agreement = sum(r["agreement"] for r in results) / len(results) if results else 0

print(f"{'='*60}")
print(f"SUMMARY")
print(f"{'='*60}")
print(f"  Average agreement : {avg_agreement:.1f}%")
print(f"  Perfect match     : {perfect} places (0 diff)")
print(f"  Minor diff (1–3)  : {minor} places")
print(f"  Moderate (4–8)    : {moderate} places")
print(f"  Major (9+)        : {major} places")
print()

# ── Largest disagreements ─────────────────────────────────────────────────────
by_diff = sorted(results, key=lambda x: -x["diff_size"])

print(f"{'='*60}")
print(f"TOP 20 LARGEST DISAGREEMENTS")
print(f"{'='*60}")
for r in by_diff[:20]:
    if r["diff_size"] == 0:
        break
    print(f"\n  {r['slug']}  (GTFS: {r['gtfs_count']} | API: {r['api_count']} | agreement: {r['agreement']}%)")
    if r["only_api"]:
        print(f"    API only  (+): {', '.join(r['only_api'])}")
    if r["only_gtfs"]:
        print(f"    GTFS only (-): {', '.join(r['only_gtfs'])}")

# ── Perfect matches ───────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"PERFECT MATCHES ({perfect} places)")
print(f"{'='*60}")
for r in results:
    if r["diff_size"] == 0:
        print(f"  ✓ {r['slug']} ({r['both_count']} communes)")

# ── Places only in one file ───────────────────────────────────────────────────
only_in_gtfs = [r["slug"] for r in results if r["api_count"] == 0 and r["gtfs_count"] > 0]
only_in_api  = [r["slug"] for r in results if r["gtfs_count"] == 0 and r["api_count"] > 0]

if only_in_gtfs:
    print(f"\nPlaces in GTFS but missing from API ({len(only_in_gtfs)}):")
    print("  " + ", ".join(only_in_gtfs))

if only_in_api:
    print(f"\nPlaces in API but missing from GTFS ({len(only_in_api)}):")
    print("  " + ", ".join(only_in_api))

print()
print("Done.")