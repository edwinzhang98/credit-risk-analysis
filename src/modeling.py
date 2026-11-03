"""Model training: champion WOE scorecard, challenger LightGBM, Platt calibration, decline-reason codes.

Both models output a calibrated PD (probability of default). Calibration is fitted on the validation window only.
"""
from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.metrics import auc

warnings.filterwarnings("ignore", category=UserWarning, module="optbinning")


# ---------------------------------------------------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------------------------------------------------
def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


@dataclass
class PlattCalibrator:
    """Two-parameter logistic recalibration on the log-odds of the raw model output (keeps the ranking unchanged)."""

    a: float = 1.0
    b: float = 0.0

    def fit(self, p_raw, y) -> "PlattCalibrator":
        lr = LogisticRegression(C=1e6, max_iter=1000)
        lr.fit(_logit(p_raw).reshape(-1, 1), np.asarray(y))
        self.a, self.b = float(lr.coef_[0, 0]), float(lr.intercept_[0])
        return self

    def transform(self, p_raw) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-(self.a * _logit(p_raw) + self.b)))


# ---------------------------------------------------------------------------------------------------------------------
# Challenger: LightGBM
# ---------------------------------------------------------------------------------------------------------------------
LGBM_PARAMS = {
    "objective": "binary",
    "learning_rate": 0.03,
    "num_leaves": 63,
    "min_data_in_leaf": 400,
    "feature_fraction": 0.6,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 10.0,
    "max_bin": 255,
    "max_cat_to_onehot": 8,
    "cat_smooth": 50,
    "min_data_per_group": 200,
    "verbose": -1,
    "deterministic": True,
    "force_col_wise": True,
    "num_threads": 8,
}


def prepare_lgbm_frame(df: pd.DataFrame, features: list[str], categorical: list[str], categories: dict | None = None):
    """Numeric features as float, categoricals as pandas category with categories frozen from the training data."""
    X = df[features].copy()
    categories = categories or {}
    for c in features:
        if c in categorical:
            cats = categories.get(c)
            if cats is None:
                cats = sorted(X[c].dropna().astype(str).unique().tolist())
                categories[c] = cats
            X[c] = pd.Categorical(X[c].astype("object").where(X[c].notna(), None).map(lambda v: None if v is None else str(v)), categories=cats)
        else:
            X[c] = pd.to_numeric(X[c], errors="coerce").astype("float64")
    return X, categories


def train_lgbm(X_tr, y_tr, X_va, y_va, params: dict | None = None, seed: int = 42, num_boost_round: int = 5000, early_stopping: int = 200, sample_weight=None):
    p = dict(LGBM_PARAMS)
    p.update(params or {})
    p.update({"seed": seed, "bagging_seed": seed, "feature_fraction_seed": seed, "data_random_seed": seed, "metric": "auc"})
    dtr = lgb.Dataset(X_tr, label=y_tr, weight=sample_weight, free_raw_data=False)
    dva = lgb.Dataset(X_va, label=y_va, reference=dtr, free_raw_data=False)
    booster = lgb.train(
        p, dtr, num_boost_round=num_boost_round, valid_sets=[dva], valid_names=["valid"],
        callbacks=[lgb.early_stopping(early_stopping, verbose=False), lgb.log_evaluation(0)],
    )
    return booster


# ---------------------------------------------------------------------------------------------------------------------
# Champion: WOE logistic-regression scorecard
# ---------------------------------------------------------------------------------------------------------------------
@dataclass
class ScorecardResult:
    scorecard: object  # optbinning.Scorecard
    selected: list[str]
    screening: pd.DataFrame  # IV screening of all candidates
    selection_log: pd.DataFrame  # why each candidate was or was not selected
    points_table: pd.DataFrame  # points per variable and bin
    max_points: dict = field(default_factory=dict)


