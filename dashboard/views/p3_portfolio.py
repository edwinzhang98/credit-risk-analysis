import numpy as np
import pandas as pd
import streamlit as st

from common import how_to_read, load, page_header
from src import charts
from src.economics import PRODUCT_NAMES
from src.metrics import wilson_interval

page_header("Portfolio snapshot", "Where is the risk in the booked portfolio, and is the picture stable over time?")

cube = load("portfolio_cube")
WINDOWS = {"Train (Jan-Oct 2019)": "train", "Validation (Nov-Dec 2019)": "valid", "Out-of-time test (Jan-Mar 2020)": "test", "Monitoring (Apr-Oct 2020)": "monitor"}
c1, c2, c3 = st.columns([1.4, 1.2, 1.4])
segment = c1.selectbox("Break the bad rate down by", list(cube.segment.unique()), index=1)
windows = c2.multiselect("Period", list(WINDOWS), default=list(WINDOWS)[:3])
products = c3.multiselect("Product", list(PRODUCT_NAMES), default=list(PRODUCT_NAMES), format_func=lambda k: PRODUCT_NAMES[k])

d = cube[(cube.segment == segment) & cube.split.isin([WINDOWS[w] for w in windows]) & cube.product_type.isin(products)]
if d.empty:
    st.warning("No loans match these filters.")
    st.stop()
agg = d.groupby("value", observed=True).agg(loans=("loans", "sum"), bads=("bads", "sum"), amount=("amount", "sum")).reset_index()
agg["bad_rate"] = agg.bads / agg.loans
agg["share"] = agg.loans / agg.loans.sum()
lo, hi = wilson_interval(agg.bads, agg.loans)
agg["ci_low"], agg["ci_high"] = lo, hi
order = {"< 15K": 0, "15K-30K": 1, "30K-60K": 2, "60K-100K": 3, "100K+": 4, "< 10%": 0, "10-20%": 1, "20-30%": 2, "30-50%": 3, "50%+": 4,
         "No history": -1, "On time": 0, "1-5 days": 1, "6-30 days": 2, "31+ days": 3, "0": 0, "1": 1, "2-3": 2, "4+": 3,
         "≤ 6 months": 0, "7-12 months": 1, "13-24 months": 2, "25+ months": 3, "18-24": 0, "25-34": 1, "35-44": 2, "45-54": 3, "55-64": 4, "65+": 5}
agg = agg.assign(o=agg.value.map(order).fillna(99)).sort_values(["o", "value"]).drop(columns="o")
overall = agg.bads.sum() / agg.loans.sum()

st.plotly_chart(charts.segment_bad_rate(agg, segment, overall), use_container_width=True)
small = agg[agg.loans < 1000]
if len(small):
    st.caption(f"Small segments (fewer than 1,000 loans: {', '.join(small.value)}) have wide intervals; read their bad rate with care.")

trend = d.groupby(["decision_month", "value"], observed=True).agg(loans=("loans", "sum"), bads=("bads", "sum")).reset_index()
trend["bad_rate"] = trend.bads / trend.loans
top_vals = agg.sort_values("loans", ascending=False).value.head(6).tolist()
trend = trend[trend.value.isin(top_vals)]
trend["value"] = pd.Categorical(trend.value, categories=[v for v in agg.value if v in top_vals], ordered=True)
st.plotly_chart(charts.segment_trend(trend.sort_values(["value", "decision_month"]), segment), use_container_width=True)

with st.expander("Table"):
    st.dataframe(agg.rename(columns={"value": segment}).round(4), hide_index=True, use_container_width=True)

how_to_read("""
**What you are looking at.** The left chart shows, for each group, the share of booked loans that later defaulted ("bad rate"). The thin
whiskers are 95% confidence intervals: if a whisker is long, the group is small and its bad rate is uncertain. The right chart shows how much
of the portfolio each group represents. The line chart below shows the same bad rates month by month.

**What to try.** Switch the breakdown to *Worst lateness, 24 months* or *Rejections, last 12 months*: past repayment
behaviour separates good and bad customers far more than loan size or income does, which is why it dominates both models. Switch the period to
*Monitoring* to see the whole portfolio's bad rate drop after April 2020.

**What it is not.** These are correlations in loans the lender already approved. They do not say that, for example, a longer loan term *causes*
default, and they say nothing about applicants the lender rejected. Age and sex are shown only because fair-lending monitoring requires it;
they are not used in any model.
""")
