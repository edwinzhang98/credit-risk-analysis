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
        st.markdown("**Manual review assumptions** (not in the data; to be measured from review outcomes). At 300 CU a review and a 10% good-decline rate, the gain over the two-tier rule ranges from 1.8M to 32.0M CU a quarter across 20%-60% catch rates.")
        c1, c2, c3, c4 = st.columns(4)
        cost = c1.slider("Cost per review (CU)", 50, 1500, int(rev0.cost_per_case), 50)
        catch = c2.slider("Share of bad applicants a reviewer declines", 0.10, 0.80, float(rev0.bad_catch_rate), 0.05)
        gdec = c3.slider("Share of good applicants a reviewer declines", 0.00, 0.40, float(rev0.good_decline_rate), 0.01)
        cap = c4.slider("Review capacity (share of each month's applications)", 0.00, 0.15, float(rev0.capacity_share), 0.005, format="%.3f")
    rv = Review(cost, catch, gdec, cap)
    tiers = assign_tiers(pH, g, l, rv, capacity_share=cap, groups=T.decision_month.to_numpy())  # cap applied month by month
    wanted = int((assign_tiers(pH, g, l, rv, capacity=None) == 1).sum())
    tab, tot = tier_outcomes(tiers, y, g, l, amt, rv, months=MONTHS)
    two = evaluate_policy(approve_ev_positive(pH, g, l), y, g, l)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Approval rate (after review)", f"{tot['approval_rate']:.1%}")
    k2.metric("Bad rate of approved loans", f"{tot['bad_rate_approved']:.2%}")
    k3.metric("Reviews per month", f"{tot['reviews_per_month']:,.0f}", help=f"Capacity: {cap:.1%} of each month's applications ({cap * len(T) / MONTHS:,.0f} reviews a month on average); {wanted / MONTHS:,.0f} a month "
              "would be worth reviewing, so the most valuable are kept within each month's cap. Booked-loan volume.")
    k4.metric("Net profit vs two-tier rule", charts.fmt_money(tot["net_profit"]), charts.fmt_money(tot["net_profit"] - two["net_profit"]))
    empty_title = None
    if (tiers == 1).sum() == 0:
        empty_title = "No review capacity is set, so no application goes to review" if cap == 0 and wanted else "No application is worth reviewing with these settings"
    st.plotly_chart(charts.tier_bars(tab, title=empty_title), use_container_width=True)
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
               + f" (0.5 = no information). For age 50+, AUC is {m['leakage']['proxy_auc_age50']:.2f} with all inputs; "
               f"{m['leakage']['proxy_auc_age50_without']['Years with current employer']:.2f} without years with current employer; "
               f"{m['leakage']['proxy_auc_age50_without']['Product type and share of past cash applications']:.2f} without product type and share of past cash applications; "
               f"{m['leakage']['proxy_auc_age50_without']['Loan size, payment and income (7 inputs)']:.2f} without the 7 loan-size, payment and income inputs. "
               "Excluding an attribute does not stop proxies, so outcomes are tested by group.")

