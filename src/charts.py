"""Plotly figures shared by the Streamlit dashboard and the HTML report, so both show identical charts.

Style rules (internal-tool look): light surface, hairline solid grid, 2px lines, thin bars, one fixed colour per entity,
the title states the takeaway and the subtitle states what is plotted and its unit. No dual axes anywhere.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------------------------------------------------------------------
# Palette (validated reference palette; colour follows the entity, never its rank)
# ---------------------------------------------------------------------------------------------------------------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"
NEUTRAL = "#b5b3ab"
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
BLUE_RAMP = {250: "#86b6ef", 350: "#5598e7", 450: "#2a78d6", 550: "#1c5cab", 650: "#104281"}

MODEL_COLORS = {"Challenger (LightGBM)": BLUE, "Champion (scorecard)": ORANGE}
MODEL_SHORT = {"challenger": "Challenger (LightGBM)", "champion": "Champion (scorecard)"}
TIER_COLORS = {"Auto-approve": BLUE_RAMP[250], "Manual review": BLUE_RAMP[450], "Decline": BLUE_RAMP[650]}
SWAP_COLORS = {
    "Approved by both": NEUTRAL,
    "Swap-in (declined -> approved)": BLUE,
    "Swap-out (approved -> declined)": ORANGE,
    "Declined by both": "#6f6d66",
}
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


def base_layout(fig: go.Figure, title: str, subtitle: str = "", height: int = 420, legend: bool = True) -> go.Figure:
    """Apply the house style. `title` = one-sentence takeaway; `subtitle` = what is plotted and the unit."""
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b>",
            subtitle=dict(text=subtitle, font=dict(size=12.5, color=INK_2)),
            x=0,
            xanchor="left",
            y=0.97,
            yanchor="top",
            font=dict(size=15.5, color=INK),
        ),
        font=dict(family=FONT, size=12.5, color=INK_2),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        height=height,
        margin=dict(l=64, r=28, t=86 if subtitle else 64, b=56),
        hoverlabel=dict(bgcolor="white", bordercolor=AXIS, font=dict(family=FONT, size=12, color=INK)),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1.0, bgcolor="rgba(0,0,0,0)", font=dict(size=12, color=INK_2), title_text=""),
        hovermode="closest",
        bargap=0.35,
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, linewidth=1, ticks="outside", tickcolor=AXIS, tickfont=dict(color=MUTED), title_font=dict(color=INK_2), zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=GRID, gridwidth=1, linecolor=AXIS, tickfont=dict(color=MUTED), title_font=dict(color=INK_2), zeroline=False)
    return fig


def _line(x, y, name, color, hover, dash=None, width=2, showlegend=True, customdata=None):
    return go.Scatter(
        x=x, y=y, name=name, mode="lines", line=dict(color=color, width=width, dash=dash, shape="linear"),
        hovertemplate=hover, customdata=customdata, showlegend=showlegend,
    )


def _marker(x, y, name, color, text=None, symbol="circle", size=10, hover=None, textpos="top center", showlegend=False):
    return go.Scatter(
        x=[x], y=[y], name=name, mode="markers+text" if text else "markers",
        marker=dict(color=color, size=size, symbol=symbol, line=dict(color=SURFACE, width=2)),
        text=[text] if text else None, textposition=textpos, textfont=dict(color=INK, size=12),
        hovertemplate=hover or f"{name}<extra></extra>", showlegend=showlegend,
    )


def fmt_money(x: float) -> str:
    """Compact currency-unit label: 1.2M CU, 850K CU."""
    a = abs(x)
    if a >= 1e9:
        return f"{x / 1e9:.2f}B CU"
    if a >= 1e6:
        return f"{x / 1e6:.1f}M CU"
    if a >= 1e3:
        return f"{x / 1e3:.0f}K CU"
    return f"{x:.0f} CU"


def pct(x: float, digits: int = 1) -> str:
    return f"{100 * x:.{digits}f}%"


# ---------------------------------------------------------------------------------------------------------------------
# Data audit
# ---------------------------------------------------------------------------------------------------------------------
SPLIT_LABELS = {"train": "Train", "valid": "Valid", "test": "OOT test", "monitor": "Monitoring (COVID period)"}


def _month_label(m) -> str:
    m = int(m)
    return f"{m // 100}-{m % 100:02d}"


def monthly_volume_bad_rate(monthly: pd.DataFrame, split_ranges: dict | None = None, title: str | None = None) -> go.Figure:
    """Two stacked panels sharing the month axis: loans per month (bars) and bad rate with 95% CI (line + band)."""
    x = [_month_label(m) for m in monthly["decision_month"]]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.11, row_heights=[0.42, 0.58],
                        subplot_titles=("Loans booked per month", "Bad rate per month (95% interval)"))
    fig.add_trace(go.Bar(x=x, y=monthly["n"], marker_color=BLUE, marker_line_width=0, name="Loans",
                         hovertemplate="%{x}<br>%{y:,.0f} loans<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x + x[::-1], y=list(monthly["bad_rate_ci_high"]) + list(monthly["bad_rate_ci_low"][::-1]), fill="toself",
                             fillcolor="rgba(42,120,214,0.12)", line=dict(width=0), hoverinfo="skip", showlegend=False), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=monthly["bad_rate"], mode="lines+markers", line=dict(color=BLUE, width=2), marker=dict(size=7, color=BLUE, line=dict(color=SURFACE, width=2)),
                             name="Bad rate", customdata=np.c_[monthly["n"], monthly["bads"]],
                             hovertemplate="%{x}<br>bad rate %{y:.2%}<br>%{customdata[1]:,.0f} bads of %{customdata[0]:,.0f}<extra></extra>"), row=2, col=1)
    if split_ranges:
        for name, (a, b) in split_ranges.items():
            if name == "train":
                continue
            fig.add_vrect(x0=_month_label(a), x1=_month_label(b), fillcolor="#efeee9", opacity=0.6, line_width=0, layer="below")
            fig.add_annotation(x=_month_label(a), y=1.06, yref="y domain", text=SPLIT_LABELS.get(name, name), showarrow=False, xanchor="left",
                               font=dict(size=10.5, color=INK_2), row=1, col=1)
    base_layout(fig, title or "Bad rate rose through 2019, then volume and bad rate both fell from April 2020",
                "Loans per decision month and share that defaulted (%); shaded = validation, test and monitoring windows", height=540, legend=False)
    fig.update_yaxes(tickformat=",.0f", row=1, col=1)
    fig.update_yaxes(tickformat=".1%", rangemode="tozero", row=2, col=1)
    fig.update_xaxes(tickangle=-45, tickfont=dict(size=10.5))
    for a in fig.layout.annotations[:2]:
        a.update(font=dict(size=12, color=INK_2), x=0, xanchor="left")
    return fig


PROCESS_DATES = {"responsedate_1012D", "responsedate_4527233D", "responsedate_4917613D", "assignmentdate_238D", "assignmentdate_4527235D", "assignmentdate_4955616D"}


def point_in_time_chart(pit: pd.DataFrame, min_share: float = 0.01, min_n: int = 50_000, top: int = 14) -> go.Figure:
    """Bad rate of loans whose dated 'last event' falls after vs on/before the decision (event fields with enough volume).

    Tax-authority response/assignment dates are excluded here: they are process timestamps (always decision + 14 days),
    handled separately in the audit, not client events.
    """
    d = pit[(pit.share_after_decision >= min_share) & pit.bad_rate_if_on_or_before.notna() & (pit.n_non_null >= min_n) & ~pit.field.isin(PROCESS_DATES)].copy()
    d = d.sort_values("share_after_decision", ascending=True).tail(top)
    d["label"] = d["field"] + "  (" + (100 * d["share_after_decision"]).round(1).astype(str) + "% after)"
    fig = go.Figure()
    for i, r in enumerate(d.itertuples()):
        fig.add_trace(go.Scatter(x=[r.bad_rate_if_on_or_before, r.bad_rate_if_after], y=[r.label, r.label], mode="lines",
                                 line=dict(color=AXIS, width=2), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=d.bad_rate_if_on_or_before, y=d.label, mode="markers", name="Event on or before the decision",
                             marker=dict(color=BLUE, size=10, line=dict(color=SURFACE, width=2)), hovertemplate="%{y}<br>bad rate %{x:.2%}<extra>on/before</extra>"))
    fig.add_trace(go.Scatter(x=d.bad_rate_if_after, y=d.label, mode="markers", name="Event after the decision (not knowable at decision time)",
                             marker=dict(color=ORANGE, size=10, line=dict(color=SURFACE, width=2)), hovertemplate="%{y}<br>bad rate %{x:.2%}<extra>after</extra>"))
    base_layout(fig, "Where the client's 'last event' happened after the decision, the loan defaulted more often",
                "Bad rate (%) by whether the field's date is after the decision date; brackets = share of dates that fall after it", height=560)
    fig.update_xaxes(tickformat=".0%", title="Bad rate", showgrid=True, gridcolor=GRID, rangemode="tozero")
    fig.update_yaxes(showgrid=False, tickfont=dict(size=11, color=INK_2))
    fig.update_layout(margin=dict(l=300, b=90), legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="left", x=0))
    return fig


def snapshot_offset_chart(off: pd.DataFrame) -> go.Figure:
    """Match rate of the provided 30-day application count vs recounts ending at different reference dates."""
    d = off[off.test.str.startswith("applications30d")].copy()
    d["offset"] = d.test.str.extract(r"\+ (\d+)d").astype(int)[0]
    d = d.sort_values("offset")
    d["label"] = np.where(d.offset == 0, "Decision date<br>(point in time)", "Decision date<br>+ " + d.offset.astype(str) + " days")
    colors = [BLUE if o == 0 else NEUTRAL for o in d.offset]
    fig = go.Figure(go.Bar(x=d.label, y=d.match_rate, marker_color=colors, marker_line_width=0, width=0.45,
                           text=[f"{v:.1%}" for v in d.match_rate], textposition="outside", textfont=dict(color=INK),
                           hovertemplate="%{x}<br>match rate %{y:.2%}<extra></extra>"))
    base_layout(fig, "The provided '30-day applications' count includes days after the decision",
                "Exact match between the provided count and our recount over the 30 days ending on each date (% of loans)", height=400, legend=False)
    fig.update_xaxes(tickangle=0)
    fig.update_yaxes(tickformat=".0%", range=[0.85, 1.0], title="Exact match rate")
    return fig
