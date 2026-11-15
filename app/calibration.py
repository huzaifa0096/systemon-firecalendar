"""FireCalendar harmonization engine.

Method (see the application's Method view for the plain-language version):

1. Common unit. Every product is counted as *fire cell-days*: the number of
   distinct ~1 km grid cells (0.01 deg) with at least one detection on a day.
   One VIIRS fire split over several 375 m pixels then counts once, like MODIS.

2. Reference scale = VIIRS Suomi-NPP. Every other product is linked to it
   directly over the years both were operating:
       MODIS (Terra+Aqua) -> SNPP   overlap 2012-2025
       TERRA only         -> SNPP   (bridges Nov 2000 - Jun 2002, before Aqua)
       NOAA-20            -> SNPP   (calibrated alternate reference-period source)

3. Local ratios. For each calibration cell (CELL deg) and calendar month,
       k[c,m] = (R[c,m] + LM * prior[c,m]) / (S[c,m] + LM)
   where S, R are source/reference cell-days summed over the overlap years and
       prior[c,m] = k_region[m] * r[c]
       k_region[m] = sum_c R / sum_c S                      (regional seasonal ratio)
       r[c]       = (R_c + LC) / (sum_m k_region[m] S[c,m] + LC)   (cell's own bias, shrunk to 1)
   Cells with few fires fall back to the regional ratio; busy cells use their own.

4. Validation. Leave-one-year-out (LOYO): hide one overlap year, refit, predict
   that year's VIIRS from MODIS, compare. Done for any area the user selects.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data" / "calibration"
FINE = 0.01
REF = "SNPP"
PRIORITY = ["SNPP", "N20", "N21", "MODIS", "TERRA"]  # first covered product wins
LINKS = ["MODIS", "TERRA", "N20", "N21"]
LABEL = {
    "SNPP": "VIIRS S-NPP (observed)",
    "N20": "VIIRS NOAA-20 (calibrated)",
    "N21": "VIIRS NOAA-21 (calibrated)",
    "MODIS": "MODIS Terra+Aqua (reconstructed)",
    "TERRA": "MODIS Terra (reconstructed)",
}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@dataclass
class Params:
    cell: float = 1.0    # calibration cell size (deg); chosen by LOYO sweep
    lm: float = 20.0     # pseudo-count toward the prior (source cell-days)
    lc: float = 30.0     # pseudo-count toward regional ratio (reference cell-days)
    unit: str = "n"      # "n" = fire cell-days, "pix" = raw pixel counts
    # Calibration window per link. Terra's orbit drifted after 2020 (its ratio to
    # VIIRS rises ~20%), and the Terra link only rebuilds 2000-2002, so we fit it
    # on the years when Terra still flew its nominal 10:30 orbit.
    cal_years: dict = field(default_factory=lambda: {"TERRA": (2012, 2019)})


# --------------------------------------------------------------------------
# Ratio fitting
# --------------------------------------------------------------------------
def fit_from_sums(Ss: np.ndarray, Rs: np.ndarray, p: Params) -> tuple[np.ndarray, np.ndarray]:
    """Ss, Rs: [C,12] summed source/reference counts. Returns k[C,12], k_region[12]."""
    k_reg = Rs.sum(0) / np.maximum(Ss.sum(0), 1e-9)
    k_reg = np.where(Ss.sum(0) > 0, k_reg, np.nan)
    k_reg = np.where(np.isnan(k_reg), np.nanmean(k_reg), k_reg)
    expected = (Ss * k_reg).sum(1)
    r_c = (Rs.sum(1) + p.lc) / (expected + p.lc)
    prior = k_reg[None, :] * r_c[:, None]
    k = (Rs + p.lm * prior) / (Ss + p.lm)
    return k, k_reg


def national_median_ratio(S: np.ndarray, R: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Baseline method: k[m] = median over years of (sum R / sum S). S,R:[C,Y,12]."""
    s = S.sum(0)
    r = R.sum(0)
    ratio = np.where(mask & (s > 0), r / np.maximum(s, 1e-9), np.nan)
    return np.nanmedian(ratio, axis=0)


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------
def anomaly_class(series: np.ndarray, valid: np.ndarray, band: float = 0.25) -> np.ndarray:
    """series [Y,12]. Class of each month vs the median of the same month in other years."""
    out = np.full(series.shape, np.nan)
    for m in range(12):
        col = series[:, m]
        ok = valid[:, m]
        for y in np.where(ok)[0]:
            others = col[ok & (np.arange(len(col)) != y)]
            if len(others) < 3:
                continue
            med = np.median(others)
            if med <= 0:
                continue
            a = col[y] / med - 1
            out[y, m] = 1 if a > band else (-1 if a < -band else 0)
    return out


