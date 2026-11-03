import numpy as np
import pandas as pd
import streamlit as st

from common import base_economics, base_review, how_to_read, load, metrics, page_header, styled
from src import charts
from src.economics import PRODUCT_NAMES, Review
from src.strategy import approve_ev_positive, assign_tiers, evaluate_policy, tier_outcomes

page_header("Strategy & monitoring plan", "How should applications be routed, is the policy fair, and how will we know when it stops working?")

m = metrics()
T = load("predictions_test")
y, amt = T.target.to_numpy(), T.loan_amount.to_numpy()
econ, rev0 = base_economics(), base_review()
g, l = econ.per_loan(T.loan_amount, T.product_type)
pH = T.pd_challenger.to_numpy()
MONTHS = 3
CH, CP = "Challenger (LightGBM)", "Champion (scorecard)"

tab1, tab2, tab3, tab4 = st.tabs(["Three-tier policy", "Fair lending", "Monitoring", "Recommendations"])

with tab1:
    with st.container(border=True):
        st.markdown("**Manual review assumptions** (not in the data; to be measured from review outcomes)")
        c1, c2, c3, c4 = st.columns(4)
        cost = c1.slider("Cost per review (CU)", 50, 1500, int(rev0.cost_per_case), 50)
        catch = c2.slider("Share of bad applicants a reviewer declines", 0.10, 0.80, float(rev0.bad_catch_rate), 0.05)
        gdec = c3.slider("Share of good applicants a reviewer declines", 0.00, 0.40, float(rev0.good_decline_rate), 0.01)
        cap = c4.slider("Review capacity (share of applications)", 0.00, 0.15, float(rev0.capacity_share), 0.005, format="%.3f")
    rv = Review(cost, catch, gdec, cap)
    tiers = assign_tiers(pH, g, l, rv, capacity=cap * len(T))
    tab, tot = tier_outcomes(tiers, y, g, l, amt, rv, months=MONTHS)
    two = evaluate_policy(approve_ev_positive(pH, g, l), y, g, l)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Approval rate (after review)", f"{tot['approval_rate']:.1%}")
    k2.metric("Bad rate of approved loans", f"{tot['bad_rate_approved']:.2%}")
    k3.metric("Reviews per month", f"{tot['reviews_per_month']:,.0f}", help=f"Capacity: {cap * len(T) / MONTHS:,.0f} reviews a month")
    k4.metric("Net profit vs two-tier rule", charts.fmt_money(tot["net_profit"]), charts.fmt_money(tot["net_profit"] - two["net_profit"]))
    st.plotly_chart(charts.tier_bars(tab), use_container_width=True)
    show = tab[["tier", "applications", "share", "per_month", "bad_rate", "median_amount", "credit_loss", "forgone_margin", "review_cost", "net_profit"]]
    st.dataframe(styled(show, {"applications": "{:,.0f}", "share": "{:.1%}", "per_month": "{:,.0f}", "bad_rate": "{:.2%}", "median_amount": "{:,.0f}",
                               "credit_loss": "{:,.0f}", "forgone_margin": "{:,.0f}", "review_cost": "{:,.0f}", "net_profit": "{:,.0f}"}), hide_index=True, use_container_width=True)
    c1, c2 = st.columns([1, 1])
    rt = T.assign(tier=np.array(["Auto-approve", "Manual review", "Decline"])[tiers], pd=pH)
    rr = rt[rt.tier == "Manual review"].groupby("product_type").agg(reviews=("pd", "size"), pd_from=("pd", "min"), pd_to=("pd", "max"), smallest_loan=("loan_amount", "min"))
    if len(rr):
        c1.markdown("**Who gets reviewed**")
        rr = rr.rename(index=PRODUCT_NAMES).rename_axis("Product").reset_index()
        c1.dataframe(styled(rr, {"reviews": "{:,.0f}", "pd_from": "{:.1%}", "pd_to": "{:.1%}", "smallest_loan": "{:,.0f}"}), hide_index=True, use_container_width=True)

