import numpy as np
import pandas as pd
import streamlit as st

from common import CACHE, HEADERS, how_to_read, kpi_row, load, metrics, page_header, styled
from src import charts
from src.explain import fmt_value
from src.features import LABELS

m = metrics()
mm = m["models"]
CH, CP = "Challenger (LightGBM)", "Champion (scorecard)"
_imp = load("shap_global")
_gs = _imp.groupby("group").share.sum()
track_share = float(_gs.get("Repayment history", 0) + _gs.get("Previous applications", 0))
page_header("Model & explainability", "How well do the two models separate good from bad customers, and why is a given applicant declined?")

kpi_row([
    ("Gini, challenger (out-of-time)", f"{mm['gini_test_challenger']:.3f}", "Rank-ordering on Jan to Mar 2020; 0 = random, 1 = perfect."),
    ("Gini, champion scorecard", f"{mm['gini_test_champion']:.3f}", f"{mm['scorecard_variables']}-variable WOE logistic scorecard."),
    ("Calibration ratio (test)", f"{mm['calibration_ratio_test_challenger']:.2f}", "Mean predicted PD ÷ observed bad rate. Below 1 = the test quarter defaulted more than predicted."),
    ("Impact from the client's track record", f"{track_share:.0%}", f"Share of the challenger's total SHAP impact from repayment history and previous applications. Largest single input: {mm['top_driver'].lower()}."),
])

tab1, tab2, tab3 = st.tabs(["Why was this applicant declined?", "How good are the models?", "What drives the models?"])

with tab1:
    sample, shp, vals = load("explain_sample"), load("explain_shap"), load("explain_values")
    vals = vals.assign(case_id=vals.case_id.astype("int64"))
    typical = load("typical_values").set_index("feature").typical_approved
    c1, c2 = st.columns([1, 2])
    which = c1.radio("Show", ["Declined applicants", "Approved applicants"], horizontal=True)
    pool = sample[sample.decision_challenger == ("Decline" if which.startswith("Declined") else "Approve")].sort_values("pd_challenger", ascending=which.startswith("Approved"))
    options = pool.case_id.tolist()
    fmt = lambda cid: (lambda r: f"#{cid} · {r.product_type} · {r.loan_amount:,.0f} CU · PD {r.pd_challenger:.1%}")(pool.set_index("case_id").loc[cid])
    cid = c2.selectbox("Applicant (out-of-time test sample)", options, format_func=fmt)
    r = sample.set_index("case_id").loc[cid]
    contrib = shp.set_index("case_id").loc[cid]
    raw_vals = vals.set_index("case_id").loc[cid]

    def readable(f):
        v = raw_vals[f]
        try:
            return fmt_value(f, float(v))
        except (TypeError, ValueError):
            return fmt_value(f, None if v in ("nan", "None", "<NA>") else v)

    values = {f: readable(f) for f in contrib.index}
    decision = "Declined" if r.decision_challenger == "Decline" else "Approved"
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Decision (challenger, cost-based rule)", decision)
    k2.metric("Predicted PD", f"{r.pd_challenger:.1%}")
    k3.metric("Break-even PD for this product", f"{r.breakeven_pd:.1%}")
    k4.metric("Scorecard points (champion)", f"{r.score_champion:.0f}", help="600 points = odds of 50:1; +20 points doubles the odds of repaying.")
    st.plotly_chart(charts.explanation_bars(contrib, LABELS, values), use_container_width=True)
    reasons = [(r[f"reason_{i}"], r[f"reason_{i}_feature"]) for i in range(1, 5) if r[f"reason_{i}"]]
    if reasons:
        rows = [{"Principal reason (plain English)": lab, "This applicant": values.get(f, ""), "Typical approved applicant": fmt_value(f, typical.get(f, np.nan)) if f in typical.index else "-"} for lab, f in reasons]
        st.markdown("**Principal reasons** (inputs that pushed this applicant's risk up the most, as on an adverse-action notice):")
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    sc_reasons = [r[f"sc_reason_{i}"] for i in range(1, 5)]
    st.caption("Champion scorecard reasons (largest points lost vs the best bin of each variable): " + "; ".join(sc_reasons))
    st.caption(f"Actual outcome (known only in hindsight): {'defaulted' if r.target == 1 else 'did not default'}.")