def score(pred: np.ndarray, obs: np.ndarray, valid: np.ndarray) -> dict:
    """pred, obs: [Y,12] over held-out years. valid: [Y,12] bool."""
    yrs = valid.any(1)
    ann_p = np.where(valid, pred, 0).sum(1)[yrs]
    ann_o = np.where(valid, obs, 0).sum(1)[yrs]
    keep = ann_o > 0
    ann_err = np.abs(ann_p[keep] - ann_o[keep]) / ann_o[keep] * 100
    mp, mo = pred[valid], obs[valid]
    r = float(np.corrcoef(mp, mo)[0, 1]) if len(mp) > 2 and mo.std() > 0 and mp.std() > 0 else float("nan")
    big = mo >= 20
    mon_err = np.abs(mp[big] - mo[big]) / mo[big] * 100 if big.any() else np.array([np.nan])
    ca, co = anomaly_class(pred, valid), anomaly_class(obs, valid)
    both = ~np.isnan(ca) & ~np.isnan(co)
    agree = float((ca[both] == co[both]).mean() * 100) if both.any() else float("nan")
    # per-calendar-month normalised RMSE -> uncertainty band for reconstructed months
    nrmse = []
    for m in range(12):
        v = valid[:, m]
        if v.sum() >= 2 and obs[v, m].mean() > 0:
            nrmse.append(float(np.sqrt(np.mean((pred[v, m] - obs[v, m]) ** 2)) / obs[v, m].mean()))
        else:
            nrmse.append(float("nan"))
    return {
        "annual_error_pct_median": _r(np.median(ann_err)) if len(ann_err) else None,
        "annual_error_pct_mean": _r(np.mean(ann_err)) if len(ann_err) else None,
        "monthly_error_pct_median": _r(np.nanmedian(mon_err)) if np.isfinite(mon_err).any() else None,
        "monthly_r": _r(r, 3),
        "anomaly_agreement_pct": _r(agree),
        "years_tested": int(keep.sum()),
        "monthly_nrmse": [_r(x, 3) for x in nrmse],
    }


