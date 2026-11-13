"""Demo: harmonize MODIS + VIIRS monthly hotspot counts (Pakistan) into one series.

Method (simple, explainable, good for a hackathon):
  1. Overlap period 2012-2025: both sensors observed the same area.
  2. For each calendar month m, fit a ratio k_m = median(VIIRS / MODIS) over the overlap years.
     (Per-month ratio because the VIIRS/MODIS ratio changes with season: small fires
      in wheat/rice stubble season are seen by VIIRS but often missed by MODIS.)
  3. Harmonized series in "VIIRS-equivalent" units:
       2000-2011 -> MODIS * k_m      (back-cast)
       2012-2025 -> VIIRS            (real VIIRS, more detail)
  4. Validation: leave-one-year-out -> predict VIIRS from MODIS, report error.
"""
import sys
import numpy as np
import pandas as pd

src = sys.argv[1] if len(sys.argv) > 1 else "data/pakistan_monthly_hotspots_2000_2025.csv"
out = sys.argv[2] if len(sys.argv) > 2 else "data/pakistan_harmonized_monthly.csv"

df = pd.read_csv(src)
df["year"] = df.month.str[:4].astype(int)
df["mon"] = df.month.str[5:7].astype(int)
M, V = "modis_filtered", "viirs_filtered_1km_dedup"

ov = df[(df.year >= 2012) & df[V].notna() & (df[M] > 0)].copy()
ov["ratio"] = ov[V] / ov[M]
k = ov.groupby("mon").ratio.median()
print("Per-month VIIRS/MODIS ratio (median, 2012-2025):")
print(k.round(2).to_string())

# leave-one-year-out validation
errs = []
for y in sorted(ov.year.unique()):
    tr, te = ov[ov.year != y], ov[ov.year == y]
    kk = tr.groupby("mon").ratio.median()
    pred = te[M] * te.mon.map(kk)
    errs.append(np.abs(pred - te[V]).sum() / te[V].sum())
print(f"\nLeave-one-year-out yearly-total error: mean {np.mean(errs)*100:.1f}%")
raw_corr = ov[[M, V]].corr().iloc[0, 1]
print(f"Monthly MODIS vs VIIRS correlation (overlap): r = {raw_corr:.3f}")

df["harmonized"] = np.where(df.year >= 2012, df[V], df[M] * df.mon.map(k))
df["source"] = np.where(df.year >= 2012, "VIIRS (S-NPP)", "MODIS x k_month")
clim = df[(df.year >= 2001) & (df.year <= 2024)].groupby("mon").harmonized.median()
df["median_2001_2024"] = df.mon.map(clim).round(0)
df["anomaly_pct"] = ((df.harmonized / df.median_2001_2024 - 1) * 100).round(1)
df["harmonized"] = df.harmonized.round(0).astype(int)
df[["month", "harmonized", "source", "median_2001_2024", "anomaly_pct"]].to_csv(out, index=False)

cal = df[df.year >= 2001].pivot(index="year", columns="mon", values="harmonized")
print("\nBurning-activity calendar (harmonized hotspots, rows=year, cols=month):")
print(cal.to_string())
print(f"\nWrote {out}")
