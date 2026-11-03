import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import CFG, ROOT, how_to_read, kpi_row, load, metrics, page_header, styled
from src import charts

m = metrics()
page_header("Data & quality audit", "Can we trust this data, and was every input really available when the credit decision was made?")

rc, keys, vr = load("dq_row_counts"), load("dq_keys"), load("dq_value_ranges")
off, pit, tr = load("dq_snapshot_offset"), load("dq_point_in_time"), load("dq_time_range")
lk = m["leakage"]

kpi_row([
    ("Booked loans reconciled", f"{m['data']['loans']:,}", "No table holds a loan missing from the base table; tables with several rows per loan are reduced to one row per loan before the join; 47,994 defaults match the dataset README."),
    ("Key and target checks failed", f"{int(keys.violations.sum())}", "Primary keys unique in every table; target is 0/1; 47,994 defaults match the dataset README."),
    ("Raw columns reviewed", f"{lk['raw_columns_reviewed']}", f"{lk['kept']} kept, {lk['rebuilt']} rebuilt point-in-time, {lk['dropped']} dropped and {lk['raw_columns_reviewed'] - lk['kept'] - lk['rebuilt'] - lk['dropped']} kept only to test fair lending, each with a written reason."),
    ("Snapshot taken after the decision", "≈ 14 days", "Event dates run up to 14 days past the decision date, never more; the only later dates are scheduled future due dates (up to 47 days)."),
])

tab1, tab2, tab3, tab4 = st.tabs(["Reconciliation and ranges", "Time coverage", "Look-ahead leakage", "Feature inclusion log"])
with tab1:
    st.markdown("**Row counts by source table** (`sql/dq/dq_01_row_counts.sql`)")
    st.dataframe(styled(rc, {"n_rows": "{:,.0f}", "n_cases": "{:,.0f}", "share_of_base_cases": "{:.1%}", "n_orphan_cases": "{:,.0f}"}), hide_index=True, use_container_width=True)
    st.markdown("**Keys and target** (`sql/dq/dq_02_keys_and_target.sql`)")
    st.dataframe(styled(keys.assign(status=lambda d: d.violations.eq(d.expected).map({True: "pass", False: "FAIL"})), {"violations": "{:,.0f}", "expected": "{:,.0f}"}),
                 hide_index=True, use_container_width=True)
    st.markdown("**Value ranges in the fields that drive money** (`sql/dq/dq_06_value_ranges.sql`)")
    st.dataframe(styled(vr, {"n_loans": "{:,.0f}"}), hide_index=True, use_container_width=True)
with tab2:
    st.plotly_chart(charts.monthly_volume_bad_rate(tr, CFG["split"]), use_container_width=True)
    st.caption("The April 2020 break (volume down about 86% in one month and back to March's level by September; bad rate halved) is why model building stops at "
               "March 2020 and the later months are used to illustrate monitoring. October 2020 covers 1 to 5 October only.")
with tab3:
    st.plotly_chart(charts.snapshot_offset_chart(off), use_container_width=True)
    st.plotly_chart(charts.point_in_time_chart(pit), use_container_width=True)
    abl, grp, biz = load("leakage_ablation"), load("leakage_ablation_groups"), load("leakage_business")
    t = abl[abl.split == "test"]
    st.plotly_chart(charts.ablation_dots(t), use_container_width=True)
    gap_post = lk["gini_post_activity_naive"] - lk["gini_post_activity_pit"]
    gap_rest = lk.get("gini_no_activity_naive", float("nan")) - lk.get("gini_no_activity_pit", float("nan"))
    st.markdown(f"**What the leak does to the model** (notebook 02): with the snapshot fields as provided, out-of-time Gini is **{lk['gini_test_naive_offline']:.3f}** vs "
                f"**{lk['gini_test_pit']:.3f}** point-in-time; with decision-time values swapped in where they can be rebuilt, **{lk['gini_test_naive_decision_time']:.3f}**. "
                f"The naive model's edge is larger among the **{lk['share_post_decision_activity']:.1%}** of clients who did something after the decision "
                f"({gap_post:+.3f} vs {gap_rest:+.3f} Gini elsewhere). The rest comes from clearly leaking snapshot fields that mix pre- and post-decision information; they were dropped, "
                f"at a cost of less than one Gini point.")
    c1, c2 = st.columns(2)
    c1.dataframe(grp.pivot_table(index="model", columns="group", values="gini").rename_axis(index="Model", columns="Out-of-time Gini").round(3), use_container_width=True)
    c2.dataframe(styled(biz, {"approval_rate": "{:.1%}", "expected_bad_rate_of_approved": "{:.2%}", "observed_bad_rate_of_approved": "{:.2%}", "net_profit": "{:,.0f}"}),
                 hide_index=True, use_container_width=True)
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
**Reconciliation** means the numbers add up: no table holds a loan missing from the base table, keys are unique, and the 47,994 defaults match the
data provider's README. All 1,526,659 loans appear once in the main loan table and have an applicant record; the credit-bureau table covers 98.3% of
them and 80% have at least one earlier application. Tables with several rows per loan are reduced to one row per loan before the join (the
applicant's own row; earlier applications aggregated in `sql/03`). Analysts check this first because a bad join silently duplicates or drops customers.

**Look-ahead leakage** is the most important finding on this page. A credit decision can only use what was known when it was made. Here, the
pre-computed "history" fields (applications in the last 30 days, last rejection date, and so on) were measured about two weeks *after* the
decision. Two charts prove it:
- *Snapshot timing:* we recount each client's applications ourselves. The provided "30-day" count agrees with a count ending at the decision date
  for 90.1% of loans, rising to 92.5%, 96.7% and 98.4% for windows ending 7, 14 and 21 days later. The earlier-applications table holds nothing
  with event dates more than 14 days after the decision, so the +21-day window cannot add later applications (it only starts later). The test shows the fields
  were measured at least 14 days after the decision. Event dates run up to 14 days past the decision date, never more; the only later dates are scheduled future due dates (up to 47 days). We therefore assume a 14-day snapshot offset.
- *Point-in-time check:* for each dated field, the blue dot is the default rate when the event happened before the decision, the orange dot when it
  happened after. After-decision events (for example a rejection elsewhere a week later) go with much higher default rates. These
  fields are not available at decision time and overstate offline performance.

**What we did about it:** dated histories were rebuilt from the previous-applications table using only applications created *before* the
decision date; clearly leaking fields were dropped. Some retained long-window snapshot summaries, measured about 14 days after the decision, still carry residual look-ahead. The feature inclusion log records the decision and reason for every raw column.
""")
