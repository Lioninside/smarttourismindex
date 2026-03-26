from pathlib import Path
import geopandas as gpd

gpkg_path = Path("data_raw/osm/osm_switzerland.gpkg")

layers = gpd.list_layers(gpkg_path)

print("Layers in OSM GeoPackage:")
print(layers)

print("\nLayer names only:")
for layer in layers["name"]:
    print(layer)