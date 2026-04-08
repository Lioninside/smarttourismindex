# Smart Tourism Index – Public Transport Reachability Matrix
## Engineering Handover and Knowledge Documentation

**Audience:** Senior Developer, Senior Director  
**Prepared:** 2026-04-02  
**Purpose:** Transfer-ready technical and methodological documentation for a new chat, a new engineer, or future project knowledge.

---

## 1. Executive Summary

This project builds a municipality-level public-transport reachability graph for the Smart Tourism Index.

The target output is a JSON adjacency structure:

```json
{
  "bellinzona": ["locarno", "lugano", "biasca"],
  "luzern": ["zug", "schwyz", "engelberg", "interlaken"]
}
```

Meaning: from municipality `bellinzona`, the listed municipalities from the curated project list are reachable by public transport within 1 hour.

The final agreed architecture is:

1. Maintain a correct municipality master file.
2. Assign one correct representative PT node per municipality.
3. Validate those nodes against the timetable API and preserve `station_id`.
4. Restrict the municipality universe to the BFS overnight-coverage scope where required.
5. Use a 100 km coordinate prefilter.
6. Verify only the remaining candidate OD pairs via API.
7. Export a JSON adjacency list.

This architecture replaced an earlier, more naive all-pairs approach that was technically possible but methodologically weak and operationally inefficient.

---

## 2. Business Objective

The Smart Tourism Index needs a comparable measure of public-transport accessibility between municipalities.

This is **not** a system to:
- discover all Swiss stations within 1 hour,
- crawl the entire network,
- or build a generic timetable graph.

It **is** a system to:
- measure reachability among a curated list of tourism-relevant municipalities,
- using meaningful representative PT hubs,
- validated against a real timetable API.

---

## 3. Core Design Principles

### 3.1 The list of places is curated
The project works on a fixed municipality list in `places_master.csv`.

### 3.2 Station choice is a business rule, not just a technical lookup
A municipality must not be represented by:
- Talstation,
- Bergbahn,
- funicular stop,
- tourist stop,
- random side stop,
- accidental fuzzy match.

The representative PT node should normally be:
1. the main rail station in the municipality,
2. otherwise a central bus hub,
3. otherwise a functionally appropriate nearby hub if the municipality itself lacks a strong PT node.

### 3.3 API-valid does not mean methodologically correct
A stop can resolve perfectly and still be the wrong node for the index.

### 3.4 Coordinates are a prefilter only
Coordinates are used to reduce impossible OD pairs before API checks.
They are not the final accessibility result.

---

## 4. Sources Used

### 4.1 Internal working files
Main files used during development:
- `places_master.csv`
- `ManuallyReviewed_manualReviewDone.CSV`
- `doublecheck_full.csv`
- `places_master_merged.csv`
- `places_master_merge_issues.csv`
- `reachable_within_60m.json`

### 4.2 External PT API documentation
- search.ch timetable API  
  https://search.ch/timetable/api/help.en.html
- Transport Open Data API  
  https://transport.opendata.ch/docs.html

### 4.3 BFS scope source
- BFS PXWeb portal  
  https://www.pxweb.bfs.admin.ch

---

## 5. What Was Tried, What Worked, What Failed

## 5.1 Initial full matrix concept

The original idea was straightforward:
- take all municipalities,
- resolve a station,
- check all other municipalities,
- build a 193×193 or similar matrix.

### Why it looked good
- conceptually simple,
- easy to explain,
- obvious graph output.

### Why it was rejected in naive form
The station matching quality was not reliable enough.
A full matrix built on wrong stations would look precise but be wrong.

### Conclusion
Master-data cleanup had to come first.

---

## 5.2 Station resolution phase

A station-resolution script was built to map municipalities to timetable-recognized PT nodes.

### Main problem observed
The API often returned technically valid but methodologically poor stations.

Examples encountered:
- `Aeschi bei Spiez -> Spiez, Schiffstation`
- `Interlaken -> Interlaken, Heimwehfluhbahn`
- `Hasliberg -> Hasliberg Twing (Gondelbahn)`
- `Langnau im Emmental -> Marbach (Talstation)`
- `Buchs -> Kirchberg-Alchenflüh, Bahnhof`

These matches are valid in API terms but wrong for the project.

### Outcome
The process changed from automatic matching to:
- first-pass automation,
- then manual review,
- then API revalidation.

This was the correct decision.

---

## 5.3 API throttling / 429

Repeated `HTTP 429` errors occurred.

### Meaning
The API rate-limited the process because too many requests were sent in too little time.

### Important interpretation
This is **not** a data problem.
It is a temporary API-throttling problem.

### What helped
- more delay between requests,
- retry logic,
- rerunning only failed rows.

### What did not solve the real issue
Slowing requests does not fix bad methodology.
A wrong station remains wrong even if the request succeeds.

---

## 5.4 Manual review became decisive

The project then created:
- `ManuallyReviewed_manualReviewDone.CSV`

### Critical insight
In that file, the **correct reviewed station** was stored in:
- `api_resolved_name`

