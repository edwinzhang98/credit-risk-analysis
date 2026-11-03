import numpy as np
import pandas as pd
import streamlit as st

from common import base_economics, how_to_read, load, page_header, styled
from src import charts
from src.strategy import (approve_at_rate, approve_below, approve_ev_positive, evaluate_policy, headroom_table, rate_at_same_bad_rate,
                          swap_set, swap_summary)

page_header("Swap-set analysis", "If the policy changes, who moves from declined to approved, who moves the other way, and what are they worth?")

T = load("predictions_test")
y, amt = T.target.to_numpy(), T.loan_amount.to_numpy()
econ = base_economics()
g, l = econ.per_loan(T.loan_amount, T.product_type)
pC, pH = T.pd_champion.to_numpy(), T.pd_challenger.to_numpy()
CH, CP = "Challenger (LightGBM)", "Champion (scorecard)"
B = y.mean()

mode = st.radio("Question", ["1 · Move the cut-off on today's book", "2 · Switch from the scorecard to the challenger"], horizontal=True)

def fmt_swap(sw):
    out = sw[["cell", "applications", "share", "bads", "bad_rate", "bad_rate_ci_low", "bad_rate_ci_high", "loan_amount", "credit_loss_if_approved", "net_value_if_approved"]].copy()
    return styled(out, {"applications": "{:,.0f}", "share": "{:.1%}", "bads": "{:,.0f}", "bad_rate": "{:.2%}", "bad_rate_ci_low": "{:.2%}", "bad_rate_ci_high": "{:.2%}",
                        "loan_amount": "{:,.0f}", "credit_loss_if_approved": "{:,.0f}", "net_value_if_approved": "{:,.0f}"})


if mode.startswith("1"):
    c1, c2 = st.columns(2)
    model = c1.radio("Model used for the new cut-off", [CH, CP], horizontal=True)
    p = pC if model == CP else pH
    rule_kind = c2.radio("New cut-off", ["Cost-based rule (product break-evens)", "Single PD cut-off"], horizontal=True)
    if rule_kind.startswith("Single"):
        cut = st.slider("Decline if predicted PD is at or above", 0.02, 0.50, 0.15, 0.005, format="%.3f")
        new = approve_below(p, cut)
    else:
        new = approve_ev_positive(p, g, l)
    cur = np.ones(len(T), bool)
    sw = swap_set(cur, new, y, amt, g, l)
    out = sw[sw.cell.str.startswith("Swap-out")].iloc[0]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Applications declined (swap-outs)", f"{out.applications:,.0f}", help=f"{out.share:.1%} of the loans the historical policy approved")
    k2.metric("Their bad rate", f"{out.bad_rate:.1%}", help=f"Whole book: {B:.2%}; 95% interval {out.bad_rate_ci_low:.1%} to {out.bad_rate_ci_high:.1%}")
    k3.metric("Book bad rate after", f"{y[new].mean():.2%}", f"{100 * (y[new].mean() - B):+.2f} pp", delta_color="inverse")
    k4.metric("Net value of declining them", charts.fmt_money(-out.net_value_if_approved),
              help="Modelled credit losses avoided at the assumed 60% loss rate minus margin forgone on the declined good customers, over the quarter.")
    st.dataframe(fmt_swap(sw[sw.applications > 0]), hide_index=True, use_container_width=True)

    st.markdown("**Can the room be spent on more approvals?** Only applicants the lender rejected in the past could be added, and their bad rate is not "
                "in the data. Choose an assumption for it to see how many new approvals each declined loan pays for at an unchanged book bad rate:")
    r_mult = st.slider("Assumed bad rate of newly approved applicants, as a multiple of today's book bad rate", 1.5, 6.0, 2.0, 0.1,
                       help="Below about 2x the exchange rate explodes (more than 3 new approvals per declined loan) and would soon exceed the volume the lender rejects today.")
    r = r_mult * B
    h = headroom_table(B, float(out.bad_rate), int(out.applications), [r]).iloc[0]
    k1, k2, k3 = st.columns(3)
    k1.metric("Assumed bad rate of new approvals", f"{r:.1%}")
    if out.applications < 500 or out.bad_rate <= B:
        st.warning(f"Only {out.applications:,.0f} loans are declined at this cut-off, at a bad rate of {out.bad_rate:.1%}: too few, or not risky enough, "
                   "to fund new approvals. Lower the cut-off to see the exchange rate.")
    elif np.isfinite(h.new_approvals_per_decline):
        k2.metric("New approvals per declined loan", f"{h.new_approvals_per_decline:.2f}")
        k3.metric("Net change in approvals per month", f"{h.net_change_in_approvals / 3:+,.0f}", help="Booked-loan volume; an upper bound, limited by how many applicants the lender rejects today.")
    grid = headroom_table(B, float(out.bad_rate), int(out.applications), np.linspace(B * 1.02, float(out.bad_rate) * 1.15, 60))
    fig = charts.headroom_chart(grid, B, float(out.bad_rate))
    if np.isfinite(h.new_approvals_per_decline):
        fig.add_trace(charts._marker(r, h.new_approvals_per_decline, "your assumption", charts.ORANGE, text="your assumption", textpos="top right"))
    st.plotly_chart(fig, use_container_width=True)
