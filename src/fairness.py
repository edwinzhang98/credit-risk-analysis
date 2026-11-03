"""Fair-lending checks: outcomes of a decision policy by sensitive group.

Sensitive attributes (sex, age band) are used ONLY here, to test the policy. They are never model inputs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.metrics import wilson_interval

AGE_BANDS = [18, 25, 35, 45, 55, 65, 120]
AGE_LABELS = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]


def age_band(age_years) -> pd.Series:
    return pd.cut(pd.Series(age_years, dtype=float), bins=AGE_BANDS, labels=AGE_LABELS, right=False).astype("object").fillna("unknown")


def group_outcomes(group, approve, y, pd_) -> pd.DataFrame:
    """Approval rate, approval-rate ratio vs the most-approved group, approved-book bad rate and calibration by group."""
    df = pd.DataFrame({"group": np.asarray(group), "approve": np.asarray(approve, bool), "y": np.asarray(y, int), "pd": np.asarray(pd_, float)})
    g = df.groupby("group", observed=True)
    out = pd.DataFrame(
        {
            "applications": g.size(),
            "approval_rate": g["approve"].mean(),
            "observed_bad_rate": g["y"].mean(),
            "mean_pd": g["pd"].mean(),
        }
    )
    appr = df[df.approve].groupby("group", observed=True)
    out["approved"] = appr.size().reindex(out.index).fillna(0)
    out["approved_bads"] = appr["y"].sum().reindex(out.index).fillna(0)
    out["bad_rate_approved"] = out["approved_bads"] / out["approved"].where(out["approved"] > 0)
    lo, hi = wilson_interval(out["approved_bads"], out["approved"])
    out["bad_rate_approved_ci_low"], out["bad_rate_approved_ci_high"] = lo, hi
    out["approval_rate_ratio"] = out["approval_rate"] / out["approval_rate"].max()
    out["calibration_ratio"] = out["mean_pd"] / out["observed_bad_rate"]
    out["passes_four_fifths"] = out["approval_rate_ratio"] >= 0.8
    return out.reset_index()


def proxy_strength(feature_frame: pd.DataFrame, sensitive, seed: int = 42, sample: int = 200_000) -> float:
    """How well the model's features predict a binary sensitive attribute (AUC of a quick LightGBM).

    0.5 = no information; values well above 0.5 mean the features carry a proxy for the attribute, which is a reason
    to check outcomes by group even though the attribute itself is excluded.
    """
    import lightgbm as lgb
    from sklearn.metrics import roc_auc_score

    s = pd.Series(np.asarray(sensitive))
    keep = s.notna().values
    X, t = feature_frame.loc[keep].reset_index(drop=True), s[keep].reset_index(drop=True)
    classes = sorted(t.unique())
    if len(classes) != 2:
        raise ValueError("proxy_strength expects a binary attribute")
    t = (t == classes[1]).astype(int)
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(t))[: min(sample, len(t))]
    cut = int(len(idx) * 0.7)
    tr, te = idx[:cut], idx[cut:]
    model = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.1, num_leaves=31, random_state=seed, verbose=-1, deterministic=True, force_col_wise=True)
    model.fit(X.iloc[tr], t.iloc[tr])
    return float(roc_auc_score(t.iloc[te], model.predict_proba(X.iloc[te])[:, 1]))