def screen_iv(X: pd.DataFrame, y, numeric: list[str], categorical: list[str], max_n_bins: int = 6, min_bin_size: float = 0.02):
    """Fit monotonic optimal binning on every candidate; return the binning process and an IV summary."""
    from optbinning import BinningProcess

    fit_params = {c: {"monotonic_trend": "auto_asc_desc"} for c in numeric}
    bp = BinningProcess(
        variable_names=numeric + categorical, categorical_variables=categorical, max_n_bins=max_n_bins,
        min_bin_size=min_bin_size, binning_fit_params=fit_params, n_jobs=1,
    )
    bp.fit(X[numeric + categorical], np.asarray(y))
    summary = bp.summary()[["name", "dtype", "n_bins", "iv", "gini"]].sort_values("iv", ascending=False).reset_index(drop=True)
    return bp, summary


def select_scorecard_features(bp, summary: pd.DataFrame, X: pd.DataFrame, max_features: int = 18, min_iv: float = 0.02, max_iv: float = 0.8, max_corr: float = 0.6):
    """Greedy selection by IV with a WOE-correlation filter (standard scorecard practice)."""
    woe = bp.transform(X, metric="woe")
    chosen, log = [], []
    for _, r in summary.iterrows():
        name, iv = r["name"], float(r["iv"])
        if iv < min_iv:
            log.append((name, iv, "not selected: IV below 0.02 (weak)"))
            continue
        if iv > max_iv:
            log.append((name, iv, "not selected: IV above 0.8 (too good to be true; investigate)"))
            continue
        if len(chosen) >= max_features:
            log.append((name, iv, f"not selected: scorecard capped at {max_features} variables"))
            continue
        corr = woe[chosen + [name]].corr().loc[name, chosen].abs() if chosen else pd.Series(dtype=float)
        if len(corr) and corr.max() > max_corr:
            log.append((name, iv, f"not selected: WOE correlation {corr.max():.2f} with {corr.idxmax()}"))
            continue
        chosen.append(name)
        log.append((name, iv, "selected"))
    return chosen, pd.DataFrame(log, columns=["feature", "iv", "decision"])


def fit_scorecard(X_tr: pd.DataFrame, y_tr, numeric: list[str], categorical: list[str], max_features: int = 18, seed: int = 42) -> ScorecardResult:
    from optbinning import BinningProcess, Scorecard

    bp_all, summary = screen_iv(X_tr, y_tr, numeric, categorical)
    selected, log = select_scorecard_features(bp_all, summary, X_tr[numeric + categorical], max_features=max_features)

    def build(sel):
        fit_params = {c: {"monotonic_trend": "auto_asc_desc"} for c in sel if c in numeric}
        bp = BinningProcess(
            variable_names=sel, categorical_variables=[c for c in sel if c in categorical], max_n_bins=6, min_bin_size=0.02,
            binning_fit_params=fit_params, n_jobs=1,
        )
        sc = Scorecard(
            binning_process=bp, estimator=LogisticRegression(C=1.0, max_iter=2000, random_state=seed),
            scaling_method="pdo_odds", scaling_method_params={"pdo": 20, "odds": 50, "scorecard_points": 600}, rounding=False,
        )
        sc.fit(X_tr[sel], np.asarray(y_tr))
        return sc

    # Drop variables whose coefficient sign flips (WOE coefficients must all be negative: higher WOE = safer).
    sc = build(selected)
    for _ in range(10):
        coefs = dict(zip(selected, sc.estimator_.coef_[0]))
        flipped = [k for k, v in coefs.items() if v >= 0]
        if not flipped:
            break
        for k in flipped:
            selected.remove(k)
            log.loc[log.feature == k, "decision"] = "dropped after fit: coefficient sign flipped (collinearity)"
        sc = build(selected)

    table = sc.table(style="detailed")
    table = table[table["Count"] > 0].copy() if "Count" in table else table
    # Missing and special values are scored with WOE 0 (optbinning's default), whatever their empirical WOE in the table
    neutral = table["Bin"].astype(str).isin(["Special", "Missing"])
    table["WoE used in score"] = np.where(neutral, 0.0, table["WoE"].astype(float))
    coef = dict(zip(selected, sc.estimator_.coef_[0]))
    table["Points"] = [_points_from_woe(w, coef[v], sc.estimator_.intercept_[0], len(selected)) for v, w in zip(table["Variable"], table["WoE used in score"])]
    res = ScorecardResult(sc, selected, summary, log, table, {})
    res.max_points = scorecard_max_points(res)
    return res


