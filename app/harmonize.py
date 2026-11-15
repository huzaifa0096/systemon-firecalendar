"""Spatial analysis for the Pakistan FIRMS archive."""
from functools import lru_cache
from pathlib import Path
from threading import Lock

import numpy as np
import pandas as pd

from scripts.build_parquet import SENSORS, ROOT

MONTHS = pd.period_range("2000-11", "2025-12", freq="M")
LOCK = Lock()


@lru_cache(maxsize=1)
def archive():
    parquet = ROOT / "data/processed/hotspots.parquet"
    if parquet.exists():
        points = pd.read_parquet(parquet)
        points = points.loc[points.type.eq(0) & points.conf_ok]
        points["date"] = pd.to_datetime(points.date)
    else:
        frames = []
        for folder, sensor in SENSORS.items():
            for path in sorted((ROOT / "data/raw" / folder).glob("*_Pakistan.csv")):
                raw = pd.read_csv(path, usecols=["latitude","longitude","acq_date","acq_time","satellite","daynight","type","confidence","frp"])
                valid = raw.confidence.ge(30) if sensor == "MODIS" else raw.confidence.isin(["n","h"])
                frame = raw.loc[valid & raw.type.eq(0)].rename(columns={"latitude":"lat","longitude":"lon","acq_date":"date","acq_time":"hhmm_utc"})
                frame["sensor"] = sensor
                frames.append(frame)
        points = pd.concat(frames, ignore_index=True)
        points["date"] = pd.to_datetime(points.date)
    for col in ["sensor","satellite","daynight"]:
        points[col] = points[col].astype("category")
    points["period"] = points.date.dt.to_period("M")
    points["cell"] = (np.floor(points.lat / .01).astype("int64") * 100000 + np.floor(points.lon / .01).astype("int64"))
    return points


def selection(box):
    with LOCK:
        data = archive()
    w,s,e,n = box
    return data.loc[data.lon.between(w,e) & data.lat.between(s,n)]


@lru_cache(maxsize=1)
def engine():
    from .calibration import Engine
    return Engine()


@lru_cache(maxsize=24)
def model(box):
    from .calibration import anomalies
    with LOCK:
        eng = engine()
    area = eng.area(box)
    result = eng.series(area)
    complete = np.isfinite(result["H"]).all(axis=1)
    pct, rank, med = anomalies(result["H"], complete)
    validation = result["validation"].get("MODIS", {})
    ours = validation.get("ours", {})
    result.update(anomaly=pct, percentile=rank, median=med)
    result["validation_summary"] = {
        "r": ours.get("monthly_r"),
        "loyo_error_pct": ours.get("annual_error_pct_median"),
        "monthly_error_pct": ours.get("monthly_error_pct_median"),
        "years_tested": ours.get("years_tested", 0),
        "baseline": validation.get("baseline", {}),
        "metric": "Median absolute annual error in held-out years",
        "units": "VIIRS-equivalent fire cell-days",
    }
    return result


def calendar(box, start, end):
    from .calibration import LABEL
    result = model(box)
    eng = engine()
    periods = pd.period_range(str(start)[:7], str(end)[:7], freq="M")
    partial = set()
    if start.day != 1:
        partial.add(periods[0])
    if end.day != periods[-1].days_in_month:
        partial.add(periods[-1])
    adjusted = None
    if partial:
        w, s, e, n = box
        cd = eng.cd
        selected = cd[cd.lon.between(w, e) & cd.lat.between(s, n)
                      & cd.date.between(pd.Timestamp(start), pd.Timestamp(end))]
        adjusted = eng.series(eng.dense(selected))
    rows = []
    for p in periods:
        yi, mi = p.year - int(eng.years[0]), p.month - 1
        values = adjusted if p in partial else result
        value = values["H"][yi, mi]
        if not np.isfinite(value):
            continue
        src = result["src"][yi, mi]
        def number(v):
            return round(float(v), 1) if np.isfinite(v) else None
        rows.append(dict(
            month=str(p), year=p.year, mon=p.month,
            modis=number(values["raw"]["MODIS"][yi, mi]),
            viirs=number(values["raw"]["SNPP"][yi, mi]) if eng.coverage["SNPP"][yi, mi] else None,
            harmonized=round(float(value), 1), source=LABEL.get(src, src),
            median_2001_2024=number(result["median"][yi, mi]),
            baseline_median=number(result["median"][yi, mi]),
            lower=number(values["lo"][yi, mi]), upper=number(values["hi"][yi, mi]),
            partial=p in partial,
            anomaly_pct=number(result["anomaly"][yi, mi]) if p not in partial else None,
            percentile=number(result["percentile"][yi, mi]) if p not in partial else None,
        ))
    complete = np.isfinite(result["H"]).all(axis=1)
    normal = np.nanmedian(result["H"][complete], axis=0)
    return dict(rows=rows, bbox=box, k=eng.k_region.get("MODIS", np.zeros(12)).tolist(),
                k_source="local spatial calibration", climatology={m+1: float(v) for m,v in enumerate(normal)},
                validation=result["validation_summary"],
                units="VIIRS-equivalent fire cell-days", baseline="Same calendar month in other complete years",
                archive_detections=len(selection(box)))