def _r(x, nd=1):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(x) else round(x, nd)


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------
@dataclass
class Engine:
    params: Params = field(default_factory=Params)

    def __post_init__(self) -> None:
        self.meta = json.loads((DATA / "meta.json").read_text())
        cd = pd.read_parquet(DATA / "celldays.parquet")
        cd["product"] = cd["product"].astype(str)
        cd["lat"] = ((cd["ci"] + 0.5) * FINE - 90).astype("float32")
        cd["lon"] = ((cd["cj"] + 0.5) * FINE - 180).astype("float32")
        d = pd.to_datetime(cd["date"])
        cd["year"] = d.dt.year.astype("int16")
        cd["month"] = (d.dt.month - 1).astype("int8")
        cd["date"] = d
        self.cd = cd
        self.years = np.arange(int(self.cd["year"].min()), int(self.cd["year"].max()) + 1)
        self.coverage = self._coverage()
        self._grid()
        self.fit()

    # ---- setup ---------------------------------------------------------
    def _coverage(self) -> dict[str, np.ndarray]:
        """[Y,12] bool: months fully observed by each product."""
        plats = self.meta["platforms"]

        def span(first: str, last: str) -> np.ndarray:
            f, l = pd.Timestamp(first), pd.Timestamp(last)
            start = f if f.day <= 3 else (f + pd.offsets.MonthBegin(1))
            end = l if l.day >= l.days_in_month - 2 else (l - pd.offsets.MonthEnd(1))
            cov = np.zeros((len(self.years), 12), bool)
            for i, y in enumerate(self.years):
                for m in range(12):
                    t = pd.Timestamp(int(y), m + 1, 1)
                    cov[i, m] = (t >= start.replace(day=1)) and (t <= end.replace(day=1))
            return cov

        cov = {}
        if "Terra" in plats:
            cov["TERRA"] = span(plats["Terra"]["first"], plats["Terra"]["last"])
        if "Terra" in plats and "Aqua" in plats:
            first = max(plats["Terra"]["first"], plats["Aqua"]["first"])
            last = min(plats["Terra"]["last"], plats["Aqua"]["last"])
            cov["MODIS"] = span(first, last)
        for p in ("SNPP", "N20", "N21"):
            if p in plats:
                cov[p] = span(plats[p]["first"], plats[p]["last"])
        return cov

    def _grid(self) -> None:
        c = self.params.cell
        self.cd["gi"] = np.floor((self.cd["lat"] + 90) / c).astype("int32")
        self.cd["gj"] = np.floor((self.cd["lon"] + 180) / c).astype("int32")
        keys = self.cd[["gi", "gj"]].drop_duplicates().reset_index(drop=True)
        keys["cidx"] = np.arange(len(keys), dtype=np.int32)
        self.cells = keys
        self.cd = self.cd.drop(columns=[c for c in ("cidx",) if c in self.cd]).merge(keys, on=["gi", "gj"])
        self.C = len(keys)
        self.yi = {int(y): i for i, y in enumerate(self.years)}
        self.cd["yidx"] = (self.cd["year"] - self.years[0]).astype("int16")
        self.nat = self.dense(self.cd)

    def dense(self, sub: pd.DataFrame) -> dict[str, dict[str, np.ndarray]]:
        """{product: {"n": [C,Y,12], "pix": [C,Y,12]}} for a subset of cell-days."""
        out = {}
        Y = len(self.years)
        for p in PRIORITY:
            n = np.zeros((self.C, Y, 12), np.float64)
            pix = np.zeros((self.C, Y, 12), np.float64)
            s = sub[sub["product"] == p]
            if len(s):
                idx = (s["cidx"].to_numpy(), s["yidx"].to_numpy(), s["month"].to_numpy())
                np.add.at(n, idx, 1)
                np.add.at(pix, idx, s["npix"].to_numpy())
            out[p] = {"n": n, "pix": pix}
        return out

    def overlap_mask(self, src: str) -> np.ndarray:
        if src not in self.coverage or REF not in self.coverage:
            return np.zeros((len(self.years), 12), bool)
        m = self.coverage[src] & self.coverage[REF]
        if src in (self.params.cal_years or {}):
            lo, hi = self.params.cal_years[src]
            m = m & ((self.years >= lo) & (self.years <= hi))[:, None]
        return m

    # ---- calibration -------------------------------------------------
    def fit(self) -> None:
        u = self.params.unit
        self.k, self.k_region, self.k_loyo, self.k_base, self.k_base_loyo = {}, {}, {}, {}, {}
        R = self.nat[REF][u]
        for src in LINKS:
            mask = self.overlap_mask(src)
            if not mask.any():
                continue
            S = self.nat[src][u]
            Sm, Rm = S * mask[None], R * mask[None]
            Ss, Rs = Sm.sum(1), Rm.sum(1)
            self.k[src], self.k_region[src] = fit_from_sums(Ss, Rs, self.params)
            self.k_base[src] = national_median_ratio(S, R, mask)
            loyo, base_loyo = {}, {}
            for yi in np.where(mask.any(1))[0]:
                loyo[yi] = fit_from_sums(Ss - Sm[:, yi], Rs - Rm[:, yi], self.params)[0]
                m2 = mask.copy()
                m2[yi] = False
                base_loyo[yi] = national_median_ratio(S, R, m2)
            self.k_loyo[src], self.k_base_loyo[src] = loyo, base_loyo

    # ---- area queries -------------------------------------------------
    def area(self, bbox: tuple[float, float, float, float] | None):
        if bbox is None:
            return self.nat
        w, s, e, n = bbox
        cd = self.cd
        sub = cd[(cd["lon"] >= w) & (cd["lon"] <= e) & (cd["lat"] >= s) & (cd["lat"] <= n)]
        return self.dense(sub)

    def validate(self, a, src: str = "MODIS") -> dict:
        """LOYO for one link on area arrays `a`. Ours vs the national-median baseline."""
        if src not in self.k_loyo:
            return {}
        u = self.params.unit
        mask = self.overlap_mask(src)
        yis = sorted(self.k_loyo[src])
        S, R = a[src][u], a[REF][u]
        Sp, Rp = S, R
        pred = np.stack([(S[:, yi] * self.k_loyo[src][yi]).sum(0) for yi in yis])
        obs = np.stack([R[:, yi].sum(0) for yi in yis])
        bpred = np.stack([Sp[:, yi].sum(0) * self.k_base_loyo[src][yi] for yi in yis])
        bobs = np.stack([Rp[:, yi].sum(0) for yi in yis])
        valid = mask[yis]
        return {
            "link": f"{src} -> {REF}",
            "years": [int(self.years[y]) for y in yis],
            "ours": score(pred, obs, valid),
            "baseline": score(bpred, bobs, valid),
        }

    def series(self, a) -> dict:
        """Harmonized monthly series [Y,12] for area arrays `a`."""
        u = self.params.unit
        Y = len(self.years)
        H = np.full((Y, 12), np.nan)
        src = np.full((Y, 12), "", dtype=object)
        preds = {REF: a[REF][u].sum(0)}
        for p in LINKS:
            if p in self.k:
                preds[p] = (a[p][u] * self.k[p][:, None, :]).sum(0)
        for p in PRIORITY:
            if p not in preds or p not in self.coverage:
                continue
            take = self.coverage[p] & np.isnan(H)
            H[take] = preds[p][take]
            src[take] = p
        # uncertainty: +- per-month NRMSE from this area's own LOYO test
        lo, hi = H.copy(), H.copy()
        val = {}
        for p in LINKS:
            if p not in self.k_loyo:
                continue
            v = self.validate(a, p)
            val[p] = v
            nr = np.array([x if x is not None else np.nan for x in v["ours"]["monthly_nrmse"]])
            sel = src == p
            band = H * nr[None, :]
            lo[sel] = np.maximum(H - band, 0)[sel]
            hi[sel] = (H + band)[sel]
        raw = {p: a[p]["pix"].sum(0) for p in ("MODIS", "TERRA", "SNPP", "N20")}
        naive = np.where(self.coverage.get(REF, np.zeros((Y, 12), bool)), raw["SNPP"],
                         np.where(self.coverage.get("TERRA", np.zeros((Y, 12), bool)), raw["MODIS"], np.nan))
        return {"H": H, "lo": lo, "hi": hi, "src": src, "raw": raw, "naive": naive, "validation": val}


def anomalies(H: np.ndarray, complete: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """% anomaly vs median of the same month in all other years + percentile rank."""
    Y = H.shape[0]
    pct = np.full(H.shape, np.nan)
    rank = np.full(H.shape, np.nan)
    med = np.full(H.shape, np.nan)
    for m in range(12):
        ok = ~np.isnan(H[:, m]) & complete
        for y in range(Y):
            if np.isnan(H[y, m]):
                continue
            others = H[ok & (np.arange(Y) != y), m]
            if len(others) < 3:
                continue
            md = np.median(others)
            med[y, m] = md
            pct[y, m] = (H[y, m] / md - 1) * 100 if md > 0 else np.nan
            rank[y, m] = (others < H[y, m]).mean() * 100
    return pct, rank, med