else:
    c1, c2 = st.columns(2)
    sq = c1.radio("Status quo", ["Champion scorecard, cost-based rule", "Champion scorecard at an approval rate"], horizontal=False)
    if sq.endswith("rule"):
        cur = approve_ev_positive(pC, g, l)
    else:
        rate = c1.slider("Champion approval rate", 0.80, 0.995, 0.95, 0.005, format="%.3f")
        cur = approve_at_rate(pC, rate)
    match = c2.radio("Use the challenger at...", ["the same approval rate", "the same bad rate", "its own cost-based rule"])
    if match == "the same approval rate":
        new = approve_at_rate(pH, cur.mean())
    elif match == "the same bad rate":
        new = approve_at_rate(pH, rate_at_same_bad_rate(pH, y, y[cur].mean()))
    else:
        new = approve_ev_positive(pH, g, l)
    sw = swap_set(cur, new, y, amt, g, l)
    summ = swap_summary(cur, new, y, g, l, amt)
    s = summ.set_index("metric")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Approval rate", f"{s.loc['approval_rate', 'proposed']:.1%}", f"{100 * s.loc['approval_rate', 'change']:+.1f} pp")
    k2.metric("Bad rate of approved loans", f"{s.loc['bad_rate_approved', 'proposed']:.2%}", f"{100 * s.loc['bad_rate_approved', 'change']:+.2f} pp", delta_color="inverse")
    k3.metric("Modelled credit losses (60% loss rate)", charts.fmt_money(s.loc["credit_loss", "proposed"]), charts.fmt_money(s.loc["credit_loss", "change"]), delta_color="inverse")
    k4.metric("Net profit", charts.fmt_money(s.loc["net_profit", "proposed"]), charts.fmt_money(s.loc["net_profit", "change"]))
    c1, c2 = st.columns([1.1, 1])
    status = "the champion's cost-based rule" if sq.endswith("rule") else f"the champion approving {cur.mean():.1%}"
    c1.plotly_chart(charts.swap_bars(sw, subtitle=f"Status quo: {status}; proposed: the challenger at {match}. Bad rate (%) with 95% intervals; axis labels = applications"),
                    use_container_width=True)
    c2.markdown("**The 2 × 2 swap set**")
    c2.dataframe(fmt_swap(sw), hide_index=True, use_container_width=True)
    prof = T.assign(cell=np.select([cur & new, ~cur & new, cur & ~new], ["Approved by both", "Swap-in", "Swap-out"], "Declined by both"))
    prof = prof.groupby("cell").agg(applications=("target", "size"), bad_rate=("target", "mean"), median_amount=("loan_amount", "median"),
                                    share_cash=("product_type", lambda v: (v == "CAL").mean()), share_new_to_lender=("is_new_to_lender", "mean"),
                                    mean_pd_champion=("pd_champion", "mean"), mean_pd_challenger=("pd_challenger", "mean"))
    c2.markdown("**Who they are**")
    prof = prof.reindex(["Swap-in", "Swap-out", "Approved by both", "Declined by both"]).reset_index()
    c2.dataframe(styled(prof, {"applications": "{:,.0f}", "bad_rate": "{:.2%}", "median_amount": "{:,.0f}", "share_cash": "{:.1%}", "share_new_to_lender": "{:.1%}",
                               "mean_pd_champion": "{:.2%}", "mean_pd_challenger": "{:.2%}"}), hide_index=True, use_container_width=True)

how_to_read("""
A **swap set** shows which decisions change between the two models. Every application lands in one of four cells: approved under both
policies, declined under both, **swap-in** (declined today, approved tomorrow) or **swap-out** (approved today, declined tomorrow). A change is worth making when swap-outs default much more often than swap-ins, and the money column says by how much. At the assumed 60% loss rate, defaults imply the modelled losses shown.

**Question 1, today's book.** The status quo is what actually happened: every loan in the data was approved. Tightening the cut-off only
creates swap-outs, and we can see exactly how they performed. Loosening would create swap-ins from people the lender rejected in the past;
they are not in the data, so the headroom chart turns the question around: *if* those applicants defaulted at a given rate, how many could be
approved per declined loan at an unchanged bad rate? The answer depends entirely on an unobserved number, which is why the recommendation is a
small, controlled below-cut-off test.

**Question 2, a model change.** Both models score the same booked loans, so swap-ins and swap-outs are both observed. "Same approval rate"
asks: approving the same number of people, does the new model pick safer ones? "Same bad rate" asks: holding risk constant, how many more people
can be approved? The same-bad-rate comparison is matched after the fact on booked test loans; it needs its own cut-off fixed in advance and its own test (the trial compares the two cost-based rules).
""")
