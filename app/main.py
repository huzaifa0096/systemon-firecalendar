"""National calendar backed by the verified Pakistan monthly series."""
from datetime import date
from pathlib import Path
import csv
import io
import math

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="FireCalendar")
with (ROOT / "data/pakistan_harmonized_monthly.csv").open(newline="") as source:
    MONTHS = [
        dict(month=r["month"], harmonized=int(r["harmonized"]), source=r["source"],
             median_2001_2024=float(r["median_2001_2024"]), anomaly_pct=float(r["anomaly_pct"]))
        for r in csv.DictReader(source)
    ]


def select(start: str, end: str):
    try:
        first, last = [date.fromisoformat(value + "-01") for value in (start, end)]
    except ValueError:
        raise HTTPException(400, "Use YYYY-MM for the start and end months.")
    if first > last or start < MONTHS[0]["month"] or end > MONTHS[-1]["month"]:
        raise HTTPException(400, "Choose an ordered range from November 2000 to December 2025.")
    return [row for row in MONTHS if start <= row["month"] <= end]


@app.get("/api/pakistan/calendar")
def calendar(start: str = "2000-11", end: str = "2025-12"):
    select(start, end)
    first = date.fromisoformat(start + "-01")
    import calendar as dates
    last = date.fromisoformat(end + "-" + str(dates.monthrange(int(end[:4]), int(end[5:]))[1]))
    return {"region": "Pakistan", **science.calendar((60,23,79,38), first, last)}


@app.get("/api/pakistan/calendar.csv")
def download(start: str = "2000-11", end: str = "2025-12"):
    rows = calendar(start, end)["rows"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return Response(output.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="pakistan-{start}-{end}.csv"'
    })



from fastapi import Depends, Query
from fastapi.responses import StreamingResponse
from . import harmonize as science


import json
PAK_RING = json.loads((ROOT / "web/assets/pakistan-boundary.json").read_text())["coordinates"][0]


def overlaps_pakistan(west, south, east, north):
    # Clip the outline against each study-box edge.
    ring = PAK_RING
    for axis, edge, sign in [(0, west, 1), (0, east, -1), (1, south, 1), (1, north, -1)]:
        clipped = []
        for a, b in zip(ring[-1:] + ring[:-1], ring):
            inside_a = sign * (a[axis] - edge) >= 0
            inside_b = sign * (b[axis] - edge) >= 0
            if inside_a != inside_b:
                t = (edge - a[axis]) / (b[axis] - a[axis])
                clipped.append([x + t * (y - x) for x, y in zip(a, b)])
            if inside_b:
                clipped.append(b)
        ring = clipped
    return len(ring) >= 3


def area(west:float=69.3,south:float=27.7,east:float=75.4,north:float=34.0,
         start:date=date(2000,11,1),end:date=date(2025,12,31)):
    if not (-180<=west<east<=180 and -90<=south<north<=90):
        raise HTTPException(400,"Enter valid west, south, east and north bounds.")
    if not (60<=west<east<=79 and 23<=south<north<=38 and overlaps_pakistan(west,south,east,north)):
        raise HTTPException(400,"Choose a study area in Pakistan.")
    if not date(2000,11,1)<=start<=end<=date(2025,12,31):
        raise HTTPException(400,"Choose dates within November 2000 through December 2025.")
    return (west,south,east,north), start, end


def season(months:str="10,11"):
    try:
        values=tuple(sorted(set(int(x) for x in months.split(","))))
        if not values or not all(1<=m<=12 for m in values):
            raise ValueError
        return values
    except ValueError:
        raise HTTPException(400,"Enter season months as numbers from 1 to 12, separated by commas.")


@app.get("/api/calendar")
def region_calendar(view=Depends(area)):
    return science.calendar(*view)


@app.get("/api/summary")
def summary(view=Depends(area)):
    rows = science.calendar(*view)["rows"]
    peak = max(rows,key=lambda r:r["harmonized"])
    totals={}
    for row in rows:
        totals[row["year"]]=totals.get(row["year"],0)+row["harmonized"]
    return dict(total=sum(totals.values()),peak_month=peak["month"],peak_year=max(totals,key=totals.get),current_anomaly_pct=rows[-1]["anomaly_pct"])


@app.get("/api/trust")
def region_trust(view=Depends(area),months=Depends(season)):
    return science.trust(*view,months)


@app.get("/api/policy_check")
def region_policy(view=Depends(area),months=Depends(season),policy_year:int=Query(2024,ge=2001,le=2025),years:int=Query(2,ge=1,le=10)):
    return science.policy(*view,months,policy_year,years)


@app.get("/api/calendar.csv")
def regional_csv(view=Depends(area)):
    rows=science.calendar(*view)["rows"]
    output=io.StringIO()
    writer=csv.DictWriter(output,fieldnames=rows[0].keys() if rows else ["month", "harmonized", "source"])
    writer.writeheader()
    writer.writerows(rows)
    return Response(output.getvalue(),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=calendar.csv"})


@app.get("/api/hotspots.csv")
def hotspots(view=Depends(area)):
    box,start,end=view
    data=science.selection(box)
    columns=["date","lat","lon","sensor","satellite","hhmm_utc","daynight","frp","type"]
    data=data.loc[data.date.between(str(start),str(end)),columns]
    def chunks():
        yield ",".join(columns)+"\n"
        for i in range(0,len(data),10000):
            yield data.iloc[i:i+10000].to_csv(index=False,header=False)
    return StreamingResponse(chunks(),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=hotspots.csv"})


@app.get("/api/map/history")
def map_history(month: str, west: float = 60, south: float = 23,
                east: float = 79, north: float = 38):
    import calendar as dates
    select(month, month)
    start = date.fromisoformat(month + "-01")
    end = date(start.year, start.month, dates.monthrange(start.year, start.month)[1])
    box, _, _ = area(west, south, east, north, start, end)
    points = science.selection(box)
    points = points.loc[points.date.between(str(start), str(end))]
    total = len(points)
    sample = points.sort_values("frp", ascending=False, na_position="last").head(2000)
    features = []
    for row in sample.itertuples():
        power = float(row.frp)
        features.append({"geometry": {"x": float(row.lon), "y": float(row.lat)},
                         "attributes": {"acq_time": int(row.date.timestamp() * 1000),
                                        "observation_date": str(row.date.date()),
                                        "satellite": str(row.satellite), "confidence": str(row.confidence),
                                        "frp": power if math.isfinite(power) else None,
                                        "daynight": str(row.daynight)}})
    return {"features": features, "total": total, "month": month,
            "exceededTransferLimit": total > len(features)}


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
