"""Spatial analysis for the Pakistan FIRMS archive."""
from functools import lru_cache
from pathlib import Path
from threading import Lock

import numpy as np
import pandas as pd

from scripts.build_parquet import SENSORS, ROOT

MONTHS = pd.period_range("2000-11", "2025-12", freq="M")
DEFAULTS = pd.Series([2.80, 2.65, 2.90, 3.11, 3.98, 6.78, 5.38, 3.67, 6.74, 5.86, 5.04, 4.04], index=range(1, 13))
LOCK = Lock()


@lru_cache(maxsize=1)
def archive():
    parquet = ROOT / "data/processed/hotspots.parquet"
    if parquet.exists():
        import duckdb
        with duckdb.connect() as con:
            points = con.execute("select * from read_parquet(?) where type=0 and conf_ok", [str(parquet)]).df()
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


def counts(points, index):
    modis = points[points.sensor == "MODIS"]
    viirs = points[points.sensor == "VIIRS_SNPP"].drop_duplicates(["date","cell"])
    return pd.DataFrame({"modis":modis.groupby("period").size(), "viirs":viirs.groupby("period").size()}).reindex(index).fillna(0).astype(int)


def ratios(overlap):
    ratio = overlap.viirs / overlap.modis
    by_month = ratio.groupby(ratio.index.month)
    fitted = by_month.median().where(by_month.size() >= 5).reindex(DEFAULTS.index)
    return fitted.fillna(DEFAULTS), fitted.notna()


@lru_cache(maxsize=24)
def model(box):
    data = selection(box)
    series = counts(data, MONTHS)
    overlap = series[(series.index.year >= 2012) & series.modis.gt(0)]
    k, fitted = ratios(overlap)
    series["estimate"] = np.where(series.index.year < 2012, series.modis * series.index.month.map(k), series.viirs)
    normal = series.loc["2001":"2024","estimate"].groupby(lambda p:p.month).median().round()
    errors = []
    for year, test in overlap.groupby(overlap.index.year):
        coeff, _ = ratios(overlap[overlap.index.year != year])
        if test.viirs.sum():
            errors.append((test.modis * test.index.month.map(coeff) - test.viirs).abs().sum() / test.viirs.sum())
    r = overlap.modis.corr(overlap.viirs) if len(overlap)>1 and overlap.min().ne(overlap.max()).all() else None
    return series, k, fitted, normal, {"r": None if pd.isna(r) else round(r,3), "loyo_error_pct":round(100*np.mean(errors),1) if errors else None}, len(data)


def calendar(box, start, end):
    series,k,fitted,normal,validation,n = model(box)
    selected = series.loc[str(start)[:7]:str(end)[:7]].copy()
    partial = set()
    if start.day != 1:
        partial.add(selected.index[0])
    if end.day != selected.index[-1].days_in_month:
        partial.add(selected.index[-1])
    if partial:
        data = selection(box)
        actual = counts(data[data.date.between(str(start),str(end))], selected.index)
        for period in partial:
            m,v = actual.loc[period]
            selected.loc[period] = [m,v,m*k[period.month] if period.year<2012 else v]
    rows=[]
    for p,row in selected.iterrows():
        median = int(normal[p.month])
        rows.append(dict(month=str(p),year=p.year,mon=p.month,modis=int(row.modis),viirs=int(row.viirs) if p.year>=2012 else None,
                         harmonized=int(np.rint(row.estimate)),source="MODIS × k" if p.year<2012 else "VIIRS S-NPP",
                         median_2001_2024=median,partial=p in partial,
                         anomaly_pct=round((row.estimate/median-1)*100,1) if median and p not in partial else None))
    return dict(rows=rows,bbox=box,k=k.to_dict(),k_source="bbox" if fitted.all() else "mixed" if fitted.any() else "default",
                climatology=normal.to_dict(),validation=validation,archive_detections=n)


def complete_years(start,end,months):
    return [y for y in range(start.year,end.year+1)
            if pd.Period(year=y,month=min(months),freq="M").start_time.date()>=start
            and pd.Period(year=y,month=max(months),freq="M").end_time.date()<=end]


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
    series,*_ = model(box)
    season=series[series.index.month.isin(months)].estimate
    totals=season.groupby(season.index.year).sum()
    complete=complete_years(start,end,months)
    before=[y for y in complete if year-window<=y<year]
    after=[y for y in complete if year<=y<year+window]
    base=float(totals.loc[before].mean()) if before else None
    post=float(totals.loc[after].mean()) if after else None
    historical=float(totals.loc[2001:2024].median())
    change=100*(post/base-1) if base and post is not None else None
    evidence=trust(box,max(start,pd.Timestamp(year=year,month=1,day=1).date()),min(end,pd.Timestamp(year=year+window-1,month=12,day=31).date()),months)
    verdict="Insufficient data"
    if len(before)==window and len(after)==window and change is not None and evidence["score"]!="Insufficient data":
        verdict="Within reference error"
        if abs(change)>15.8:
            verdict=("Observed increase" if change>0 else "Observed reduction") if evidence["score"]=="High" else "Weak evidence"
    return dict(before_years=before,after_years=after,before_mean=base,after_mean=post,change_pct=change,
                vs_median_pct=100*(post/historical-1) if historical and post is not None else None,
                uncertainty_pct=15.8,trust=evidence,verdict=verdict)
