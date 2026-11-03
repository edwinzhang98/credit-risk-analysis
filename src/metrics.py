"""Metric functions. Every definition here matches docs/02_metric_definitions.md.

Conventions: `y` is the default flag (1 = bad), `pd_` / `score` is a probability of default where higher = riskier.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

EPS = 1e-6


# --------------------------------------------------------------------------------------------------------------------
# Rank-ordering metrics (secondary in this project; reported in the model card)
# --------------------------------------------------------------------------------------------------------------------
def auc(y, score) -> float:
    return float(roc_auc_score(np.asarray(y), np.asarray(score)))


def gini(y, score) -> float:
    """Gini = 2 * AUC - 1 (the credit-industry convention)."""
    return 2.0 * auc(y, score) - 1.0


def ks(y, score) -> float:
    """Kolmogorov-Smirnov: max gap between the cumulative score distributions of bads and goods."""
    y = np.asarray(y)
    order = np.argsort(np.asarray(score), kind="mergesort")
    y_sorted = y[order]
    cum_bad = np.cumsum(y_sorted) / max(y_sorted.sum(), 1)
    cum_good = np.cumsum(1 - y_sorted) / max((1 - y_sorted).sum(), 1)
    return float(np.max(np.abs(cum_bad - cum_good)))


def brier(y, p) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(np.mean((p - y) ** 2))


# --------------------------------------------------------------------------------------------------------------------
# Rates with uncertainty
# --------------------------------------------------------------------------------------------------------------------
def wilson_interval(bads, n, z: float = 1.96):
    """95% Wilson score interval for a rate (works for small n and rates near 0)."""
    bads, n = np.asarray(bads, float), np.asarray(n, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = np.where(n > 0, bads / n, np.nan)
        denom = 1 + z**2 / n
        centre = (p + z**2 / (2 * n)) / denom
        half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return centre - half, centre + half


def bad_rate_table(df: pd.DataFrame, by, target: str = "target", amount: str | None = None) -> pd.DataFrame:
    """Volume, defaults, bad rate (with 95% CI) by segment."""
    g = df.groupby(by, observed=True, dropna=False)
    out = g[target].agg(n="size", bads="sum").reset_index()
    out["share"] = out["n"] / out["n"].sum()
    out["bad_rate"] = out["bads"] / out["n"]
    lo, hi = wilson_interval(out["bads"], out["n"])
    out["bad_rate_ci_low"], out["bad_rate_ci_high"] = lo, hi
    if amount:
        out["amount"] = g[amount].sum().values
    return out


# --------------------------------------------------------------------------------------------------------------------
# Stability
# --------------------------------------------------------------------------------------------------------------------
def quantile_edges(ref, n_bins: int = 10) -> np.ndarray:
    """Bin edges at the reference distribution's quantiles (unique, open-ended)."""
    ref = np.asarray(ref, float)
    ref = ref[~np.isnan(ref)]
    qs = np.unique(np.quantile(ref, np.linspace(0, 1, n_bins + 1)[1:-1]))
    return np.concatenate([[-np.inf], qs, [np.inf]])


def psi_table(ref, cur, edges=None, n_bins: int = 10) -> pd.DataFrame:
    """Population Stability Index by bin. Missing values get their own bin."""
    ref, cur = np.asarray(ref, float), np.asarray(cur, float)
    edges = quantile_edges(ref, n_bins) if edges is None else np.asarray(edges, float)

    def dist(x):
        counts = np.histogram(x[~np.isnan(x)], bins=edges)[0].astype(float)
        counts = np.append(counts, np.isnan(x).sum())
        return counts / max(len(x), 1)

    e, a = dist(ref), dist(cur)
    labels = [f"[{edges[i]:.4g}, {edges[i + 1]:.4g})" for i in range(len(edges) - 1)] + ["missing"]
    t = pd.DataFrame({"bin": labels, "expected_share": e, "actual_share": a})
    t = t[(t.expected_share > 0) | (t.actual_share > 0)].copy()
    ee, aa = np.clip(t.expected_share, EPS, None), np.clip(t.actual_share, EPS, None)
    t["psi"] = (aa - ee) * np.log(aa / ee)
    return t.reset_index(drop=True)


def psi(ref, cur, edges=None, n_bins: int = 10) -> float:
    return float(psi_table(ref, cur, edges, n_bins)["psi"].sum())


def psi_categorical(ref, cur) -> float:
    """PSI of a categorical input from category shares; missing values are their own category."""
    e = pd.Series(ref, dtype=object).fillna("missing").astype(str).value_counts(normalize=True)
    a = pd.Series(cur, dtype=object).fillna("missing").astype(str).value_counts(normalize=True)
    cats = e.index.union(a.index)
    ee = np.clip(e.reindex(cats, fill_value=0).to_numpy(float), EPS, None)
    aa = np.clip(a.reindex(cats, fill_value=0).to_numpy(float), EPS, None)
    return float(np.sum((aa - ee) * np.log(aa / ee)))


# --------------------------------------------------------------------------------------------------------------------
# Univariate screening (Information Value), used in the audit and feature inclusion log
# --------------------------------------------------------------------------------------------------------------------
def _iv_from_counts(goods: np.ndarray, bads: np.ndarray) -> tuple[float, np.ndarray]:
    g = (goods + 0.5) / (goods.sum() + 0.5 * len(goods))
    b = (bads + 0.5) / (bads.sum() + 0.5 * len(bads))
    woe = np.log(g / b)
    return float(np.sum((g - b) * woe)), woe


def iv_numeric(x, y, n_bins: int = 10) -> float:
    """Information Value of a numeric variable using reference-quantile bins plus a missing bin."""
    x, y = np.asarray(x, float), np.asarray(y)
    edges = quantile_edges(x, n_bins) if np.isfinite(x).any() else np.array([-np.inf, np.inf])
    idx = np.where(np.isnan(x), len(edges) - 1, np.clip(np.searchsorted(edges, x, side="right") - 1, 0, len(edges) - 2))
    k = len(edges)
    bads = np.bincount(idx, weights=y, minlength=k)
    n = np.bincount(idx, minlength=k)
    keep = n > 0
    return _iv_from_counts((n - bads)[keep], bads[keep])[0]


def iv_categorical(x, y, max_levels: int = 30) -> float:
    """Information Value of a categorical variable; rare levels are pooled into 'other', missing kept separate."""
    s = pd.Series(x).astype("object").where(pd.notna(x), "__missing__")
    top = s.value_counts().index[:max_levels]
    s = s.where(s.isin(top), "__other__")
    t = pd.DataFrame({"x": s.values, "y": np.asarray(y)}).groupby("x")["y"].agg(["size", "sum"])
    return _iv_from_counts((t["size"] - t["sum"]).values.astype(float), t["sum"].values.astype(float))[0]


# --------------------------------------------------------------------------------------------------------------------
# Calibration
# --------------------------------------------------------------------------------------------------------------------
def calibration_table(y, p, n_bins: int = 10) -> pd.DataFrame:
    """Mean predicted PD vs observed bad rate by predicted-PD decile."""
    df = pd.DataFrame({"y": np.asarray(y), "p": np.asarray(p)})
    df["bin"] = pd.qcut(df["p"].rank(method="first"), n_bins, labels=False)
    out = df.groupby("bin").agg(n=("y", "size"), bads=("y", "sum"), mean_pd=("p", "mean"), bad_rate=("y", "mean")).reset_index()
    lo, hi = wilson_interval(out["bads"], out["n"])
    out["ci_low"], out["ci_high"] = lo, hi
    return out