with tab2:
    fair = load("fairness")
    pol = st.selectbox("Policy", list(fair.policy.unique()), index=1)
    att = st.radio("Group by", ["Sex", "Age band"], horizontal=True)
    sub = fair[(fair.policy == pol) & (fair.attribute == att)].copy()
    if att == "Sex":
        sub["group"] = sub.group.map({"F": "Female", "M": "Male"}).fillna(sub.group)
    st.plotly_chart(charts.fairness_bars(sub, att.lower(), title=f"{pol}: approval-rate ratio by {att.lower()} (lowest {sub.approval_rate_ratio.min():.2f})"), use_container_width=True)
    st.dataframe(styled(sub[["group", "applications", "approval_rate", "approval_rate_ratio", "observed_bad_rate", "bad_rate_approved", "mean_pd", "calibration_ratio"]],
                        {"applications": "{:,.0f}", "approval_rate": "{:.1%}", "approval_rate_ratio": "{:.2f}", "observed_bad_rate": "{:.2%}",
                         "bad_rate_approved": "{:.2%}", "mean_pd": "{:.2%}", "calibration_ratio": "{:.2f}"}), hide_index=True, use_container_width=True)
    pr = load("proxy_check")
    st.caption("Proxy check (notebook 02): the 90 model inputs predict " + "; ".join(f"{r.attribute.lower()} with AUC {r.auc_from_model_inputs:.2f}" for r in pr.itertuples())
               + " (0.5 = no information). Excluding an attribute does not stop proxies, so outcomes are tested by group.")

with tab3:
    mon = load("monitoring_monthly")
    c1, c2 = st.columns(2)
    c1.plotly_chart(charts.monitor_lines(mon, "psi", "Score PSI stayed below the investigate line, even through COVID", "PSI of each model's PD vs the training window by month",
                                         fmt=".3f", bands=((0.10, "investigate", charts.STATUS["warning"]), (0.25, "act", charts.STATUS["critical"]))), use_container_width=True)
    c2.plotly_chart(charts.monitor_lines(mon[mon.decision_month >= 201911], "gini", "Rank-ordering held up through the shock", "Gini by decision month, out-of-sample months only", fmt=".3f"),
                    use_container_width=True)
    c1.plotly_chart(charts.monitor_lines(mon, "calibration_ratio", "The PD level drifted with the population", "Mean predicted PD ÷ observed bad rate by month (1.0 = calibrated)", fmt=".2f",
                                         bands=((0.8, "0.80", charts.STATUS["warning"]), (1.25, "1.25", charts.STATUS["warning"]))), use_container_width=True)
    c2.plotly_chart(charts.monitor_lines(mon, "approval_rate_cost_rule", "Approval rate under the same rule moved with the mix", "Share approved by the cost-based rule by month", fmt=".1%"),
                    use_container_width=True)
    csi = load("csi_flags")
    st.markdown("**Inputs that drifted (characteristic stability index ≥ 0.10)**")
    st.dataframe(styled(csi, {"max_csi": "{:.2f}"}), hide_index=True, use_container_width=True)
    st.markdown("""
| Metric | Frequency | Investigate | Act | Owner |
|---|---|---|---|---|
| Score PSI vs development sample | monthly | ≥ 0.10 | ≥ 0.25 | Risk analytics |
| Feature CSI (top inputs) | monthly | ≥ 0.10 | ≥ 0.25 | Risk analytics |
| Approval rate under the rule | weekly | ± 3 pp vs plan | ± 5 pp | Credit policy |
| Calibration ratio (mature vintages) | monthly | outside 0.8 to 1.25 | two months in a row | Model validation |
| Gini (mature vintages) | quarterly | 5 points below validation | 10 points below | Model validation |
| Override rate and override bad rate | monthly | > 5% of decisions | override bad rate above model-approved | Credit policy |
| Review hit rate | monthly | 25% below assumption | - | Underwriting operations |
""")

