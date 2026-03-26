import json
from pathlib import Path

origin_path = Path("data_processed/bfs/bfs_origin_split_2025.json")
supply_path = Path("data_processed/bfs/bfs_supply_demand_2025.json")

with origin_path.open("r", encoding="utf-8") as f:
    origin = json.load(f)

with supply_path.open("r", encoding="utf-8") as f:
    supply = json.load(f)

origin_slugs = {row["slug"] for row in origin}
supply_slugs = {row["slug"] for row in supply}

print("Only in origin:")
print(sorted(origin_slugs - supply_slugs))

print("\nOnly in supply:")
print(sorted(supply_slugs - origin_slugs))