with tab3:
    mon = load("monitoring_monthly")
    c1, c2 = st.columns(2)
    c1.plotly_chart(charts.monitor_lines(mon, "psi", "Challenger PSI stayed below 0.10; the scorecard's crossed it from May 2020", "PSI of each model's PD vs the training window by month",
                                         fmt=".3f", bands=((0.10, "investigate", charts.STATUS["warning"]), (0.25, "act", charts.STATUS["critical"]))), use_container_width=True)
    c2.plotly_chart(charts.monitor_lines(mon[mon.decision_month >= 201911], "gini", "Rank-ordering held up through the shock", "Gini by decision month, out-of-sample months only", fmt=".3f"),
                    use_container_width=True)
    oos = mon[mon.decision_month >= 201911]
    c1.plotly_chart(charts.monitor_lines(oos, "calibration_ratio", charts.calibration_drift_title(oos),
                                         "Mean predicted PD ÷ observed bad rate by month (1.0 = calibrated; Nov-Dec 2019 is the calibration window; Oct 2020 = 1-5 Oct)", fmt=".2f",
                                         bands=((0.8, "0.80", charts.STATUS["warning"]), (1.25, "1.25", charts.STATUS["warning"]))), use_container_width=True)
    recent = mon[mon.decision_month >= 202001].approval_rate_cost_rule
    fig_ar = charts.monitor_lines(oos, "approval_rate_cost_rule",
                                  f"Approval rates under the rule stayed between {recent.min():.0%} and {recent.max():.0%} for both models, so they did not flag the April 2020 shift",
                                  "Share approved by the cost-based rule by decision month (%)", fmt=".1%")
    fig_ar.update_yaxes(tickformat=".0%")
    c2.plotly_chart(fig_ar, use_container_width=True)
    csi = load("csi_flags")
    st.markdown("**Inputs that drifted (characteristic stability index ≥ 0.10)**")
    st.dataframe(styled(csi, {"max_csi": "{:.2f}"}), hide_index=True, use_container_width=True)
    st.markdown("""
| Metric | Frequency | Investigate | Act | Owner |
|---|---|---|---|---|
| Score PSI vs development sample | monthly | ≥ 0.10 | ≥ 0.25 | Risk analytics |
| Feature CSI (12 most influential inputs, every categorical input, inputs already shifting) | monthly | ≥ 0.10 | ≥ 0.25 | Risk analytics |
| Approval rate under the rule | weekly | ± 3 pp vs plan | ± 5 pp | Credit policy |
| Early delinquency (30+ days past due at month 3) vs expected | monthly | + 20% vs expected | + 40% | Risk analytics |
| Calibration ratio (mature vintages) | monthly | outside 0.8 to 1.25 | two months in a row | Model validation |
| Gini (mature vintages) | quarterly | 5 points below validation | 10 points below | Model validation |
| Override rate and override bad rate | monthly | > 5% of decisions | override bad rate above model-approved | Credit policy |
| Reviewer catch rate (1 − bads among review approvals ÷ bads expected in the reviewed pool) | monthly, as outcomes mature | below 30% (25% under the 40% assumption) | - | Underwriting operations |

The early-delinquency triggers (+20% to investigate, +40% to act) are proposals in `config.yaml` `proposals`, to be agreed before launch.
""")

with tab4:
    mv, room = m["model_value"], m["room"][CH]
    rec = pd.DataFrame([
        {"For": "Head of Credit Policy", "Do": "Adopt the cost-based rule as the cut-off policy, once Finance confirms the margins: product break-evens of 25% (cash), 14% (cards), 8% (point-of-sale)",
         "Expected impact": f"decline {room['declined_share']:.1%} of today's approvals (bad rate {room['tail_bad_rate']:.1%}); total cost of wrong decisions {m['vs_today'][CH]['total_cost_change']:+.0%} vs today's policy",
         "Measure": "approval rate, bad rate of approved loans by vintage, net profit", "Risk": "margins are assumptions; Finance must sign off the cost matrix"},
        {"For": "Model Risk / Validation", "Do": "Validate the challenger and run a champion/challenger test of the two-tier cost rules (20% of traffic, stratified by product); pilot manual review separately outside the trial arms",
         "Expected impact": f"under the two-tier cost rules, {-100 * m['model_value']['rule_vs_rule']['approval_rate_change']:.1f} pp fewer approvals than the champion rule; approved-book bad rate {m['loss_curve'][CH]['rule']['bad_rate_approved']:.2%} vs {m['loss_curve'][CP]['rule']['bad_rate_approved']:.2%} ({-100 * m['model_value']['rule_vs_rule']['bad_rate_change']:.1f} pp lower); +{charts.fmt_money(m['model_value']['rule_vs_rule']['net_profit_change'])} modelled net profit and {charts.fmt_money(-m['model_value']['rule_vs_rule']['credit_loss_change'])} lower modelled credit losses a quarter",
         "Measure": f"sized to detect {m['loss_curve'][CH]['rule']['bad_rate_approved']:.2%} vs {m['loss_curve'][CP]['rule']['bad_rate_approved']:.2%}: {m['test_design']['champion_challenger_loans_challenger']:,} approved challenger loans and {m['test_design']['champion_challenger_loans_champion']:,} approved champion loans; 30+ days past due at month 3, then full default; proposed bad-rate tolerance 0.2 pp (`config.yaml` `proposals`), to be agreed before launch", "Risk": "less transparent than the scorecard; requires SHAP reason codes in production"},
        {"For": "Credit Policy + Finance", "Do": "Run a below-cut-off test: approve a random sample of applicants just below today's approval line (applicants the current policy rejects), with capped amounts",
         "Expected impact": f"measures the bad rate of today's rejects; if the true rate is the 25%-lower target ({m['test_pass']['swap_in_bad_rate']:.1%}), about {m['test_pass']['new_approvals_per_decline']:.1f} new approvals per declined tail loan, about {m['test_pass']['net_change_per_quarter']:+,.0f} more loans a quarter; expansion is sized on the measured rate",
         "Measure": f"exact one-sided 2.5% binomial test with at least 80% power at the target; passes if at most {m['test_design']['below_cutoff_pass_max_defaults']} of {m['test_design']['below_cutoff_loans_needed']:,} approved loans default ({m['test_design']['below_cutoff_pass_max_rate']:.1%}); passes {m['test_design']['below_cutoff_power_at_target']:.0%} of the time if the true rate is {m['test_pass']['swap_in_bad_rate']:.1%}", "Risk": f"about {m['test_design']['below_cutoff_loans_needed']:,} test loans; expected net cost ≈ {charts.fmt_money(m['test_design']['price_of_information'])} on the declined tail's economics, likely an underestimate because today's rejects are probably riskier"},
        {"For": "Underwriting operations", "Do": "Pilot the grey zone separately outside the trial arms, within 5% of each month's applications; log review outcomes and measure the catch rate before counting the gain",
         "Expected impact": f"{m['three_tier']['totals']['reviews_per_month']:,.0f} reviews a month on average on booked-loan volume (reset on through-the-door volume); monthly caps {m['three_tier']['capacity_by_month']['202001']:,} / {m['three_tier']['capacity_by_month']['202002']:,} / {m['three_tier']['capacity_by_month']['202003']:,} for Jan / Feb / Mar 2020; {charts.fmt_money(m['three_tier']['uplift_vs_two_tier'])} a quarter at 40% catch, 10% good-decline and 300 CU a review; 1.8M to 32.0M CU at 20%-60% catch with 10% good-decline",
         "Measure": "reviewer catch rate, review cost per case, turnaround time", "Risk": "value depends on the reviewer catch rate, which is not yet measured"},
        {"For": "Compliance", "Do": "Approve the excluded-attribute list and the adverse-action reason library; review age-band outcomes",
         "Expected impact": "documented fair-lending position before go-live; Compliance to confirm lawful remedies", "Measure": "approval-rate ratio and calibration by sex and age band each quarter",
         "Risk": "inputs still carry age information (proxy AUC 0.84)"},
        {"For": "Risk analytics", "Do": "Monthly monitoring pack (PSI, CSI, calibration, approval rate, overrides) with the triggers above",
         "Expected impact": "applicant-mix checks monthly; early delinquency once vintages reach month 3 on book (detection speed not back-tested)", "Measure": "alerts raised and actioned",
         "Risk": "score stability alone missed the 2020 outcome shift; calibration needs mature vintages"},
    ])
    st.dataframe(rec, hide_index=True, use_container_width=True)

