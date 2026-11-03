"""Shared helpers for every dashboard page: cached data loading, page header, KPI tiles, 'How to read this'."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config  # noqa: E402
from src.economics import Economics, Review  # noqa: E402

CFG = load_config()
CACHE = Path(CFG["processed_dir"]) / "dashboard"
METRICS = Path(CFG["reports_dir"]) / "metrics.json"


def cache_ready() -> bool:
    return CACHE.exists() and METRICS.exists()


def require_cache() -> None:
    if not cache_ready():
        st.error(
            "The dashboard cache is missing. Run the pipeline first:\n\n"
            "```bash\nmake all\n```\n\n(it reads the raw data from `config.yaml` and writes `data/processed/dashboard/`)."
        )
        st.stop()


@st.cache_data(show_spinner=False)
def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(CACHE / f"{name}.parquet")


@st.cache_data(show_spinner=False)
def metrics() -> dict:
    return json.loads(METRICS.read_text())


def base_economics() -> Economics:
    return Economics.from_config(CFG)


def base_review() -> Review:
    return Review.from_config(CFG)


def page_header(title: str, question: str) -> None:
    """Title plus the one sentence this page answers."""
    st.title(title)
    st.markdown(f"<div class='question'>{question}</div>", unsafe_allow_html=True)


def how_to_read(markdown_text: str) -> None:
    """Plain-language explanation at the bottom of each page, folded by default."""
    st.divider()
    with st.expander("How to read this", expanded=False, icon=":material/help:"):
        st.markdown(markdown_text)


def kpi_row(items: list[tuple[str, str, str | None]]) -> None:
    """items: (label, value, help) rendered as metric tiles in one row."""
    cols = st.columns(len(items))
    for col, (label, value, help_text) in zip(cols, items):
        col.metric(label, value, help=help_text)


def note(text: str) -> None:
    st.markdown(f"<div class='note'>{text}</div>", unsafe_allow_html=True)


CSS = """
<style>
  .block-container {padding-top: 2.2rem; max-width: 1280px;}
  h1 {font-size: 1.75rem !important; font-weight: 650 !important; letter-spacing: -0.01em;}
  h2 {font-size: 1.2rem !important; font-weight: 600 !important; margin-top: 1.2rem;}
  h3 {font-size: 1.02rem !important; font-weight: 600 !important;}
  .question {font-size: 1.02rem; color: #52514e; border-left: 3px solid #2a78d6; padding: 2px 0 2px 12px; margin: -0.4rem 0 1.2rem 0;}
  .note {font-size: 0.86rem; color: #52514e; background: #f3f2ee; border-radius: 6px; padding: 8px 12px; margin: 4px 0 12px 0;}
  [data-testid="stMetricValue"] {font-size: 1.45rem; font-weight: 600;}
  [data-testid="stMetricLabel"] p {font-size: 0.82rem; color: #52514e;}
  div[data-testid="stExpander"] details summary p {font-weight: 600;}
  table {font-variant-numeric: tabular-nums;}
</style>
"""


def apply_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


HEADERS = {
    "cell": "Cell", "applications": "Applications", "share": "Share", "bads": "Defaults", "bad_rate": "Bad rate",
    "bad_rate_ci_low": "95% CI low", "bad_rate_ci_high": "95% CI high", "loan_amount": "Loan amount (CU)",
    "credit_loss_if_approved": "Credit loss if approved (CU)", "net_value_if_approved": "Net value if approved (CU)",
    "model": "Model", "policy": "Policy", "approval_rate": "Approval rate", "bad_rate_approved": "Bad rate of approved",
    "capture_rate": "Defaults declined (capture)", "false_positive_rate": "Good customers declined", "credit_loss": "Credit loss (CU)",
    "forgone_margin": "Margin forgone (CU)", "net_profit": "Net profit (CU)", "tier": "Tier", "per_month": "Per month",
    "median_amount": "Median loan (CU)", "review_cost": "Review cost (CU)", "group": "Group", "approval_rate_ratio": "Approval-rate ratio",
    "observed_bad_rate": "Observed bad rate", "mean_pd": "Mean predicted PD", "calibration_ratio": "Calibration ratio",
    "reviews": "Reviews", "pd_from": "PD from", "pd_to": "PD to", "smallest_loan": "Smallest loan (CU)",
    "share_cash": "Share cash loans", "share_new_to_lender": "Share new to lender", "mean_pd_champion": "Mean PD, champion",
    "mean_pd_challenger": "Mean PD, challenger", "feature": "Input", "first_month": "First month flagged", "months_flagged": "Months flagged", "max_csi": "Max CSI",
}


def styled(df, formats: dict):
    """Rename columns to readable headers and apply per-column number formats (keys use the original column names)."""
    fmt = {HEADERS.get(k, k): v for k, v in formats.items() if k in df.columns}
    return df.rename(columns=HEADERS).style.format(fmt)
