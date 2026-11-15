# FireCalendar — submission preparation

Status: prepared draft; not submitted to NASA Space Apps.

## Project name

FireCalendar

## High-level summary

FireCalendar helps users explore Pakistan's seasonal fire activity from November 2000 to December 2025. MODIS and VIIRS detect fires at different spatial resolutions, so joining their raw counts can introduce a sensor-related discontinuity. We count common fire cell-days and use overlapping observations to estimate local, month-specific calibration factors on the Suomi NPP reference scale. An interactive map, monthly calendar, anomaly view and exports make the record accessible. Area-specific held-out validation and observation limitations help users interpret the reconstructed values.

## Detailed description

Users select an area in Pakistan, explore monthly archived hotspots, and inspect harmonized activity, seasonal patterns and unusual months. Rectangle selection links the map to an area briefing. The application also provides a seasonal Trust Meter, descriptive before/after comparisons, and CSV/PNG exports.

Each product is counted in distinct 0.01-degree fire cell-days. Local 1-degree calibration cells and calendar-month ratios relate source sensors to S-NPP. Sparse cells borrow strength from regional ratios through smoothing. The method is evaluated by leaving out an overlap year, fitting on the remaining years and comparing reconstructed values with observed S-NPP values. Validation is reported for the selected area, alongside a national-ratio baseline. Performance varies by area; local calibration is not always better.

The interface is built with HTML, CSS, JavaScript and Leaflet. The Python API uses FastAPI, pandas and NumPy, with Parquet support through PyArrow. The repository includes the required Pakistan archive and local startup instructions.

The product supports exploration and communication of seasonal fire activity. It does not estimate burned perimeter, prove policy causation, provide cloud-free coverage, or eliminate every sensor difference. Reconstruction error bands are model-error bands, not statistical confidence intervals.

## NASA data

NASA FIRMS Standard Processing MODIS Terra/Aqua, VIIRS Suomi NPP and VIIRS NOAA-20 country-year observations for Pakistan. See DATA_SOURCES.md for URLs and filters.

## Other resources

Credit Esri imagery/labels, OpenStreetMap contributors, Leaflet and the open-source Python dependencies. Retain applicable third-party notices.

## Remaining submission checklist

- Verify all registered team members and the exact selected challenge on the official team page.
- Add a public final-project repository URL to the form.
- Supply a separate public English demo: at most 7 slides including title/closing slides, or a video of at most 30 seconds with English subtitles.
- Include actual team names, challenge, project image, user experience and NASA-data use in the demo.
- Check both links without login or permission requests.
- Review every numerical claim against the delivered application's results.
- Review source credits and required declarations.
- Submit only when the team explicitly authorizes final submission; verify the confirmation banner.

The Karachi organizer's email gives a website deadline of 15 November 2026 at 11:59 PM Pakistan time. Local presentation is separate: 7 minutes presenting and 3 minutes for questions, with attendance required before judging at 4 PM. This document does not register attendance or submit anything.
