# SmartTourismIndex

Offline-first Swiss tourism ranking pipeline and website export. Identifies beautiful Swiss base locations with strong public transport access and lower overtourism pressure than the obvious hotspots.

Live ranking: **[smarttourismindex.onrender.com](https://smarttourismindex.onrender.com)**

---

## What it does

Answers the question: *Where should a tourist stay in Switzerland for a beautiful, practical base with access to nature, scenic transport, water, and culture — without defaulting to the most crowded places?*

The index ranks 184 Swiss places on two layers:

| Layer | Weight | What it measures |
|---|---|---|
| **Base** | 60% | Quality of the place itself (anti-overtourism, hiking, water, heritage, climate, walkability) |
| **Access** | 40% | What is reachable within 1 hour by public transport (scenic transport, destinations, culture, hiking) |

Public transport is the engine, not a scored dimension — strong PT automatically improves Access scores.

---

## Repository structure

```
smarttourismindex/
├── README.md
├── .gitignore
│
├── docs/
│   ├── SCORING_MODEL.md       ← current weights, formulas, data sources
│   ├── PIPELINE.md            ← script reference, setup, engineering notes
│   ├── CHANGELOG.md           ← version history
│   └── archive/               ← previous version docs
│
├── metadata/
│   ├── places_master.csv      ← canonical place list (slug, name, canton, coordinates)
│   ├── place_mapping.json     ← BFS commune name → slug alias map
│   └── places_master_template.csv
│
├── scripts/
│   ├── pipeline/              ← 02_bfs → ... → 12_export (numbered, run in order)
│   │   └── exclude.json       ← slugs excluded from final output
│   ├── tools/                 ← one-time setup and inspection utilities
│   ├── run_smart_tourism_pipeline.ps1
│   └── run_smart_tourism_pipeline_skip.ps1
│
├── data_raw/                  ← source files, local only (gitignored)
├── data_processed/            ← pipeline outputs, committed to git
├── data_export/               ← website-ready JSON, committed to git
└── website/                   ← frontend (HTML, CSS, JS)
```

---

## Running the pipeline

From repo root:

```powershell
# Full run
powershell -ExecutionPolicy Bypass -File .\scripts\run_smart_tourism_pipeline.ps1

# Skip already-complete steps (use during development)
powershell -ExecutionPolicy Bypass -File .\scripts\run_smart_tourism_pipeline_skip.ps1
```

Required packages:
```powershell
python -m pip install xarray netCDF4 pandas geopandas shapely pyogrio fiona pyproj
```

See `docs/PIPELINE.md` for one-time setup steps (TLM extraction, ISOS download) and the full script reference.

---

## Data sources

| Source | Used for |
|---|---|
| BFS tourism statistics | Overnights, occupancy, domestic/international split |
| STATPOP 2024 | Resident population (tourism intensity denominator) |
| MeteoSwiss NetCDF normals | Summer climate metrics (Jun–Aug) |
| swissTLM3D GDB | Hiking trails, water features, scenic transport |
| OSM GeoPackage (Switzerland) | Walkability, museums, POIs |
| ISOS national inventory | Heritage/historic townscape classification |
| SBB API (cached) | 1-hour PT reachability per place |

All source files stay in `data_raw/` (gitignored, local only).

---

## Documentation

| File | Contents |
|---|---|
| `docs/SCORING_MODEL.md` | All weights, formulas, normalisation, known limitations |
| `docs/PIPELINE.md` | Script order, data flow, engineering issues, sanity checks |
| `docs/CHANGELOG.md` | What changed in each version |