with tab2:
    met = load("model_metrics")
    biz = load("model_business_comparison")
    st.markdown("**In money, on the out-of-time test window** (cost-based rule and fixed approval rates)")
    show = biz[["model", "policy", "approval_rate", "bad_rate_approved", "capture_rate", "false_positive_rate", "credit_loss", "forgone_margin", "net_profit"]].copy()
    st.dataframe(styled(show, {"approval_rate": "{:.1%}", "bad_rate_approved": "{:.2%}", "capture_rate": "{:.1%}", "false_positive_rate": "{:.1%}",
                               "credit_loss": "{:,.0f}", "forgone_margin": "{:,.0f}", "net_profit": "{:,.0f}"}), hide_index=True, use_container_width=True)
    c1, c2 = st.columns(2)
    c1.plotly_chart(charts.calibration_deciles(load("calibration_test")), use_container_width=True)
    c2.plotly_chart(charts.gini_by_window(met), use_container_width=True)
    st.markdown("**Is the champion handicapped?** The gap between the models, split into algorithm and information (out-of-time test)")
    st.dataframe(styled(load("champion_checks"), {"valid_gini": "{:.3f}", "test_gini": "{:.3f}"}), hide_index=True, use_container_width=True)
    st.markdown("**By segment** (new-to-lender clients have no internal history, so both models rank them less well)")
    seg = load("segment_metrics")
    seg_view = seg.pivot_table(index="segment", columns="model", values=["gini", "calibration_ratio", "bad_rate"]).round(3)
    seg_view.columns = [f"{HEADERS.get(a, a)}, {b.split(' (')[0].lower()}" for a, b in seg_view.columns]
    st.dataframe(seg_view.rename_axis("Segment"), use_container_width=True)

with tab3:
    imp = load("shap_global")
    st.plotly_chart(charts.shap_importance(imp), use_container_width=True)
    grp = imp.groupby("group").share.sum().sort_values(ascending=False)
    st.caption("Share of total impact by input group: " + " · ".join(f"{k} {v:.0%}" for k, v in grp.items()))
    coefs = load("scorecard_coefficients").sort_values("iv", ascending=False)
    st.markdown("**Champion scorecard variables** (information value on the training window; all coefficients have the expected sign)")
    st.dataframe(styled(coefs[["label", "feature", "iv", "coefficient"]], {"iv": "{:.3f}", "coefficient": "{:.3f}"}), hide_index=True, use_container_width=True)
    with st.expander("Scorecard points table (bins and points per variable)"):
        pts = load("scorecard_points")
        cols = ["Variable", "Bin", "Count", "Event rate", "WoE"] + (["WoE used in score"] if "WoE used in score" in pts else []) + ["Points"]
        pts = pts.assign(Variable=pts.Variable.map(LABELS))[cols]
        st.caption("Missing values are scored with a neutral WOE of 0 whatever their observed default rate, so every Missing bin earns the same points. "
                   "A decline reason that comes from a missing value reads \"(no record)\" for history fields and \"(not provided)\" for application-form fields.")
        st.dataframe(pts.round(3), hide_index=True, use_container_width=True, height=420)

how_to_read("""
**Explaining one decision.** Pick an applicant. The bar chart starts from the average applicant and shows which inputs pushed this person's
predicted risk up (orange) or down (blue), measured with SHAP values in "log-odds" (the scale the model adds things up on). The table lists the
**principal reasons**: the up to four inputs that raised the risk the most, in plain English, next to this applicant's value and the typical value
among approved applicants. This is the format of an adverse-action notice. The scorecard gives its own reasons: the variables where the applicant
scored furthest below the best possible points (a reason from a missing value says "no record" or "not provided").

**How good is the model.** *Gini* measures how well a model ranks applicants (0 = coin flip, 1 = perfect). It is useful for comparing models,
but the decision is made on the money table. *Calibration* compares predicted and actual default rates: the points fall above the diagonal
because the test quarter defaulted more than the months the models were calibrated on; ranking held up, the level did not.

**What SHAP is not.** It explains how the model uses its inputs, not what causes default.
""")