with tab4:
    mv, room = m["model_value"], m["room"][CH]
    rec = pd.DataFrame([
        {"For": "Head of Credit Policy", "Do": "Replace any fixed or 0.5 cut-off with the cost-based rule: product break-evens of 25% (cash), 14% (cards), 8% (point-of-sale)",
         "Expected impact": f"decline {room['declined_share']:.1%} of today's approvals (bad rate {room['tail_bad_rate']:.0%}); total cost of wrong decisions {-m['loss_curve'][CH]['rule_cost_saving_vs_default']:.0%} vs 0.5",
         "Measure": "approval rate, bad rate of approved loans by vintage, net profit", "Risk": "margins are assumptions; Finance must sign off the cost matrix"},
        {"For": "Model Risk / Validation", "Do": "Validate the challenger and run it as a champion/challenger test (20% of traffic, stratified by product)",
         "Expected impact": f"{100 * mv['same_bad_rate']['extra_approvals_pp']:+.1f} pp approvals at the scorecard's bad rate",
         "Measure": "30+ days past due at month 3, then full default; pre-registered decision rule", "Risk": "less transparent than the scorecard; requires SHAP reason codes in production"},
        {"For": "Credit Policy + Finance", "Do": "Run a below-cut-off test: approve a random 10% of the declined band with capped amounts",
         "Expected impact": "measures the bad rate of today's rejects, the number that decides whether approvals can rise at a flat bad rate",
         "Measure": "bad rate of test approvals vs the declined tail", "Risk": f"about {m['test_design']['below_cutoff_loans_needed']:,} test loans; expected cost ≈ {charts.fmt_money(m['test_design']['price_of_information'])}"},
        {"For": "Underwriting operations", "Do": "Route the grey zone to manual review within capacity; log review outcomes",
         "Expected impact": f"{m['three_tier']['totals']['reviews_per_month']:,.0f} reviews a month; {charts.fmt_money(m['three_tier']['uplift_vs_two_tier'])} a quarter if reviewers catch 40% of bads",
         "Measure": "review hit rate, review cost per case, turnaround time", "Risk": "value depends on the reviewer hit rate, which is not yet measured"},
        {"For": "Compliance", "Do": "Approve the excluded-attribute list and the adverse-action reason library; review age-band outcomes",
         "Expected impact": "documented fair-lending position before go-live", "Measure": "approval-rate ratio by sex and age band each quarter",
         "Risk": "inputs still carry age information (proxy AUC 0.84)"},
        {"For": "Risk analytics", "Do": "Monthly monitoring pack (PSI, CSI, calibration, approval rate, overrides) with the triggers above",
         "Expected impact": "input shifts caught within a month; outcome shifts within one to three months via early delinquency", "Measure": "alerts raised and actioned",
         "Risk": "score stability alone missed the 2020 outcome shift; calibration needs mature vintages"},
    ])
    st.dataframe(rec, hide_index=True, use_container_width=True)

how_to_read("""
**Three tiers.** Each application goes to the action with the highest expected value: approve, decline, or send to a person. A review costs money
and a reviewer only catches some of the bad applicants, so review is worth it only in the grey zone near the break-even PD *and* for loans large
enough to justify the cost; small point-of-sale loans never qualify. If more applications qualify than the team can handle, the most valuable
reviews are kept. Move the sliders: a better reviewer or a cheaper review widens the grey zone.

**Fair lending.** The *approval-rate ratio* compares each group's approval rate with the most-approved group; below 0.80 (the "four-fifths"
screen) is a trigger for review, not a legal verdict. Look at the bad rates next to it: younger applicants are approved less often because they
default more often in this book, and the calibration ratio shows whether the model over- or under-states their risk.

**Monitoring.** PSI (population stability index) compares this month's score distribution with the one the model was built on; CSI does the same
for one input. They react as soon as applicants change, before any defaults are observed. Gini and calibration need outcomes, so they lag. The
COVID months are the lesson: score PSI stayed below 0.10, yet the bad rate halved and predicted PDs ran well above actual. Only calibration showed
it, months later, while feature CSI caught a data-capture break (the employment field) at once. Hence the plan tracks an early outcome (30+ days
past due at month 3) next to PSI, and treats "PSI fine, calibration off, Gini fine" as a level problem: re-check cut-offs and calibration, do not
rebuild the model.
""")