how_to_read("""
**Three tiers.** Each application goes to the action with the highest expected value: approve, decline, or send to a person. A review costs money
and a reviewer only catches some of the bad applicants, so review is worth it only in the grey zone near the break-even PD *and* for loans large
enough to justify the cost; small point-of-sale loans never qualify. Capacity is 5% of each month's applications at the default setting; if more applications qualify than the team can handle, the most valuable
reviews are kept within each month's cap. Losses are modelled at the assumed 60% loss rate. Move the sliders: a better reviewer or a cheaper review widens the grey zone.

**Fair lending.** The *approval-rate ratio* compares each group's approval rate with the most-approved group; below 0.80 (the "four-fifths"
screen) is a trigger for review, not a legal verdict. Approval-rate parity passes this screen. Look at the bad rates next to it: younger applicants were approved less often and had higher observed default rates;
their risk is also under-predicted (calibration ratio about 0.73), and so is men's. Compliance must confirm which remedies are lawful in the relevant jurisdiction.

**Monitoring.** PSI (population stability index) compares this month's score distribution with the one the model was built on; CSI does the same
for one input. They track applicant-mix changes before defaults are observed; detection speed was not back-tested. Gini and calibration need outcomes, so they lag. The
COVID months are the lesson: the challenger's score PSI stayed below 0.10 (the scorecard's reached about 0.15, in step with the employment field's
collapse), yet the bad rate halved and predicted PDs ran well above actual. Retrospective monthly checks show the calibration shift and the
data-capture break in the employment field. The fall in the bad rate may reflect COVID-era measures, the lender's own tightening or loans
too recent to have defaulted (the outcome horizon is not disclosed); the data cannot separate these, so the back-test is illustrative. Hence the
plan tracks an early outcome (30+ days past due at month 3) next to PSI, and treats "PSI fine, calibration off, Gini fine" as a level problem: re-check cut-offs and calibration, do not
rebuild the model.
""")
