from pathlib import Path
import geopandas as gpd

gdb_path = Path("data_raw/swisstopo/swissTLM3D_2026_LV95_LN02.gdb")

layers = gpd.list_layers(gdb_path)

print("Layers in GDB:")
print(layers)

print("\nLayer names only:")
for layer in layers["name"]:
    print(layer)