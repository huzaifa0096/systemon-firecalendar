"""Prepare the FireCalendar point dataset, or audit its inputs without Parquet packages."""
import argparse
from collections import Counter
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SENSORS = {"modis": "MODIS", "viirs-snpp": "VIIRS_SNPP", "viirs-jpss1": "VIIRS_NOAA20"}


def read_points(path, sensor):
    raw = pd.read_csv(path, dtype={"confidence": str}, parse_dates=["acq_date"])
    date = raw.acq_date.dt
    valid = (pd.to_numeric(raw.confidence) >= 30 if sensor == "MODIS"
             else raw.confidence.isin(["n", "h"]))
    lat_cell = np.floor(raw.latitude / 0.01).astype(int).astype(str)
    lon_cell = np.floor(raw.longitude / 0.01).astype(int).astype(str)
    return pd.DataFrame({
        "date": date.date, "year": date.year, "month": date.month,
        "lat": raw.latitude, "lon": raw.longitude, "sensor": sensor,
        "conf_ok": valid, "type": raw.type, "frp": raw.frp, "daynight": raw.daynight,
        "satellite": raw.satellite, "hhmm_utc": raw.acq_time, "cell_1km": lat_cell + "_" + lon_cell,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate and count inputs only")
    args = parser.parse_args()
    if not args.check:
        import pyarrow as pa
        import pyarrow.parquet as pq

    sources = []
    for folder, sensor in SENSORS.items():
        files = sorted((ROOT / "data/raw" / folder).glob("*.csv"))
        if not files:
            parser.error(f"No CSVs in data/raw/{folder}")
        sources.extend((path, sensor) for path in files)
    destination = ROOT / "data/processed/hotspots.parquet"
    totals = Counter()
    writer = None
    if not args.check:
        destination.parent.mkdir(parents=True, exist_ok=True)
    with (nullcontext() if args.check else TemporaryDirectory(dir=destination.parent)) as temp:
        output = None if args.check else Path(temp) / "hotspots.parquet"
        try:
            for path, sensor in sources:
                points = read_points(path, sensor)
                if points.empty or points.isna().any().any():
                    raise ValueError(f"Empty file or missing fields in {path.name}")
                if not (points.lat.between(-90, 90) & points.lon.between(-180, 180)).all():
                    raise ValueError(f"Invalid coordinates in {path.name}")
                for year, count in points.groupby("year").size().items():
                    totals[sensor, year] += int(count)
                if not args.check:
                    table = pa.Table.from_pandas(points, preserve_index=False)
                    if writer is None:
                        writer = pq.ParquetWriter(output, table.schema, compression="zstd")
                    writer.write_table(table)
        finally:
            if writer is not None:
                writer.close()
        if not args.check:
            if pq.ParquetFile(output).metadata.num_rows != sum(totals.values()):
                raise ValueError("Output row count differs from input")
            output.replace(destination)
    for (sensor, year), count in sorted(totals.items()):
        print(sensor, year, count)
    for sensor in SENSORS.values():
        print(sensor, sum(n for (s, y), n in totals.items() if s == sensor))
    print(f"{len(sources)} files, {sum(totals.values()):,} rows")


if __name__ == "__main__":
    main()

