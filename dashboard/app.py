"""Credit-risk cut-off strategy · demo app.  Run:  streamlit run dashboard/app.py

Pages follow the story of the analysis. Every page reads small cached files written by the pipeline (`make all`);
nothing is recomputed from raw data here, so the first page renders in a few seconds.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from common import apply_css, require_cache  # noqa: E402

st.set_page_config(page_title="Credit Risk Cut-off Strategy", page_icon=":material/credit_score:", layout="wide", initial_sidebar_state="expanded")
apply_css()

pages = [
    st.Page("views/p1_overview.py", title="Overview", icon=":material/home:", url_path="overview", default=True),
    st.Page("views/p2_data_quality.py", title="Data & Quality Audit", icon=":material/fact_check:", url_path="data_quality"),
    st.Page("views/p3_portfolio.py", title="Portfolio Snapshot", icon=":material/donut_small:", url_path="portfolio"),
    st.Page("views/p4_model.py", title="Model & Explainability", icon=":material/psychology:", url_path="model"),
    st.Page("views/p5_threshold.py", title="Cost-based Threshold Simulator", icon=":material/tune:", url_path="threshold"),
    st.Page("views/p6_swap_set.py", title="Swap-set Analysis", icon=":material/swap_horiz:", url_path="swap_set"),
    st.Page("views/p7_strategy.py", title="Strategy & Monitoring Plan", icon=":material/monitoring:", url_path="strategy"),
]
nav = st.navigation(pages)
st.sidebar.caption("Home Credit 2024 data · 1.53M booked loans · decisions Jan 2019 to Oct 2020 · headline numbers on the out-of-time test, Jan to Mar 2020")
require_cache()
nav.run()
