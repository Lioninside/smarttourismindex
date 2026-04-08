# SmartTourismIndex — Scoring Model

> **Current version:** v5  
> **Version history:** v1 → 4-dimension MVP. v2 → 2-layer rewrite, ISOS. v3 → SBB API reachability, 14km radius, 184 places. v4 → water area-equivalent metric. v5 → walkability rewrite (OSM), weight rebalance, wider ISOS buffer, lake polygonize fix.  
> Previous versions archived in `docs/archive/`.

---

## Architecture

| Layer | Weight | Question |
|---|---|---|
| **Base** | 60% | Is this a good place to stay in? |
| **Access** | 40% | What can be reached within 1 hour by PT? |

PT is the engine, not a scored dimension. The SBB API reachable commune set powers all Access sub-scores. Strong PT shows up automatically — scoring it separately would double-count.

---

## Base layer — 60%

| Sub-score | Weight | Source | Radius |
|---|---|---|---|
| Anti-overtourism | **30%** | BFS overnights ÷ STATPOP residents 2024 | Commune |
| Local hiking | **20%** | swissTLM3D TLM_STRASSE WANDERWEGE (1,2,3) | 4 km |
| Water | **15%** | swissTLM3D lakes + rivers (area-equivalent) | 2 km |
| Heritage | **15%** | ISOS national inventory, graded by category | 4 km |
| Climate | **10%** | MeteoSwiss Jun–Aug normals | Grid point |
| Walkability | **10%** | OSM `gis_osm_roads_free` fclass pedestrian + living_street | 3 km |

### Anti-overtourism (30%)

```
tourism_intensity = annual_overnights_2024 / resident_population_2024
```

EU Commission / BFS standard indicator. Inverted (lower intensity → higher score), clipped at 99th percentile, min-max normalised across all places.

**Why clip at 99th percentile:** Zermatt (268.9), Lauterbrunnen (214.7), and Samnaun (210.3) are extreme outliers. Without clipping they compress the rest of the scale into a narrow band. The clip lets differences between moderate-pressure places remain meaningful.

**Interpretation:** High overnights alone does not mean high pressure. Locarno (~314K overnights, ~33K residents ≈ 9.5 per resident) correctly scores as low pressure. Zermatt (~1.6M overnights, ~6K residents ≈ 269 per resident) correctly scores near zero.

Validated extremes match published BFS / EU Commission figures exactly.

### Local hiking (20%)

Total metres of marked hiking trails within a 4 km buffer. `TLM_STRASSE.WANDERWEGE IN (1, 2, 3)` (national trail, regional trail, local trail). Min-max normalised.

### Water (15%)

**Metric: `water_equiv_2km_m2`**

```
water_equiv_2km_m2 = Σ clipped lake polygon area (m²)
                   + Σ (clipped river segment length (m) × BREITENKLASSE width)
```

River width per TLM `BREITENKLASSE` attribute:

| Class | Range | Width used |
|---|---|---|
| 1 | < 1 m | 0.5 m |
| 2 | 1–5 m | 3.0 m |
| 3 | 5–15 m | 10.0 m |
| 4 | 15–50 m | 30.0 m |
| 5 | > 50 m | 75.0 m |
| missing | — | 3.0 m (fallback) |

**Lake cap:** `min(lake_area, 1,000,000 m²)` per buffer. Prevents very large lakes (Lake Geneva, Lake Constance) from creating a 100× gap between lakeside and inland places.

**Lake geometry fix (v5):** TLM_STEHENDES_GEWAESSER stores outlines as closed LineStrings, not filled Polygons. `_polygonize_lakes()` applies `shapely.ops.polygonize(unary_union(...))` to convert 43,204 boundary lines to 19,108 lake polygons before area calculation. Without this fix all lake areas were 0.

Min-max normalised across all places.

### Heritage (15%)

ISOS national inventory (1,255 settlements) matched within a 4 km EPSG:2056 buffer. Multiple matches: take the highest score.

| ISOS category | Score |
|---|---|
| Stadt / Kleinstadt / Flecken | 1.0 |
| Dorf / village / villaggio / Verstädtertes Dorf | 0.7 |
| Spezialfall / Sonderfall / cas particulier / Agglomeration | 0.4 |
| Unrecognised category | 0.5 |
| No ISOS within 4 km | 0.0 |

