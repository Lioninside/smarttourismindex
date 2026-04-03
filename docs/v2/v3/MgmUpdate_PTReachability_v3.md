# SmartTourismIndex — Management Update: PT Reachability Model v3

## Objective

Establish a robust, comparable measure of public transport accessibility across 184 Swiss tourism municipalities. Output: a structured reachability graph indicating which destinations can be reached within 60 minutes by public transport.

---

## Result

A municipality-to-municipality accessibility network based on real SBB timetable data, using validated transport hubs, with controlled computational complexity.

```json
{
  "bellinzona": ["locarno", "lugano", "biasca"],
  "luzern": ["zug", "schwyz", "engelberg", "interlaken"]
}
```

File: `data_processed/sbbapi/sbbAPI_reachability.json`

---

## Architecture — 4 steps

### 1. Curated municipality master
`places_master.csv` — 184 municipalities, each with a manually verified SBB station ID and representative PT hub. This is the single source of truth.

### 2. Representative PT hub assignment
Each municipality is assigned one meaningful transport node:
- Main railway station where available
- Central bus hub otherwise
- Nearby functional hub in edge cases (e.g. Matten bei Interlaken → Interlaken West)

Manual validation was essential — automated station matching produced many technically correct but strategically wrong results.

### 3. 100km geographic prefilter
Before any API calls: only municipalities within 100km air distance are considered as candidates. This reduces API calls by ~90%, avoids rate-limit issues, and keeps computation manageable.

### 4. SBB API verification (ground truth)
Real timetable queries for each candidate pair. Only connections with ≤ 60 minutes total travel time are retained. This is the authoritative step — API response reflects actual passenger experience.

---

## Why not GTFS?

A GTFS-based reachability script was built and tested. Results: **27.7% agreement** with SBB API verified connections.

Root cause: Swiss GTFS heavily uses `calendar_dates.txt` exceptions rather than regular `calendar.txt` entries. Scripts filtering by calendar type exclude large portions of actual service. The SBB live API returns correct results regardless of how service is encoded in the feed.

Decision: SBB API is the authoritative source. GTFS script (`06b_gtfs_reachability.py`) kept on disk but not run in the pipeline.

---

## Key decisions

**Hub over local stop:** Choosing the main interchange (e.g. Interlaken Ost, not a local municipal bus) produces realistic accessibility that reflects actual tourist behaviour.

**BFS alignment:** Municipalities aligned with BFS statistical units for compatibility with overnight data in the scoring model.

**Prefilter radius:** 100km air distance eliminates impossible connections without API calls. Switzerland is ~400km × 220km — 100km covers all realistic 1-hour PT connections with margin.

---

## Refresh cadence

Regenerate `sbbAPI_reachability.json` annually after the December SBB timetable update, or when `places_master.csv` changes (new places, corrected station IDs).

---

## Known risks

| Risk | Impact | Status |
|---|---|---|
| Wrong hub selection | Incorrect reachable set for that place | Mitigated by manual validation |
| Outdated station_id | API lookup fails, falls back to coordinates | Monitor after SBB infra changes |
| API rate limits | Generation fails mid-run | Prefilter reduces calls; retry logic needed |
| Timetable currency | File reflects point-in-time snapshot | Annual refresh required |
