# FireCalendar by SystemON

Pakistan fire-season observatory for the NASA International Space Apps Challenge.

## Run locally

Requires Python 3.11 or later. Create a virtual environment, install requirements.txt, then run the following command from the project folder.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On macOS/Linux, activate with `source .venv/bin/activate` instead.

    python -m uvicorn app.main:app --host 127.0.0.1 --port 8010

Open http://127.0.0.1:8010/. On Windows, Start-FireCalendar.cmd also launches the application.

The repository includes the Pakistan source CSVs and the prepared calibration table. No NASA API key is required. The first area request loads the archive and can take longer than subsequent requests. An optional preprocessing step is `python scripts/build_parquet.py`; otherwise the application reads the included CSVs directly. The localhost address works only on the computer running the server.

## Features

- Satellite map with Pakistan place search, rectangle selection and fullscreen.
- Monthly historical timeline and playback.
- Harmonized fire calendar, anomaly chart and CSV/PNG exports.
- Selected-area briefing, sensor source and area-specific validation.
- Seasonal Trust Meter and descriptive policy comparisons.

## Calculations

Historical coverage runs from November 2000 through December 2025. The included archive contains filtered NASA FIRMS vegetation-fire detections from MODIS Terra/Aqua, VIIRS Suomi NPP and NOAA-20.

All products use distinct 0.01-degree fire cell-days, approximately a 1-km grid whose dimensions vary with latitude. Local 1-degree calibration cells and calendar-month ratios link products to the Suomi NPP reference, with sparse cells shrunk toward regional ratios. Terra-only reconstruction uses the 2012-2019 overlap period.

Leave-one-year-out validation is calculated for each selected area. Method shows local calibration alongside a national-ratio baseline in the same unit. Policy comparisons use measured seasonal prediction error. They describe changes and do not establish causation.

Anomalies compare each calendar month with other complete years, excluding the assessed year. Partial months have no percentage anomaly. CSV reconstruction error bands are not confidence intervals.

## Map and data availability

The map displays archived NASA FIRMS observations from November 2000 through December 2025 over a current basemap. Dense historical views display the strongest 2,000 detections and report the full count separately. Esri provides satellite imagery and place labels. OpenStreetMap provides the street layer. Internet is required for basemap tiles and place search; historical fire analysis uses local files.

Detections do not represent confirmed incidents or burned perimeters. Clouds, smoke, overpass times and viewing geometry affect detection. Cloud-free coverage is unavailable. Province presets use approximate rectangles.

## Structure

- app/main.py provides the API and serves the interface.
- app/harmonize.py provides area analysis, trust and policy calculations.
- app/calibration.py provides local calibration and validation.
- data/calibration contains the prepared cell-day table and platform date metadata.
- data/raw contains source Pakistan CSV files for point analysis and exports.
- web contains the interface and Pakistan boundary asset.
- scripts contains data preparation utilities.

## Sources

- NASA FIRMS https://firms.modaps.eosdis.nasa.gov/
- NASA GIBS https://www.earthdata.nasa.gov/
- Esri https://www.esri.com/
- OpenStreetMap https://www.openstreetmap.org/copyright

NASA FIRMS source CSV URLs and a repeatable download command are documented in [DATA_SOURCES.md](DATA_SOURCES.md). Third-party data and map assets retain their providers' terms and attribution requirements.

The application is an analysis prototype, not an operational fire warning service.