**Important:** ISOS geometries are stored in LV95. Use `set_crs(2056)`, not `to_crs(2056)`. Buffer is applied after reprojecting the place coordinate from WGS84 to EPSG:2056.

### Climate (10%)

MeteoSwiss Jun–Aug temperature, precipitation, sunshine normals. 3-point raw score:

| Condition | +1 pt |
|---|---|
| 15°C ≤ summer temp avg ≤ 24°C | ✓ |
| 0 < summer precip avg < 120 mm | ✓ |
| sunshine avg > 0 | ✓ |

Min-max normalised. Moderate differentiator — Ticino and Valais benefit.

### Walkability (10%)

Total metres of pedestrian and living-street roads within a 3 km buffer.

Source: OSM `gis_osm_roads_free` layer, `fclass IN ('pedestrian', 'living_street')`.

**Why OSM, not TLM (changed in v5):** TLM_STRASSE OBJEKTART 5/7/9 includes all footpaths and sidewalks but does not tag car-free resort streets as pedestrian. This caused alpine resorts (Zermatt, Engelberg) to score correctly high while Arosa and Davos scored zero despite extensive pedestrian zones. OSM pedestrian and living_street tags better reflect actual car-free street environments.

**Why 3 km (changed from 500m):** A 500m buffer captured only the immediate town centre and was too sensitive to coordinate placement. 3 km captures the full walkable catchment of a base location.

Min-max normalised. Low weight (10%) reflects that walkability is correlated with urban character — over-weighting it creates a structural city bias.

---

## Access layer — 40%

| Sub-score | Weight | Source | Method |
|---|---|---|---|
| Scenic transport | **30%** | TLM_UEBRIGE_BAHN + TLM_SCHIFFFAHRT | 14 km radius (EPSG:2056) |
| Destination pull | **30%** | BFS overnights of reachable communes | SBB API reachable set |
| Cultural access | **25%** | OSM named museums in reachable communes | SBB API reachable set |
| Access hiking | **15%** | TLM WANDERWEGE regional trails | 20 km radius |

### Scenic transport (30%)

Counts active scenic transport lines within a 14 km radius. Includes: Gondelbahn, Luftseilbahn, Standseilbahn, Zahnradbahn, Kabinenbahn, boats (weighted 0.5×). Boats deduplicated by NAME.

`TLM_UEBRIGE_BAHN.AUSSER_BETRIEB` encoding is **inverted**: `1` = active (keep), `2` = out of service (exclude). Filter: `AUSSER_BETRIEB == 1`.

### Destination pull (30%)

Sum of annual overnights across the reachable commune set (SBB API, ≤1h travel time). Log-normalised to compress the Zurich advantage. Rewards places that can reach major tourism hubs within 1 hour.

### Cultural access (25%)

Count of named OSM museums (`fclass = 'museum'`, non-empty name) in reachable communes. Capped at 20. Normalised 0–1.

### Access hiking (15%)

Total metres of regional hiking trails within a 20 km radius. Separate from local hiking (which uses 4 km). Captures major trail networks reachable from the place.

---

## Score calculation

```python
base_score = (
    s_ot        * 0.30 +
    s_loc_hike  * 0.20 +
    s_water     * 0.15 +
    s_heritage  * 0.15 +
    s_climate   * 0.10 +
    s_walk      * 0.10
)

access_score = (
    s_scenic    * 0.30 +
    s_dp        * 0.30 +
    s_cultural  * 0.25 +
    s_acc_hike  * 0.15
)

total_score = (base_score * 0.60 + access_score * 0.40) × 100
```

All sub-scores 0–1 before weighting. Missing values → median of 184 places. Monteceneri excluded from final output (`scripts/pipeline/exclude.json`).

---

## Known limitations

| Place | Issue |
|---|---|
| Gruyères | Matched to Estavannens (Bas-Intyamon) in ISOS — wrong entry, coordinate proximity mismatch |
| Arosa, Davos | Walkability = 0 — their resort streets are not tagged pedestrian/living_street in OSM |
| Bellinzona | Heritage score 0.5 (città/Spezialfall) despite UNESCO castles — ISOS category mapping, not a data error |
| Zürich | local_hiking = 0 — Üetliberg trails not within 4km of coordinate placement |
