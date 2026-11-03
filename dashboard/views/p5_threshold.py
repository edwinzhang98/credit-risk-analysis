import numpy as np
import pandas as pd
import streamlit as st

from common import base_economics, how_to_read, load, page_header
from src import charts
from src.economics import PRODUCT_NAMES, Economics
from src.strategy import approve_ev_positive, curve_by_threshold, evaluate_policy

page_header("Cost-based threshold simulator", "Which cut-off minimises the cost of wrong decisions, and how sensitive is it to what we assume a bad loan costs?")

T = load("predictions_test")
y = T.target.to_numpy()
CH, CP = "Challenger (LightGBM)", "Champion (scorecard)"
base = base_economics()

with st.container(border=True):
    st.markdown("**Assumptions** (base case from `config.yaml`; move them to see how the answer changes)")
    c1, c2, c3, c4, c5 = st.columns(5)
    m_cal = c1.slider("Margin, cash loans", 0.05, 0.35, float(base.margin_by_product["CAL"]), 0.01, format="%.2f", help="Net lifetime profit of a cash loan that is repaid, as a share of its amount.")
    m_col = c2.slider("Margin, point-of-sale", 0.01, 0.15, float(base.margin_by_product["COL"]), 0.005, format="%.3f")
    m_rel = c3.slider("Margin, revolving", 0.02, 0.25, float(base.margin_by_product["REL"]), 0.01, format="%.2f")
    ead = c4.slider("Exposure at default", 0.50, 1.00, float(base.ead_share), 0.05, format="%.2f", help="Share of the loan still owed when a default happens.")
    lgd = c5.slider("Loss given default", 0.40, 0.95, float(base.lgd), 0.05, format="%.2f", help="Share of that exposure never recovered.")
econ = Economics(lgd=lgd, ead_share=ead, margin_by_product={"CAL": m_cal, "COL": m_col, "REL": m_rel}, margin_default=base.margin_default)
g, l = econ.per_loan(T.loan_amount, T.product_type)

be = econ.breakeven_table()
st.markdown("**Break-even PD by product** = margin ÷ (margin + loss on a bad loan). Declining is only worth it above this PD.  " +
            " · ".join(f"{PRODUCT_NAMES[r.product]}: **{r.breakeven_pd:.1%}** (a bad loan costs {r.cost_ratio:.1f}× a good loan's margin)" for r in be.itertuples()))

c1, c2 = st.columns([1, 2])
model = c1.radio("Model", [CH, CP], horizontal=True)
p = T.pd_challenger.to_numpy() if model == CH else T.pd_champion.to_numpy()
thr = np.unique(np.round(np.r_[np.arange(0.005, 0.30, 0.0025), np.arange(0.30, 0.5001, 0.01), 0.5], 4))
curves = {CP: curve_by_threshold(T.pd_champion.to_numpy(), y, g, l, thr), CH: curve_by_threshold(T.pd_challenger.to_numpy(), y, g, l, thr)}
best = curves[model].loc[curves[model].total_cost.idxmin()]
cut = c2.slider("Explore a single cut-off: approve if predicted PD is below", 0.01, 0.50, float(np.round(best.threshold, 3)), 0.005, format="%.3f")

single = evaluate_policy(p < cut, y, g, l, T.loan_amount.to_numpy())
rule = evaluate_policy(approve_ev_positive(p, g, l), y, g, l, T.loan_amount.to_numpy())
today = evaluate_policy(np.ones(len(p), bool), y, g, l, T.loan_amount.to_numpy())  # today's policy: every booked loan approved

def col(res):
    return [f"{res['approval_rate']:.1%}", f"{res['bad_rate_approved']:.2%}", f"{res['capture_rate']:.1%}", f"{res['false_positive_rate']:.1%}",
            charts.fmt_money(res["credit_loss"]), charts.fmt_money(res["forgone_margin"]), charts.fmt_money(res["total_cost"]), charts.fmt_money(res["net_profit"]),
            f"{res['total_cost'] / today['total_cost'] - 1:+.0%}"]

table = pd.DataFrame({
    "Metric": ["Approval rate", "Bad rate of approved loans", "Defaults kept off the book (capture)", "Good customers declined", "Credit losses",
               "Margin forgone", "Total cost of wrong decisions", "Net profit", "Total cost vs today's policy"],
    "Today's policy (approve every booked loan)": col(today), f"Your cut-off ({cut:.1%})": col(single), "Cost-based rule (product break-evens)": col(rule),
})
st.dataframe(table, hide_index=True, use_container_width=True)

fig = charts.loss_curve(curves, rule_points={model: rule["total_cost"]}, baseline_cost=today["total_cost"],
                        title=f"With these assumptions the cheapest single cut-off is PD {best.threshold:.1%} ({model.split(' (')[0].lower()})",
                        subtitle="Credit losses + forgone margin (million CU) by PD cut-off, out-of-time test Jan to Mar 2020; vertical line = your cut-off")
fig.add_vline(x=cut, line=dict(color=charts.INK_2, width=1))
st.plotly_chart(fig, use_container_width=True)

how_to_read("""
**The cost matrix behind the chart.** Every decision can be wrong in two ways. Approving someone who then defaults costs the part of the
loan that is never recovered (exposure at default × loss given default, about 60% of the amount in the base case). Declining someone who would
have repaid costs the profit that loan would have made (its margin). The total cost of wrong decisions adds the two over all applications.

**Why the cut-off sits far below 50%.** Today's policy approved every loan in this book, and a 0.5 cut-off would do almost the same: a PD of
0.5 is a coin flip and very few applicants are that risky, so it pays for the whole risky tail. Because a bad loan costs several times what a good loan earns, it pays to decline long before 50%.
The break-even PD is where the expected margin of approving exactly equals the expected loss.

**Try this.** Lower the point-of-sale margin: its break-even falls and the rule declines more point-of-sale loans. Raise loss given default: every
break-even falls. The ranking of the two models does not change with the assumptions; the right cut-off does. That is why the assumptions sit in
`config.yaml` and need sign-off from Finance.

**Caveat.** All rates are shares of loans that the lender's past policy approved; the test quarter's predicted PDs run below the actual default rate
(calibration drift), so the realised bad rate of approved loans is a little higher than the model expected.
""")
