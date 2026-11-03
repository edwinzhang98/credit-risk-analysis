import pandas as pd
import streamlit as st

from common import how_to_read, kpi_row, load, metrics, page_header
from src import charts

m = metrics()
CH, CP = "Challenger (LightGBM)", "Champion (scorecard)"
lc, mv, room, tt = m["loss_curve"][CH], m["model_value"], m["room"][CH], m["three_tier"]

page_header("Credit risk cut-off strategy",
            "Can we approve more applicants without raising the bad rate, and where should the cut-off be?")

st.markdown(
    f"**Request from the Head of Credit Policy:** the business wants a higher approval rate, but the bad rate must not go up. "
    f"Is there room on the current cut-off; who would move from declined to approved and back; how much money is at stake?  \n"
    f"**Data:** {m['data']['loans']:,} booked consumer loans (Home Credit, decisions {m['data']['first_decision']} to {m['data']['last_decision']}), "
    f"{m['data']['bad_rate']:.2%} defaulted. Headline numbers are on the out-of-time test quarter (Jan to Mar 2020, {m['data']['test_loans']:,} loans)."
)

kpi_row([
    ("Cost of wrong decisions vs today's policy", f"{m['vs_today'][CH]['total_cost_change']:.0%}", "Credit losses on approved bads + margin forgone on declined goods: cost-based rule vs approving every booked loan (a 0.5 cut-off does almost the same here)."),
    ("Extra approvals at the same bad rate", f"{100 * mv['same_bad_rate']['extra_approvals_pp']:+.1f} pp", f"Challenger vs champion scorecard at the champion's bad rate: about {mv['same_bad_rate']['extra_approvals_per_month']:,.0f} more loans a month."),
    ("Risky tail declined by the rule", f"{room['declined_share']:.1%}", f"These loans defaulted at {room['tail_bad_rate']:.1%} vs {m['data']['test_bad_rate']:.1%} for the whole book."),
    ("Manual review queue", f"{tt['totals']['reviews_per_month']:,.0f} / month", f"Within a capacity of {tt['capacity_per_month']:,.0f} reviews a month (5% of applications)."),
])

curves = {CP: load("loss_curve_champion"), CH: load("loss_curve_challenger")}
st.plotly_chart(charts.loss_curve(curves, rule_points={CH: lc["rule"]["total_cost"]}, headline=CH, baseline_cost=m["approve_all"]["total_cost"]), use_container_width=True)

st.subheader("The answer in three points")
st.markdown(f"""
1. **Set the cut-off from what a wrong decision costs.** A defaulted loan costs about 60% of its amount; a wrongly declined good customer costs the
   product's margin. That puts the break-even PD at 25% for cash loans, 14% for cards and 8% for point-of-sale loans. Applying it declines
   **{room['declined_share']:.1%}** of applications the historical policy approved and lowers the bad rate of the approved book from
   **{m['data']['test_bad_rate']:.2%}** to **{lc['rule']['bad_rate_approved']:.2%}**.
2. **"More approvals at the same bad rate" needs a better model, plus one test.** Against a rebuilt scorecard applying the same rule, the challenger
   approves **{100 * mv['same_bad_rate']['extra_approvals_pp']:+.1f} pp** more applicants at the scorecard's bad rate. Approving applicants the
   lender rejected in the past cannot be evaluated from this data (their outcomes were never observed): a small below-cut-off test is the way to find out.
3. **Route the grey zone to people, within capacity.** About **{tt['totals']['review_rate']:.1%}** of applications (larger loans near the break-even)
   go to manual review; small point-of-sale loans never do, because a review costs more than it can save.
""")

st.subheader("How the app is organised")
st.markdown("""
| Page | Question it answers |
|---|---|
| **Data & Quality Audit** | Can we trust the data, and was every input available when the decision was made? |
| **Portfolio Snapshot** | Where is the risk in the booked portfolio? |
| **Model & Explainability** | How good are the two models, and why is a given applicant declined? |
| **Cost-based Threshold Simulator** | Which cut-off minimises the cost of wrong decisions, and how sensitive is it to our cost assumptions? |
| **Swap-set Analysis** | Who moves from approved to declined and back, and what are they worth? |
| **Strategy & Monitoring Plan** | How should decisions be routed, is it fair, and how will we know when it stops working? |
""")

how_to_read(f"""
**The chart.** Each line shows, for one model, the total cost of wrong decisions if every applicant with a predicted probability of default (PD)
below the cut-off is approved. "Cost" adds two things: money lost on approved loans that default (credit losses), and profit given up on good
customers who were declined (forgone margin). The comparison that matters is today's policy, which approved every loan in this data; the x marks
the 0.5 cut-off, which lands in the same place because very few applicants have a PD above 50%; the dot marks the cheapest single cut-off. The dotted line is the cost-based rule, which uses a different break-even per product
and does slightly better than any single cut-off.

**Why it matters.** The "best" threshold is a business decision, not a statistical one. It depends on how much a bad loan costs relative to the
margin on a good one, which is why the cut-off is derived from those costs (they are assumptions, adjustable on the Threshold Simulator page).

**Champion vs challenger.** The champion is a logistic-regression scorecard, the kind of model most lenders run in production; the challenger is
a gradient-boosted model (LightGBM). Both use the same 90 inputs, all checked to be available at the moment of the decision.

**One caveat to say out loud.** Every loan in this data was approved by the lender's past policy, so "approval rate" here means the share of
*previously approved* applicants a policy would approve. People the lender rejected in the past are not in the data.
""")
