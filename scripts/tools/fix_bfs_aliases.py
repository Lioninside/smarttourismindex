import json
from pathlib import Path

mapping_path = Path("metadata/place_mapping.json")

with mapping_path.open("r", encoding="utf-8") as f:
    mapping = json.load(f)

aliases = {
    "Brienz (BE)": "Brienz",
    "Buchs (SG)": "Buchs",
    "Eschenbach (SG)": "Eschenbach",
    "Küssnacht (SZ)": "Küssnacht",
    "Teufen (AR)": "Teufen",
    "Wil (SG)": "Wil",
    "Moutier (JU)": "Moutier (BE)",
}

for alias, target in aliases.items():
    if target not in mapping:
        print(f"Missing target in mapping: {target}")
        continue

    entry = dict(mapping[target])

    # small canton correction for Moutier
    if alias == "Moutier (JU)":
        entry["canton"] = "JU"
        entry["name"] = "Moutier"

    mapping[alias] = entry

with mapping_path.open("w", encoding="utf-8") as f:
    json.dump(mapping, f, ensure_ascii=False, indent=2)

print("Updated place_mapping.json with BFS aliases.")
print("Added aliases:")
for alias in aliases:
    print(" -", alias)