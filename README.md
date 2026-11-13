# FireCalendar development handoff

## Product and scope

A responder, land manager or researcher selects a geographic rectangle and date range to explore monthly satellite fire detections on a comparable scale. The first delivery covers Pakistan from November 2000 through December 2025. Punjab and Sindh presets are approximate rectangles. Outside the loaded country, show a coverage message. Treat calendar months before coverage begins as missing. A detection measures a hot pixel at an overpass. Multiple detections can come from the same fire.

The three product features in the agreed brief are the historical calendar, Trust Meter and Policy Claim Checker. The user can enter coordinates, draw a rectangle, inspect a selected year's anomalies, see summary cards, read the method and export filtered detections or monthly results. Live alerts, extra languages and global coverage are outside the first build.

## Evidence already in the folder

| Source | Files | Raw rows | Coverage |
|---|---:|---:|---|
| Terra/Aqua MODIS | 26 | 235,251 | 2000–2025 |
| Suomi NPP VIIRS | 14 | 828,913 | 2012–2025 |
| NOAA-20 VIIRS | 8 | 489,307 | 2018–2025 |

All 48 CSVs passed conversion to the unified in-memory schema. Monthly filtered MODIS counts and daily grid-deduplicated S-NPP counts matched the supplied Pakistan reference for the months checked. Re-running the reference model reproduced the saved 302 monthly records. November 2021 peaked at 10,954 harmonized detections. In the Punjab rectangle for October–November 2025 the filtered MODIS data contained 65 Terra and 2,310 Aqua detections, a 2.74% morning share. NOAA-20 is available for continuity research and raw exports. Keep it out of the S-NPP historical series to avoid counting two satellite streams together.

| File or directory | Use |
|---|---|
| CLAUDE.md | Authoritative local implementation brief, schema, endpoints, thresholds and UI choices |
| 1_SIMPLE_SAMJHO.md and 2_BUILD_PLAN.md | Roman Urdu introduction, tasks, roles, milestones and demo checklist |
| NASA_Challenge_Research_English and NASA_Challenge_Research_Complete (.md and .pdf) | English and Roman Urdu research packs, competitor comparisons, source links, pitch and limitations |
| RESEARCH.md | Earlier exploratory research and optional ideas; use the narrower scope in CLAUDE.md |
| data/raw and data/pakistan_monthly_hotspots_2000_2025.csv | Original point files and national sensor-count reference |
| data/pakistan_harmonized_monthly.csv and scripts/harmonize_demo.py | Expected calendar, historical median, anomaly and reproducible model |
| scripts/download_data.py and scripts/md_to_pdf.py | Reacquire country archives and render research documents |
| requirements.txt and .gitignore | Python dependencies and exclusions for raw data, generated data, credentials and environment |
| scripts/build_parquet.py | Audit inputs or create the unified point dataset |

## Local setup

Run these PowerShell commands from the project root on a machine with Python 3.11+ and package access. The downloaded Pakistan archive already covers the demo.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python scripts/build_parquet.py --check
.\.venv\Scripts\python scripts/build_parquet.py
.\.venv\Scripts\python -c "import duckdb; print(duckdb.read_parquet('data/processed/hotspots.parquet').aggregate('sensor, count(*)', 'sensor'))"
```

The build writes data/processed/hotspots.parquet. Verify the grouped counts against the table above. In the preparation environment Python 3.13, pandas and NumPy worked. PyPI DNS access failed, so DuckDB and PyArrow installation, Parquet serialization and its readback remain pending. The reference calculation and raw-data checks run without these packages.

## Implementation order and acceptance checks

1. **Calendar service.** Use FastAPI, DuckDB and the unified Parquet file. Filter vegetation detections (type 0), MODIS confidence at least 30, and nominal/high VIIRS confidence. Deduplicate S-NPP by day and approximate 0.01-degree cell. Fit each month's median S-NPP/MODIS ratio over 2012–2025, using the Pakistan fallback when fewer than five usable overlap years exist. Use the full area history for calibration and the 2001–2024 median even if the display requests one year. A short display range must produce the same result for a full month as a long range. Show unavailable anomalies when the baseline is zero.
2. **API and frontend.** Implement /api/calendar, /api/summary, /api/calendar.csv and /api/hotspots.csv, then serve plain HTML, CSS and JS at /. Use Leaflet with rectangle drawing and Plotly with a Viridis or Cividis heatmap. Test Pakistan, Punjab, Sindh, invalid bounds, partial months and an area with no coverage. Verify exports match the same selection. When the app exists, launch with python -m uvicorn app.main:app --reload --port 8000.
3. **Trust Meter.** Implement /api/trust. Compare latest seasonal Terra share and S-NPP night share with their 2012–2020 medians. Flag Terra below half the baseline or night share above 1.5 times the baseline. Zero, one and two scored flags correspond to High, Medium and Low. Sensor transitions are informational. Show insufficient observations explicitly. Use the Punjab example above as a regression case.
4. **Policy Claim Checker.** Implement /api/policy_check. Compare seasonal totals before and after a selected policy year, defaulting to two years on each side and October–November. Show years used, baseline, change and trust flags. Use complete seasons, flag incomplete windows and undefined denominators. The national model yielded r = 0.875 and 15.8% held-out prediction error. The code sums absolute monthly errors within each test year, divides by that year's observed total, then averages across years. This is a reference error for the proposed comparison rule. It supplies neither a statistical confidence interval nor proof that a policy caused a change.
5. **Demo and submission.** Check mobile layout, chart units, method explanation, CSV exports and venue connectivity for map tiles/CDN scripts. The folder proposes a 30-second walkthrough, slides, repository and optional deployment. Confirm the organizer's current resources, submission format and deadline before finalizing. The challenge page returned HTTP 502 during preparation.


## Run the observatory

Double-click Start-FireCalendar.cmd on Windows, then open http://127.0.0.1:8010/. The launch script uses the Python on PATH. With an isolated environment, run its Python with -m uvicorn app.main:app --port 8010 instead.

The current workspace implements the area calendar, both CSV exports, summary, seasonal Trust Meter and Policy Claim Checker. It opens on the Punjab rectangle and October–November season. The national reference endpoints remain available under /api/pakistan/. Point queries use the Parquet file when present or load the local Pakistan CSV archive into memory on first use. A rectangle can be drawn directly on the offline georeferenced MODIS density image or entered as coordinates. The chart and map work without CDN requests.

The national 302 monthly harmonized counts and anomalies were reproduced from points. Punjab's Oct–Nov 2025 Terra share is 65/2375 (2.74%). With policy year 2024 and two complete years on each side, the seasonal mean increased from 9,472.5 to 10,825.0 (+14.3%), within the national 15.8% reference error. Local held-out error is reported separately under Method. The before/after result is descriptive.

