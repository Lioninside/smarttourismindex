#!/usr/bin/env python3
"""
11_merge_score.py

Implements the 2-layer scoring model for SmartTourismIndex.

Inputs:
  - metadata/places_master.csv
  - data_processed/bfs/bfs_place_metrics_2025.json
  - data_processed/climate/climate_metrics_jja.json
  - data_processed/water/water_metrics.json
  - data_processed/heritage/heritage_metrics.json        (ISOS-based, 0-1)
  - data_processed/hiking/hiking_metrics.json            (local + regional metres)
  - data_processed/walkability_metrics.json              (0-1 normalised)
  - data_processed/tourism_intensity_seasonality.csv     (tourism_intensity)
  - data_processed/scenic_access_metrics.json            (scenic_score, access_hiking_score)
  - data_processed/destination_pull_metrics.json         (destination_pull_score)
  - data_processed/cultural_access_metrics.csv           (cultural_access_score)

Output:
  - data_processed/final/place_scores.json

Scoring model:
  BASE  60%:
    ot_score           25%   (inverted tourism_intensity, 99th-pct clip)
    walkability_score  20%   (0-1)
    local_hiking_score 20%   (local_hiking_m normalised, 0-1)
    water_score        15%   (lake area + river length×BREITENKLASSE width within 2 km, normalised 0-1)
    heritage_score     10%   (ISOS graded, 0-1)
    climate_score      10%   (summer suitability, 0-1)

  ACCESS 40%:
    scenic_score          30%   (scenic transport + boats, 0-1)
    destination_pull_score 30%  (reachable overnights log-normalised, 0-1)
    cultural_access_score  25%  (reachable named museums, 0-1)
    access_hiking_score    15%  (reachable regional hiking, 0-1)

  TOTAL = BASE * 0.60 + ACCESS * 0.40  (scaled to 0-100)
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional

PLACES_CSV         = Path("metadata/places_master.csv")
BFS_JSON           = Path("data_processed/bfs/bfs_place_metrics_2025.json")
CLIMATE_JSON       = Path("data_processed/climate/climate_metrics_jja.json")
WATER_JSON         = Path("data_processed/water/water_metrics.json")
HERITAGE_JSON      = Path("data_processed/heritage/heritage_metrics.json")
HIKING_JSON        = Path("data_processed/hiking/hiking_metrics.json")
WALKABILITY_JSON   = Path("data_processed/walkability_metrics.json")
INTENSITY_CSV      = Path("data_processed/tourism_intensity_seasonality.csv")
SCENIC_JSON        = Path("data_processed/scenic_access_metrics.json")
DEST_PULL_JSON     = Path("data_processed/destination_pull_metrics.json")
CULTURAL_CSV       = Path("data_processed/cultural_access_metrics.csv")
OUTPUT_JSON        = Path("data_processed/final/place_scores.json")

# Clip tourism_intensity at this percentile to contain extreme outliers
OT_CLIP_PERCENTILE = 99


def load_json(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        print(f"  WARNING: {path} not found — will use median fallback for missing values")
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_csv_metrics(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        print(f"  WARNING: {path} not found — will use median fallback for missing values")
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_places(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [r for r in reader if str(r.get("active", "")).strip().lower() == "true"]


def index_by_slug(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {r["slug"]: r for r in rows if r.get("slug")}


def load_tourism_intensity(
    path: Path, places: List[Dict[str, Any]]
) -> Dict[str, Optional[float]]:
    """Return slug -> tourism_intensity (or None if missing)."""
    if not path.exists():
        print(f"  WARNING: {path} not found")
        return {}
    name_to_slug = {p["name"]: p["slug"] for p in places}
    result: Dict[str, Optional[float]] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            slug = row.get("slug", "").strip() or name_to_slug.get(row.get("gemeinde", "").strip())
            if not slug:
                continue
            raw = row.get("tourism_intensity", "").strip()
            if raw and raw not in ("None", "nan"):
                try:
                    result[slug] = float(raw)
                    continue
                except ValueError:
                    pass
            result[slug] = None
    return result


def build_ot_scores(
    intensity_map: Dict[str, Optional[float]],
    all_slugs: List[str],
) -> Dict[str, float]:
    """
    Invert and normalise tourism_intensity -> ot_score (0-1).
    Clip at 99th percentile before normalising to contain Zermatt/Lauterbrunnen.
    Missing values → median ot_score.
    """
    valid_vals = [v for v in intensity_map.values() if v is not None]
    if not valid_vals:
        return {s: 0.5 for s in all_slugs}

    sorted_vals = sorted(valid_vals)
    clip_idx = int(math.ceil(OT_CLIP_PERCENTILE / 100.0 * len(sorted_vals))) - 1
    clip_val = sorted_vals[min(clip_idx, len(sorted_vals) - 1)]

    clipped = [min(v, clip_val) for v in valid_vals]
    ti_min = min(clipped)
    ti_max = max(clipped)
    ti_range = ti_max - ti_min if ti_max > ti_min else 1.0

    known_scores: Dict[str, float] = {}
    for slug in all_slugs:
        raw = intensity_map.get(slug)
        if raw is None:
            continue
        ti = min(raw, clip_val)
        # Invert: lower intensity → higher score
        known_scores[slug] = (ti_max - ti) / ti_range

    median_score = statistics.median(known_scores.values()) if known_scores else 0.5

    result: Dict[str, float] = {}
    for slug in all_slugs:
        if slug in known_scores:
            result[slug] = known_scores[slug]
        else:
            print(f"  WARNING: missing tourism_intensity for {slug} — using median {median_score:.3f}")
            result[slug] = median_score

    return result


def normalise_column(
    rows: List[Dict[str, Any]],
    col: str,
    all_slugs: List[str],
) -> Dict[str, float]:
    """Min-max normalise a column across all slugs. Missing → median."""
    vals = {r["slug"]: float(r[col]) for r in rows if r.get("slug") and col in r}
    known = list(vals.values())
    if not known:
        return {s: 0.5 for s in all_slugs}

    v_min = min(known)
    v_max = max(known)
    v_range = v_max - v_min if v_max > v_min else 1.0
    median_norm = statistics.median([(v - v_min) / v_range for v in known])

    result: Dict[str, float] = {}
    for slug in all_slugs:
        if slug in vals:
            result[slug] = (vals[slug] - v_min) / v_range
        else:
            print(f"  WARNING: missing {col} for {slug} — using median {median_norm:.3f}")
            result[slug] = median_norm
    return result


def water_score_from_row(row: Dict[str, Any]) -> float:
    """Combined water equivalent (m²) within 2 km buffer.

    Lakes: clipped polygon area.
    Rivers: clipped length × assumed width (30 m) → equivalent area.

    This gives fair weight to both lakeside towns (Spiez on Lake Thun) and
    river cities (Bern on the Aare, Basel on the Rhine) while avoiding the
    old stream-segment-count bias that inflated alpine stream-heavy areas.

    Falls back to 0 if the field is absent (old water_metrics.json —
    re-run 08_water.py to populate it).
    """
    return float(row.get("water_equiv_2km_m2", 0))


def climate_score_from_row(row: Dict[str, Any]) -> float:
    """Produce a 0-3 raw climate suitability score from summer metrics."""
    score = 0.0
    temp = float(row.get("summer_temp_avg", 0) or 0)
    precip = float(row.get("summer_precip_avg", 0) or 0)
    sunshine = float(row.get("summer_sunshine_avg", 0) or 0)
    if 15 <= temp <= 24:
        score += 1.0
    if 0 < precip < 120:
        score += 1.0
    if sunshine > 0:
        score += 1.0
    return score


def get_or_median(d: Dict[str, float], slug: str, label: str) -> float:
    if slug in d:
        return d[slug]
    med = statistics.median(d.values()) if d else 0.5
    print(f"  WARNING: {label} missing for {slug}, using median {med:.3f}")
    return med


def main() -> None:
    places = read_places(PLACES_CSV)
    all_slugs = [p["slug"] for p in places]

    bfs       = index_by_slug(load_json(BFS_JSON))
    climate   = index_by_slug(load_json(CLIMATE_JSON))
    water     = index_by_slug(load_json(WATER_JSON))
    heritage  = index_by_slug(load_json(HERITAGE_JSON))
    hiking    = index_by_slug(load_json(HIKING_JSON))
    walk      = index_by_slug(load_json(WALKABILITY_JSON))
    scenic    = index_by_slug(load_json(SCENIC_JSON))
    dest_pull = index_by_slug(load_json(DEST_PULL_JSON))
    cultural  = index_by_slug(load_csv_metrics(CULTURAL_CSV))

    intensity_map = load_tourism_intensity(INTENSITY_CSV, places)

    # Pre-compute normalised sub-scores across all 185 places
    ot_scores       = build_ot_scores(intensity_map, all_slugs)
    walk_scores     = {r["slug"]: float(r["walkability_score"])
                       for r in load_json(WALKABILITY_JSON) if "walkability_score" in r}
    local_hike_norm = normalise_column(list(hiking.values()), "local_hiking_m", all_slugs)
    water_norm      = normalise_column(
        [{"slug": s, "water_equiv_2km_m2": water_score_from_row(r)}
         for s, r in water.items()],
        "water_equiv_2km_m2", all_slugs,
    )
    climate_norm    = normalise_column(
        [{"slug": s, "_cs": climate_score_from_row(r)} for s, r in climate.items()],
        "_cs", all_slugs,
    )

    scenic_scores    = {r["slug"]: float(r["scenic_score"])
                        for r in load_json(SCENIC_JSON) if "scenic_score" in r}
    dp_scores        = {r["slug"]: float(r["destination_pull_score"])
                        for r in load_json(DEST_PULL_JSON) if "destination_pull_score" in r}
    cult_scores      = {r["slug"]: float(r["cultural_access_score"])
                        for r in load_csv_metrics(CULTURAL_CSV) if "cultural_access_score" in r}
    acc_hike_scores  = {r["slug"]: float(r["regional_hiking_score"])
                        for r in load_json(HIKING_JSON) if "regional_hiking_score" in r}

    rows: List[Dict[str, Any]] = []

    for place in places:
        slug = place["slug"]
        b  = bfs.get(slug, {})
        he = heritage.get(slug, {})
        o  = walk.get(slug, {})

        # ── BASE sub-scores (all 0-1) ─────────────────────────────────────
        s_ot        = get_or_median(ot_scores,       slug, "ot_score")
        s_walk      = get_or_median(walk_scores,      slug, "walkability_score")
        s_loc_hike  = get_or_median(local_hike_norm,  slug, "local_hiking_score")
        s_water     = get_or_median(water_norm,       slug, "water_score")
        s_heritage  = float(he.get("heritage_score", 0))
        s_climate   = get_or_median(climate_norm,     slug, "climate_score")

        base_score = (
            s_ot       * 0.25 +
            s_walk     * 0.20 +
            s_loc_hike * 0.20 +
            s_water    * 0.15 +
            s_heritage * 0.10 +
            s_climate  * 0.10
        )

        # ── ACCESS sub-scores (all 0-1) ───────────────────────────────────
        s_scenic   = get_or_median(scenic_scores,   slug, "scenic_score")
        s_dp       = get_or_median(dp_scores,        slug, "destination_pull_score")
        s_cultural = get_or_median(cult_scores,      slug, "cultural_access_score")
        s_acc_hike = get_or_median(acc_hike_scores,  slug, "access_hiking_score")

        access_score = (
            s_scenic   * 0.30 +
            s_dp       * 0.30 +
            s_cultural * 0.25 +
            s_acc_hike * 0.15
        )

        total_score = round((base_score * 0.60 + access_score * 0.40) * 100, 2)

        # ── Tags ─────────────────────────────────────────────────────────
        reachable_tags = []
        if hiking.get(slug, {}).get("hiking_reachable"):
            reachable_tags.append("Hiking")
        if water.get(slug, {}).get("local_water"):
            reachable_tags.append("Water")
        if scenic.get(slug, {}).get("scenic_transport_count", 0) > 0:
            reachable_tags.append("Scenic transport")
        if int(cultural.get(slug, {}).get("reachable_named_museums", 0) or 0) > 0:
            reachable_tags.append("Museums")
        if he.get("isos_name"):
            reachable_tags.append("Historic town")

        rows.append({
            "slug":        slug,
            "name":        place["name"],
            "canton":      place.get("canton", ""),
            "score_total": total_score,
            "scores": {
                "total":  total_score,
                "base":   round(base_score  * 100, 2),
                "access": round(access_score * 100, 2),
                "sub": {
                    "anti_overtourism":  round(s_ot        * 100, 2),
                    "walkability":       round(s_walk       * 100, 2),
                    "local_hiking":      round(s_loc_hike   * 100, 2),
                    "water":             round(s_water       * 100, 2),
                    "heritage":          round(s_heritage   * 100, 2),
                    "climate":           round(s_climate     * 100, 2),
                    "scenic_transport":  round(s_scenic      * 100, 2),
                    "destination_pull":  round(s_dp          * 100, 2),
                    "cultural_access":   round(s_cultural    * 100, 2),
                    "access_hiking":     round(s_acc_hike    * 100, 2),
                },
            },
            # Legacy field kept for backwards compatibility with export script
            "subscores": {
                "base_quality":      round(base_score   * 100, 2),
                "access_value":      round(access_score * 100, 2),
                "anti_overtourism":  round(s_ot         * 100, 2),
            },
            "reachable_tags": reachable_tags,
            "metrics": {
                "overnight_stays":           b.get("overnight_stays"),
                "domestic_share_overnights": b.get("domestic_share_overnights"),
                "summer_temp_avg":           climate.get(slug, {}).get("summer_temp_avg"),
                "local_hiking_m":            hiking.get(slug, {}).get("local_hiking_m"),
                "regional_hiking_m":         hiking.get(slug, {}).get("regional_hiking_m"),
                "walkability_path_m":        o.get("walkability_path_m"),
                "scenic_transport_count":    scenic.get(slug, {}).get("scenic_transport_count"),
                "reachable_named_museums":   cultural.get(slug, {}).get("reachable_named_museums"),
                "isos_name":                 he.get("isos_name", ""),
                "isos_kategorie":            he.get("isos_kategorie", ""),
            },
            "data_status": {
                "bfs":          bool(b),
                "climate":      bool(climate.get(slug)),
                "water":        bool(water.get(slug)),
                "heritage":     bool(he),
                "hiking":       bool(hiking.get(slug)),
                "walkability":  bool(o),
                "scenic":       bool(scenic.get(slug)),
                "dest_pull":    bool(dest_pull.get(slug)),
                "cultural":     bool(cultural.get(slug)),
            },
        })

    rows.sort(key=lambda x: (-x["score_total"], x["name"]))

    # Exclude places listed in metadata/exclude.json
    exclude_path = Path("metadata/exclude.json")
    exclude: List[str] = []
    if exclude_path.exists():
        exclude = json.load(exclude_path.open(encoding="utf-8"))
        before = len(rows)
        rows = [r for r in rows if r["slug"] not in exclude]
        print(f"Excluded {before - len(rows)} places: {exclude}")

    # Add rank
    for i, row in enumerate(rows):
        row["rank"] = i + 1

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(rows)} rows")
    _print_report(rows, exclude)


def _pct(vals: List[float], p: float) -> float:
    """Pure-Python percentile (nearest rank)."""
    if not vals:
        return 0.0
    s = sorted(vals)
    idx = max(0, min(len(s) - 1, int(math.ceil(p / 100 * len(s))) - 1))
    return s[idx]


def _print_report(rows: List[Dict[str, Any]], exclude: List[str]) -> None:
    SEP = "=" * 60
    n = len(rows)

    totals  = [r["score_total"]              for r in rows]
    bases   = [r["scores"]["base"]           for r in rows]
    accesses= [r["scores"]["access"]         for r in rows]

    sub_keys = [
        "anti_overtourism", "walkability", "local_hiking", "water",
        "heritage", "climate", "scenic_transport", "destination_pull",
        "cultural_access", "access_hiking",
    ]

    print(f"\n{SEP}")
    print("SCORE REPORT")
    print(SEP)
    print(f"Places scored : {n}")
    print(f"Excluded      : {len(exclude)} ({', '.join(exclude) if exclude else 'none'})")

    for label, vals in [("TOTAL", totals), ("BASE", bases), ("ACCESS", accesses)]:
        print(f"\n{label} SCORE distribution:")
        if label == "TOTAL":
            for tag, p in [("min", 0), ("p10", 10), ("p25", 25),
                           ("median", 50), ("p75", 75), ("p90", 90), ("max", 100)]:
                print(f"  {tag:<8}: {_pct(vals, p):.1f}")
            print(f"  {'range':<8}: {max(vals) - min(vals):.1f}")
        else:
            lo, med, hi = _pct(vals, 0), _pct(vals, 50), _pct(vals, 100)
            print(f"  min / median / max: {lo:.1f} / {med:.1f} / {hi:.1f}")

    print("\nSUB-SCORE COVERAGE (non-zero counts):")
    for key in sub_keys:
        nonzero = sum(1 for r in rows if r["scores"]["sub"].get(key, 0) > 0)
        print(f"  {key:<20}: {nonzero:>3} / {n}")

    print(f"\nTOP 10:")
    for r in rows[:10]:
        s = r["scores"]
        print(f"  {r['rank']:>2}  {r['name']:<20} {r['canton']:<3} "
              f"total={r['score_total']:.1f}  base={s['base']:.1f}  access={s['access']:.1f}")

    print(f"\nBOTTOM 5:")
    for r in rows[-5:]:
        s = r["scores"]
        print(f"  {r['rank']:>3}  {r['name']:<20} {r['canton']:<3} "
              f"total={r['score_total']:.1f}  base={s['base']:.1f}  access={s['access']:.1f}")

    print(f"\n{SEP}\n")


if __name__ == "__main__":
    main()