The legacy column:
- `main_station_name`
often still contained the old, incorrect value.

This was a major turning point.

### Consequence
Later revalidation scripts had to validate:
- `api_resolved_name`
and not the historical `main_station_name`.

This was initially misunderstood and later corrected.

---

## 5.5 `doublecheck.py` evolution

### Original intent
Revalidate the reviewed station list and refresh station IDs.

### Problem
A version of the script still validated the wrong field.
It validated `main_station_name` instead of the reviewed `api_resolved_name`.

### Additional technical issue
Merge collisions created suffixed columns like:
- `api_status_x`
- `api_status_y`

This caused:
- `KeyError: 'api_status'`

### Fix
The script was corrected to:
- use `api_resolved_name` as the field to validate,
- drop previously generated result columns before recomputing,
- regenerate fresh `api_resolved_id`, `api_status`, and `api_flag`.

This is the correct design.

---

## 5.6 Merge back into the master

### Goal
Turn `places_master.csv` into the real source of truth for all downstream scripts.

### Agreed merge logic
- preserve original station as `main_station_name_original`
- overwrite `main_station_name` with the reviewed station
- add `station_id`

### Why this mattered
Many scripts depend on `places_master.csv`.
The master had to become operationally correct.

---

## 5.7 Final merge outcome

The final merge and validation produced:
- Master rows: 185
- Merged rows: 185
- Unique names: 185
- Validated stations: 183 OK
- Remaining issues: 2 `HTTP_429`

Those two rows were then inspected manually.

### Two issue rows
1. `Chur`
   - problem was only API throttling
   - station itself was fine

2. `Matten bei Interlaken`
   - exposed a real methodological choice

### Final decision for Matten bei Interlaken
Final agreed representative hub:
- `Matten bei Interlaken -> Interlaken West`
- station ID: `8507496`

Reason:
- functionally much stronger for accessibility,
- better than a weak local stop,
- better than tourist or funicular-related stops.

At this point, Step 1 was effectively complete.

---

## 6. BFS Coverage Alignment

The project also needed alignment with the BFS overnight-coverage scope.

### Direct comparison result
The following names from the master did not appear directly in the BFS-covered list:
- Bergün
- Guarda
- Soglio
- Splügen
- Tschiertschen
- Viano
- Zuoz
- Sempach

### Discussion
Two options were considered:
1. exclude them,
2. map them to their BFS parent / merged municipality where applicable.

### Theoretical mappings discussed
- Bergün -> Bergün Filisur
- Guarda -> Scuol
- Soglio -> Bregaglia
- Splügen -> Rheinwald
- Tschiertschen -> Arosa
- Viano -> Brusio

### Practical scripted remaps actually requested at that stage
- `Soglio -> Bregaglia`
- `Splügen -> Rheinwald`

Important: BFS alignment is a methodology layer, not just a technical cleanup.

---

## 7. Why the naive full OD matrix was rejected

A first JSON builder checked each municipality against all others in the CSV and used chunked API calls.

### Problem discovered
With about 185 places and chunk size 30, the run implied about 1295 API batches.

That was too high.

### Why this mattered
Even though the logic was correct in terms of “only compare places from the CSV”, it was not efficient enough operationally.

### Conclusion
The pipeline needed a prefilter before API verification.

---

## 8. Final agreed production architecture: 100 km prefilter + API verification

### Final logic
For each origin:
1. compute air-line distance to every other place in the CSV,
2. keep only candidates within 100 km,
3. send only those to the API,
4. keep only destinations with `min_duration <= 3600`.

### Why this is better
It avoids:
- checking obviously implausible long-distance pairs,
- too many API calls,
- dense OD logic that adds cost but little value.

### Important clarification
This does **not** ignore the full place list.
It means:
- all places are considered in the geographic prefilter,
- only the reduced candidate set is API-checked.

That was explicitly confirmed and accepted.

---

## 9. Files and Their Roles

### `places_master.csv`
Production master.
Expected final contents:
- municipality metadata,
- corrected `main_station_name`,
- validated `station_id`,
- coordinates,
- optionally `main_station_name_original`.

### `ManuallyReviewed_manualReviewDone.CSV`
Manual review working file.
Critical semantic note:
- corrected station lived in `api_resolved_name`.

### `doublecheck_full.csv`
Station revalidation output.

### `places_master_merged.csv`
Merged corrected master candidate.

### `places_master_merge_issues.csv`
Rows still showing issues after merge, usually due to:
- `HTTP_429`,
- or a genuine station problem.

### `reachable_within_60m.json`
Final target graph output.

---

## 10. Key lessons learned

### 10.1 Station matching is the hardest part
The most difficult part was not the API call itself, but choosing the right representative PT node per municipality.

### 10.2 A correct API result can still be wrong for the index
A station can be formally valid and still not be a good municipal proxy.

### 10.3 Preserve original values
Keeping `main_station_name_original` is valuable for traceability and debugging.

### 10.4 Prefer IDs over names
Downstream logic should prefer `station_id` whenever possible.

