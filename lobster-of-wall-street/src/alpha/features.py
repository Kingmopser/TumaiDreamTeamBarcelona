"""
Stage 1 & 2 — Feature Engineering + Signal Amplification
All signals computed from pre-April 2025 data ONLY.
"""

import numpy as np
import pandas as pd
from .data import DATA_CUTOFF


def compute_features(data: pd.DataFrame, sector_map: dict) -> pd.DataFrame:
    """
    Compute all technical features for every ticker.
    Returns a DataFrame with one row per ticker.
    """
    close = data["Close"] if isinstance(data.columns, pd.MultiIndex) else data
    volume = data["Volume"] if isinstance(data.columns, pd.MultiIndex) else None

    cutoff = pd.Timestamp(DATA_CUTOFF)
    records = []

    for ticker in close.columns:
        p = close[ticker].dropna()
        p = p[p.index <= cutoff]
        if len(p) < 60:
            continue

        px = float(p.iloc[-1])
        if px <= 0 or np.isnan(px):
            continue

        # ── Returns at various horizons ──
        def _ret(days):
            t = cutoff - pd.Timedelta(days=days)
            idx = p.index[p.index <= t]
            return float(px / p.loc[idx[-1]] - 1) if len(idx) > 0 else 0.0

        r12m, r6m, r3m, r1m = _ret(365), _ret(180), _ret(90), _ret(30)

        # ── Momentum acceleration (2nd derivative proxy) ──
        # Positive → recent trend improving vs. earlier trend
        mom_accel = r3m - (r6m - r3m)

        # ── Volatility (60-day annualised) ──
        dr = p.pct_change().dropna()
        dr60 = dr.tail(60)
        vol_60d = float(dr60.std() * np.sqrt(252)) if len(dr60) > 20 else 0.0

        # ── Volume expansion (20d avg / 60d avg) ──
        vol_expand = 1.0
        if volume is not None and ticker in volume.columns:
            v = volume[ticker].dropna()
            v = v[v.index <= cutoff]
            if len(v) > 60:
                v20 = v.tail(20).mean()
                v60 = v.tail(60).mean()
                vol_expand = float(v20 / v60) if v60 > 0 else 1.0

        # ── 52-week high/low and distances ──
        p1y = p.tail(252)
        hi52 = float(p1y.max())
        lo52 = float(p1y.min())
        dist_hi = px / hi52 if hi52 > 0 else 1.0  # 1.0 = at high
        dist_lo = px / lo52 if lo52 > 0 else 1.0   # 1.0 = at low

        # ── Gap frequency (days with >5% absolute move, last 60d) ──
        gaps = int((dr60.abs() > 0.05).sum()) if len(dr60) > 0 else 0

        # ── Max drawdown (trailing 252d) ──
        peak = p1y.expanding().max()
        dd_series = p1y / peak - 1.0
        max_dd = float(dd_series.min())
        cur_dd = float(dd_series.iloc[-1]) if len(dd_series) > 0 else 0.0

        # ── Drawdown recovery speed ──
        # How fast did it bounce from its 252d low?
        days_since_low = 0
        if len(p1y) > 5:
            low_idx = p1y.idxmin()
            days_since_low = (cutoff - low_idx).days

        # recovery = pct gained from 252d low to current
        recovery_from_low = (px / lo52 - 1.0) if lo52 > 0 else 0.0

        # ── Average volume (for liquidity filter) ──
        avg_vol = 0
        if volume is not None and ticker in volume.columns:
            vt = volume[ticker].dropna()
            vt = vt[vt.index <= cutoff].tail(20)
            avg_vol = int(vt.mean()) if len(vt) > 0 else 0

        records.append({
            "ticker":       ticker,
            "sector":       sector_map.get(ticker, "Other"),
            "price":        round(px, 4),
            "r12m":         round(r12m, 4),
            "r6m":          round(r6m, 4),
            "r3m":          round(r3m, 4),
            "r1m":          round(r1m, 4),
            "mom_accel":    round(mom_accel, 4),
            "vol_60d":      round(vol_60d, 4),
            "vol_expand":   round(vol_expand, 4),
            "dist_hi":      round(dist_hi, 4),
            "dist_lo":      round(dist_lo, 4),
            "gaps_60d":     gaps,
            "max_dd":       round(max_dd, 4),
            "cur_dd":       round(cur_dd, 4),
            "days_since_low": days_since_low,
            "recovery":     round(recovery_from_low, 4),
            "avg_vol_20d":  avg_vol,
        })

    return pd.DataFrame(records)
