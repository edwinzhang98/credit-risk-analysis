"""Monitoring metrics by decision month: score stability (PSI), feature stability (CSI), rank-ordering and calibration."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.metrics import gini, psi, psi_categorical, quantile_edges

PSI_WATCH, PSI_ACT = 0.10, 0.25


def psi_status(value: float) -> str:
    if value < PSI_WATCH:
        return "stable"
    if value < PSI_ACT:
        return "investigate"
    return "act"


def monthly_score_monitor(df: pd.DataFrame, score_col: str, ref_mask, month_col: str = "decision_month", target_col: str = "target") -> pd.DataFrame:
    """One row per month: volume, bad rate, mean PD, calibration ratio, Gini and PSI vs the reference window."""
    ref = df.loc[ref_mask, score_col].to_numpy(float)
    edges = quantile_edges(ref, 10)
    rows = []
    for month, g in df.groupby(month_col, sort=True):
        y, s = g[target_col].to_numpy(int), g[score_col].to_numpy(float)
        rows.append(
            {
                month_col: month,
                "applications": len(g),
                "bad_rate": y.mean(),
                "mean_pd": s.mean(),
                "calibration_ratio": s.mean() / y.mean() if y.mean() > 0 else np.nan,
                "gini": gini(y, s) if 0 < y.sum() < len(y) else np.nan,
                "psi": psi(ref, s, edges),
            }
        )
    out = pd.DataFrame(rows)
    out["psi_status"] = out["psi"].map(psi_status)
    return out


def monthly_csi(df: pd.DataFrame, features: list[str], ref_mask, month_col: str = "decision_month") -> pd.DataFrame:
    """Characteristic stability index of each feature by month (reference = training window deciles; categories by share)."""
    rows = []
    ref = df.loc[ref_mask]
    for f in features:
        if not pd.api.types.is_numeric_dtype(df[f]):
            for month, g in df.groupby(month_col, sort=True):
                rows.append({"feature": f, month_col: month, "csi": psi_categorical(ref[f], g[f])})
            continue
        r = pd.to_numeric(ref[f], errors="coerce").to_numpy(float)
        if np.isnan(r).all():
            continue
        edges = quantile_edges(r, 10)
        for month, g in df.groupby(month_col, sort=True):
            rows.append({"feature": f, month_col: month, "csi": psi(r, pd.to_numeric(g[f], errors="coerce").to_numpy(float), edges)})
    return pd.DataFrame(rows)
