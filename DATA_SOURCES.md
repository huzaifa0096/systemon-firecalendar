# Data sources and reproducibility

FireCalendar uses NASA FIRMS Standard Processing country-year CSV files for Pakistan:

- MODIS Terra/Aqua: 2000–2025.
- VIIRS Suomi NPP: 2012–2025.
- VIIRS NOAA-20 (JPSS-1): 2018–2025.

The archive covers November 2000 through December 2025. It does not provide a 2026 archive or live observations.

Source: https://firms.modaps.eosdis.nasa.gov/country/

Exact download URL pattern:

`https://firms.modaps.eosdis.nasa.gov/data/country/{source}/{year}/{source}_{year}_Pakistan.csv`

Here `source` is `modis`, `viirs-snpp` or `viirs-jpss1`.

To download the inputs again from the project root:

```sh
python scripts/download_data.py --country Pakistan --start 2000 --end 2025
python scripts/build_parquet.py --check
python scripts/build_parquet.py
```

Existing CSVs are skipped by the download script. The optional Parquet file accelerates point loading. The prepared calibration cell-day table and date metadata are included in `data/calibration`. Their use and smoothing parameters are implemented in `app/calibration.py`.

Analysis keeps vegetation-fire detections (`type = 0`), MODIS confidence >= 30 and nominal/high VIIRS confidence. Raw CSVs contain the original downloaded rows; filtering occurs during analysis. Detection counts are not counts of distinct fire incidents or burned area.

Map imagery and labels: Esri. Street tiles: OpenStreetMap contributors (https://www.openstreetmap.org/copyright). Basemap tiles and place search need internet access. The basemap does not show historical imagery for the selected archive month.
