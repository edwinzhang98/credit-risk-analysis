import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import CFG, ROOT, how_to_read, kpi_row, load, metrics, page_header
from src import charts

m = metrics()
page_header("Data & quality audit", "Can we trust this data, and was every input really available when the credit decision was made?")

rc, keys, vr = load("dq_row_counts"), load("dq_keys"), load("dq_value_ranges")
off, pit, tr = load("dq_snapshot_offset"), load("dq_point_in_time"), load("dq_time_range")
lk = m["leakage"]

kpi_row([
    ("Booked loans reconciled", f"{m['data']['loans']:,}", "Every table joins back to the base table with one row per loan and no orphans."),
    ("Key and target checks failed", f"{int(keys.violations.sum())}", "Primary keys unique in every table; target is 0/1; 47,994 defaults match the dataset README."),
    ("Raw columns reviewed", f"{lk['raw_columns_reviewed']}", f"{lk['kept']} kept, {lk['rebuilt']} rebuilt point-in-time, {lk['dropped']} dropped, each with a written reason."),
    ("Snapshot taken after the decision", "≈ 14 days", "Dated fields run up to exactly 14 days past the decision date, never more."),
])

tab1, tab2, tab3, tab4 = st.tabs(["Reconciliation and ranges", "Time coverage", "Look-ahead leakage", "Feature inclusion log"])
with tab1:
    c1, c2 = st.columns(2)
    c1.markdown("**Row counts by source table** (`sql/dq/dq_01_row_counts.sql`)")
    c1.dataframe(rc, hide_index=True, use_container_width=True)
    c2.markdown("**Keys and target** (`sql/dq/dq_02_keys_and_target.sql`)")
    c2.dataframe(keys.assign(status=lambda d: d.violations.eq(d.expected).map({True: "pass", False: "FAIL"})), hide_index=True, use_container_width=True)
    st.markdown("**Value ranges in the fields that drive money** (`sql/dq/dq_06_value_ranges.sql`)")
    st.dataframe(vr, hide_index=True, use_container_width=True)
with tab2:
    st.plotly_chart(charts.monthly_volume_bad_rate(tr, CFG["split"]), use_container_width=True)
    st.caption("The April 2020 break (volume down about 85%, bad rate halved) is why model building stops at March 2020 and the later months are used to test monitoring.")
with tab3:
    st.plotly_chart(charts.snapshot_offset_chart(off), use_container_width=True)
    st.plotly_chart(charts.point_in_time_chart(pit), use_container_width=True)
    abl, grp, biz = load("leakage_ablation"), load("leakage_ablation_groups"), load("leakage_business")
    t = abl[abl.split == "test"]
    st.markdown(f"**What the leak would have done to the model** (notebook 02): out-of-time Gini **{lk['gini_test_naive_offline']:.3f}** with the snapshot fields as provided "
                f"vs **{lk['gini_test_pit']:.3f}** point-in-time. The difference sits in the **{lk['share_post_decision_activity']:.1%}** of loans whose client did "
                f"something after the decision (Gini {lk['gini_post_activity_naive']:.3f} vs {lk['gini_post_activity_pit']:.3f} in that group).")
    c1, c2 = st.columns(2)
    c1.dataframe(grp.pivot_table(index="model", columns="group", values="gini").round(3), use_container_width=True)
    c2.dataframe(biz.round(4), hide_index=True, use_container_width=True)
with tab4:
    log = pd.read_csv(ROOT / "docs" / "feature_inclusion_log.csv")
    c1, c2 = st.columns([1, 2])
    table = c1.selectbox("Source table", ["All"] + sorted(log.source_table.unique()))
    decision = c2.multiselect("Decision", sorted(log.decision.unique()), default=sorted(log.decision.unique()))
    view = log[log.decision.isin(decision)]
    if table != "All":
        view = view[view.source_table == table]
    st.dataframe(view, hide_index=True, use_container_width=True, height=420)
    st.caption(f"{len(view)} of {len(log)} raw columns shown. Full log: docs/feature_inclusion_log.csv")

how_to_read("""
**Reconciliation** means the numbers add up: the same 1,526,659 loans appear in every table, each once, and the count of defaults matches what
the data provider published. Analysts check this first because a bad join silently duplicates or drops customers.

**Look-ahead leakage** is the most important finding on this page. A credit decision can only use what was known when it was made. Here, the
pre-computed "history" fields (applications in the last 30 days, last rejection date, and so on) were measured about two weeks *after* the
decision. Two charts prove it:
- *Snapshot timing:* we recount each client's applications ourselves. The provided "30-day" count agrees with a count ending at the decision date
  only 90% of the time, but 97 to 98% of the time once the window reaches past the decision.
- *Point-in-time check:* for each dated field, the blue dot is the default rate when the event happened before the decision, the orange dot when it
  happened after. After-decision events (for example a rejection elsewhere a week later) go with much higher default rates: a model fed these
  fields would look good in testing and fail in production.

**What we did about it:** history features were rebuilt from the previous-applications table using only applications created *before* the
decision date; fields that cannot be rebuilt that way were dropped. The feature inclusion log records the decision and reason for every raw column.
""")