SCORE_PDO, SCORE_ODDS, SCORE_BASE = 20, 50, 600
SCORE_FACTOR = SCORE_PDO / np.log(2)
SCORE_OFFSET = SCORE_BASE - SCORE_FACTOR * np.log(SCORE_ODDS)


def _points_from_woe(woe, beta, intercept, n_vars):
    """Points of one variable for a given WOE, exactly as the scorecard adds them up (score = sum over variables)."""
    return SCORE_OFFSET / n_vars - SCORE_FACTOR * (beta * woe + intercept / n_vars)


def scorecard_points(res: ScorecardResult, X: pd.DataFrame) -> pd.DataFrame:
    """Points per variable for each applicant. Missing and special values score as WOE 0 (optbinning's default), as in the score."""
    sc = res.scorecard
    woe = sc.binning_process_.transform(X[res.selected], metric="woe")
    beta = sc.estimator_.coef_[0]
    pts = _points_from_woe(woe.to_numpy(float), beta, sc.estimator_.intercept_[0], len(res.selected))
    return pd.DataFrame(pts, index=X.index, columns=res.selected)


def scorecard_max_points(res: ScorecardResult) -> dict:
    """Best achievable points per variable: over the variable's populated bins and the neutral WOE 0 (missing / special)."""
    sc = res.scorecard
    beta = dict(zip(res.selected, sc.estimator_.coef_[0]))
    out = {}
    for var in res.selected:
        t = sc.binning_process_.get_binned_variable(var).binning_table.build()
        t = t[(t.index != "Totals") & (t["Count"] > 0) & (~t["Bin"].astype(str).isin(["Special", "Missing"]))]
        woes = np.append(t["WoE"].astype(float).to_numpy(), 0.0)
        out[var] = float(np.max(_points_from_woe(woes, beta[var], sc.estimator_.intercept_[0], len(res.selected))))
    return out


HISTORY_GROUPS = {"Repayment history", "Previous applications", "Credit bureau"}


def _missing_suffix(feature: str) -> str:
    """How a reason reads when the value is missing: history fields have no record; form fields were not provided."""
    from src.features import GROUPS

    return " (no record)" if GROUPS.get(feature) in HISTORY_GROUPS else " (not provided)"


def scorecard_reason_codes(res: ScorecardResult, X: pd.DataFrame, labels: dict, top_k: int = 4) -> pd.DataFrame:
    """Adverse-action style reasons: the variables where the applicant scored furthest below the best achievable points."""
    pts = scorecard_points(res, X)
    max_pts = scorecard_max_points(res)
    shortfall = pd.DataFrame({v: max_pts[v] - pts[v] for v in res.selected}, index=X.index)
    order = np.argsort(-shortfall.to_numpy(), axis=1, kind="mergesort")[:, :top_k]
    names = np.array(res.selected)
    out = pd.DataFrame(index=X.index)
    missing = X[res.selected].isna().to_numpy()
    rows = np.arange(len(X))
    for i in range(top_k):
        col = order[:, i]
        out[f"reason_{i + 1}"] = [labels.get(n, n) + (_missing_suffix(n) if miss else "") for n, miss in zip(names[col], missing[rows, col])]
        out[f"reason_{i + 1}_points_lost"] = shortfall.to_numpy()[rows, col]
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------------------------------------------------
def save_json(obj, path):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))


def load_json(path):
    with open(path) as f:
        return json.load(f)


def rank_metrics(y, p) -> dict:
    from src.metrics import brier, gini, ks

    return {"auc": auc(y, p), "gini": gini(y, p), "ks": ks(y, p), "brier": brier(y, p), "mean_pd": float(np.mean(p)), "bad_rate": float(np.mean(y))}