def complete_years(start,end,months):
    return [y for y in range(start.year,end.year+1)
            if pd.Period(year=y,month=min(months),freq="M").start_time.date()>=start
            and pd.Period(year=y,month=max(months),freq="M").end_time.date()<=end]


@lru_cache(maxsize=48)
def seasonal_error(box, months):
    eng = engine()
    area = eng.area(box)
    errors = []
    mask = eng.overlap_mask("MODIS")
    indices = np.array(months) - 1
    for yi, coefficients in eng.k_loyo.get("MODIS", {}).items():
        if not mask[yi, indices].all():
            continue
        observed = area["SNPP"]["n"][:, yi, indices].sum()
        predicted = (area["MODIS"]["n"][:, yi] * coefficients)[:, indices].sum()
        if observed > 0:
            errors.append(abs(predicted - observed) / observed * 100)
    return round(float(np.median(errors)), 1) if errors else None


@lru_cache(maxsize=48)
def shares(box,months):
    data = selection(box)
    data = data[data.date.dt.month.isin(months)]
    def yearly(sensor,column,value):
        subset = data[data.sensor==sensor]
        return (subset[column].eq(value).groupby(subset.date.dt.year).mean()).to_dict()
    return yearly("MODIS","satellite","Terra"), yearly("VIIRS_SNPP","daynight","N")


def trust(box,start,end,months):
    terra,night = shares(box,months)
    years = complete_years(start,end,months)
    latest = years[-1] if years else None
    flags=[]
    missing=False
    for values,threshold,flag,title in [(terra,.5,"morning_collapse","Morning detection share fell"),(night,1.5,"night_shift","Night detection share rose")]:
        baseline=[v for y,v in values.items() if 2012<=y<=2020]
        current=values.get(latest)
        if len(baseline)<5 or current is None or np.median(baseline)<=0:
            missing=True
            continue
        median=float(np.median(baseline))
        triggered=current < threshold*median if threshold<1 else current > threshold*median
        if triggered:
            flags.append(dict(id=flag,title=title,detail=f"{latest}: {current:.1%} of detections. The 2012–2020 seasonal median was {median:.1%}."))
    score="Insufficient data" if missing else ["High","Medium","Low"][len(flags)]
    if start.year<2012<=end.year:
        flags.append(dict(id="sensor_switch",title="Historical sensor transition",detail="Pre-2012 values use calibrated MODIS estimates."))
    return dict(score=score,flags=flags,latest_year=latest,terra_share={y:v for y,v in terra.items() if y in years},night_share={y:v for y,v in night.items() if y in years})


def policy(box,start,end,months,year,window):
    result = calendar(box, start, end)
    series = pd.DataFrame(result["rows"])
    series.index = pd.PeriodIndex(series.month, freq="M")
    season = series.loc[series.mon.isin(months), "harmonized"]
    totals=season.groupby(season.index.year).sum()
    complete=complete_years(start,end,months)
    before=[y for y in complete if year-window<=y<year]
    after=[y for y in complete if year<=y<year+window]
    base=float(totals.loc[before].mean()) if before else None
    post=float(totals.loc[after].mean()) if after else None
    full = model(box)["H"][:, np.array(months) - 1]
    valid_seasons = np.isfinite(full).all(axis=1)
    historical=float(np.median(full[valid_seasons].sum(axis=1))) if valid_seasons.any() else None
    uncertainty = seasonal_error(box, months)
    change=100*(post/base-1) if base and post is not None else None
    evidence=trust(box,max(start,pd.Timestamp(year=year,month=1,day=1).date()),min(end,pd.Timestamp(year=year+window-1,month=12,day=31).date()),months)
    verdict="Insufficient data"
    if len(before)==window and len(after)==window and change is not None and evidence["score"]!="Insufficient data" and uncertainty is not None:
        verdict="Within reference error"
        if abs(change)>uncertainty:
            verdict=("Observed increase" if change>0 else "Observed reduction") if evidence["score"]=="High" else "Weak evidence"
    return dict(before_years=before,after_years=after,before_mean=base,after_mean=post,change_pct=change,
                vs_median_pct=100*(post/historical-1) if historical and post is not None else None,
                uncertainty_pct=uncertainty,trust=evidence,verdict=verdict)
