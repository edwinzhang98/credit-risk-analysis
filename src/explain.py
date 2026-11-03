"""Explanations for individual decisions: SHAP for the challenger, points-below-maximum for the scorecard.

Both produce "principal reasons" in the format of an adverse-action notice: the up-to-four inputs that pushed this
applicant's risk up the most, written with the plain-English labels from src/features.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def shap_values(booster, X: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """SHAP contributions in log-odds for a LightGBM booster; returns (frame aligned to X, expected log-odds)."""
    import shap

    explainer = shap.TreeExplainer(booster)
    sv = explainer.shap_values(X)
    if isinstance(sv, list):  # older shap returns [class0, class1]
        sv = sv[1]
    base = explainer.expected_value
    if isinstance(base, (list, np.ndarray)):
        base = np.ravel(base)[-1]
    return pd.DataFrame(sv, index=X.index, columns=X.columns), float(base)


def global_importance(shap_df: pd.DataFrame, labels: dict, groups: dict) -> pd.DataFrame:
    """Mean |SHAP| per feature (average impact on the log-odds of default)."""
    imp = shap_df.abs().mean().rename("mean_abs_shap").reset_index().rename(columns={"index": "feature"})
    imp["label"] = imp.feature.map(labels)
    imp["group"] = imp.feature.map(groups)
    imp["share"] = imp.mean_abs_shap / imp.mean_abs_shap.sum()
    return imp.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)


def top_reasons(shap_df: pd.DataFrame, labels: dict, k: int = 4) -> pd.DataFrame:
    """The k inputs with the largest positive contribution to risk for each applicant (fewer if fewer push risk up)."""
    arr = shap_df.to_numpy()
    order = np.argsort(-arr, axis=1)[:, :k]
    names = np.array(shap_df.columns)
    out = pd.DataFrame(index=shap_df.index)
    for i in range(k):
        vals = arr[np.arange(len(arr)), order[:, i]]
        out[f"reason_{i + 1}"] = np.where(vals > 0, [labels.get(n, n) for n in names[order[:, i]]], "")
        out[f"reason_{i + 1}_feature"] = np.where(vals > 0, names[order[:, i]], "")
        out[f"reason_{i + 1}_impact"] = np.where(vals > 0, vals, 0.0)
    return out


def fmt_value(feature: str, value) -> str:
    """Readable value for the explanation table."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "not available"
    if isinstance(value, str):
        return value.replace("_", " ")
    v = float(value)
    if feature.startswith("share_") or feature in {"payment_to_income", "ap_share_rejected", "ap_share_closed_late", "ap_share_cash_apps", "ap_share_xsell_apps",
                                                   "down_payment_share", "disbursed_share", "net_punctuality", "ap_open_annuity_to_income"}:
        return f"{100 * v:.0f}%"
    if feature in {"loan_amount", "monthly_payment", "income_main", "down_payment", "goods_price", "disbursed_amount", "avg_instalment_24m", "max_instalment_24m",
                   "max_past_monthly_payment", "max_past_debt", "total_repaid", "ap_last_rej_credamount", "ap_last_appr_credamount", "ap_mean_appr_credamount",
                   "ap_max_appr_credamount", "ap_mean_appr_annuity", "ap_sum_open_annuity", "ap_last_income"}:
        return f"{v:,.0f} CU"
    if feature in {"is_cross_sell", "dpd_worsening", "has_repayment_history", "cb_has_enquiry_record"}:
        return "yes" if v >= 0.5 else "no"
    if abs(v - round(v)) < 1e-9:
        return f"{v:,.0f}"
    return f"{v:,.2f}"
