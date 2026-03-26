import json
from collections import Counter
from pathlib import Path

files = [
    Path("data_processed/bfs/bfs_origin_split_2025.json"),
    Path("data_processed/bfs/bfs_supply_demand_2025.json"),
]

for path in files:
    with path.open("r", encoding="utf-8") as f:
        rows = json.load(f)

    counts = Counter(row["slug"] for row in rows)
    duplicates = {slug: count for slug, count in counts.items() if count > 1}

    print(f"\n{path.name}")
    print(f"rows: {len(rows)}")
    print(f"unique slugs: {len(counts)}")
    print("duplicates:", duplicates)