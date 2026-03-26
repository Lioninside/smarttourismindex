import xarray as xr

files = [
    r"data_raw/climate/klimanormwerte-temperatur_aktuelle_periode_monthly_2056.nc",
    r"data_raw/climate/klimanormwerte-niederschlag_aktuelle_periode_monthly_2056.nc",
    r"data_raw/climate/klimanormwerte-sonnenscheindauer_aktuelle_periode_monthly_2056.nc",
]

for path in files:
    print("\n" + "=" * 80)
    print(path)

    ds = xr.open_dataset(path, decode_times=False)

    print("\nDATASET:")
    print(ds)

    print("\nCOORDS:")
    print(list(ds.coords))

    print("\nDIMS:")
    print(list(ds.dims))

    print("\nDATA_VARS:")
    print(list(ds.data_vars))

    for var in ds.data_vars:
        print("\n" + "-" * 40)
        print(f"VAR: {var}")
        print(ds[var])

    ds.close()