### 10.5 Full pairwise checking is too expensive without candidate reduction
The 100 km prefilter is an important engineering compromise.

### 10.6 BFS alignment is a domain rule
It needs to be documented explicitly.

---

## 11. What worked well

The following worked:
- manual review of station assignments,
- preserving the master as central file,
- adding `station_id`,
- revalidating stations after manual correction,
- distinguishing real data problems from `HTTP_429`,
- catching merge-column collisions,
- introducing the 100 km prefilter,
- restricting reachability to the curated municipality list.

---

## 12. What did not work or had to be revised

The following did not work well:
- blind automatic station matching,
- trusting the original `main_station_name`,
- validating the wrong reviewed column,
- dense API matrix logic without candidate reduction,
- assuming all API failures were data failures,
- using weak or tourist stops as municipality proxies.

---

## 13. Remaining risk categories

Main residual QA risks:
1. suboptimal hub selection,
2. coordinate errors affecting the 100 km prefilter,
3. station-name / station-ID mismatch,
4. unresolved BFS edge cases,
5. the 100 km radius excluding rare but fast rail connections.

---

## 14. Recommended production data model

Minimum production fields:
- `slug`
- `name`
- `canton`
- `tourism_region`
- `lat`
- `lon`
- `center_lat`
- `center_lon`
- `main_station_name`
- `station_id`
- `place_type`
- `active`

Recommended additional traceability field:
- `main_station_name_original`

---

## 15. Recommended production workflow

### Phase A – master maintenance
- maintain municipality list,
- maintain BFS scope,
- maintain representative PT node,
- refresh station ID.

### Phase B – validation
- validate the final station field,
- refresh station ID,
- flag suspicious choices.

### Phase C – reachability generation
- prefilter by 100 km,
- verify candidates via API,
- generate JSON adjacency output.

### Phase D – downstream usage
- use reachability graph in the Smart Tourism Index,
- use it for accessibility metrics or visualizations.

---

## 16. Transfer note for a new chat or new engineer

A new engineer or new chat must be told immediately:

> The master-data cleanup phase is complete or near-complete.  
> `places_master.csv` is intended to be the authority for municipalities, representative PT stations, and station IDs.  
> Earlier review files often stored the corrected station under `api_resolved_name`, not under the legacy `main_station_name`.  
> The production reachability logic is not a full station-discovery problem.  
> It is:
> 1. curated municipality list,
> 2. 100 km coordinate prefilter,
> 3. API verification,
> 4. JSON adjacency list of municipalities reachable within 1 hour.

Also state the main pitfalls:
- automatic matching was frequently methodologically wrong,
- `HTTP_429` occurred and does not imply bad data,
- BFS and tourism place lists are not always identical,
- Interlaken-area and municipality-merger cases required special judgment.

---

## 17. Current status at end of this phase

### Completed
- station review methodology established,
- manually reviewed station list created,
- corrected merge logic established,
- corrected station IDs moved back into the master,
- BFS overlap checked,
- selected BFS remaps clarified,
- prefilter-based architecture agreed,
- JSON output format defined.

### Ready next
- run the final production reachability build using:
  - cleaned `places_master.csv`,
  - 100 km prefilter,
  - API verification,
  - JSON export.

---

## 18. Recommended technical improvements

Optional but recommended:
- diagnostic JSON with candidate counts and reachable counts,
- checkpoint/resume support,
- one-row revalidation utility,
- sensitivity testing for 80 / 100 / 120 km radius,
- unit tests around merge logic.

---

## 19. Final recommendation

The most important strategic decision in this work was not an optimization, but the shift from:
- blind automatic station matching,
to:
- governed, reviewed municipal PT representation.

That decision materially improves the credibility of the final Smart Tourism Index accessibility layer.

`places_master.csv` should be treated as a governed asset, not as a disposable preprocessing file.

---

## 20. Short chronology

1. Initial idea: direct matrix via API.
2. Realization: station quality too poor.
3. Station-resolution tooling built.
4. Encountered 429 errors and bad auto-matches.
5. Manual review file created.
6. Realized corrected stations lived in `api_resolved_name`.
7. Corrected revalidation logic.
8. Merged corrected stations and IDs back into master.
9. Compared list with BFS-covered municipalities.
10. Clarified specific municipality remaps.
11. Dense OD API approach proved too heavy.
12. Switched to 100 km prefilter + API verification.
13. Finalized JSON adjacency output design.

---

## 21. Important remembered examples

- `Matten bei Interlaken -> Interlaken West (8507496)`
- `Soglio -> Bregaglia` for BFS-alignment logic
- `Splügen -> Rheinwald` for BFS-alignment logic
- `Buchs` required explicit protection against wrong-name matching
- not every `Post` or `Dorf` stop is wrong, but each one must be intentional

---

## 22. References

- search.ch Timetable API documentation: https://search.ch/timetable/api/help.en.html
- Transport Open Data API documentation: https://transport.opendata.ch/docs.html
- BFS PXWeb portal: https://www.pxweb.bfs.admin.ch
