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
