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


# ---------------------------------------------------------------------------------------------------------------------
# Cut-off and strategy
# ---------------------------------------------------------------------------------------------------------------------
def loss_curve(curves: dict, rule_points: dict | None = None, default_cut: float = 0.5, height: int = 470, title: str | None = None,
               subtitle: str | None = None, headline: str | None = None) -> go.Figure:
    """Total decision cost (credit losses + forgone margin) vs a single PD cut-off, one line per model.

    curves: {model_name: DataFrame from strategy.curve_by_threshold}; rule_points: {model_name: total cost of the product-level cost rule}.
    """
    fig = go.Figure()
    best = {}
    for name, c in curves.items():
        col = MODEL_COLORS.get(name, BLUE)
        fig.add_trace(go.Scatter(
            x=c.threshold, y=c.total_cost / 1e6, mode="lines", name=name, line=dict(color=col, width=2),
            customdata=np.c_[c.approval_rate, c.bad_rate_approved, c.credit_loss / 1e6, c.forgone_margin / 1e6],
            hovertemplate="cut-off PD %{x:.1%}<br>total cost %{y:.1f}M CU<br>approval %{customdata[0]:.1%} · bad rate %{customdata[1]:.2%}"
                          "<br>credit loss %{customdata[2]:.1f}M · forgone margin %{customdata[3]:.1f}M<extra>" + name + "</extra>"))
        i = int(np.nanargmin(c.total_cost.to_numpy()))
        best[name] = c.iloc[i]
        d = c.iloc[(c.threshold - default_cut).abs().argmin()]
        fig.add_trace(_marker(d.threshold, d.total_cost / 1e6, f"{name}: default 0.5 cut-off", col, symbol="x", size=11,
                              hover=f"default 0.5 cut-off<br>total cost {d.total_cost / 1e6:.1f}M CU<extra>{name}</extra>"))
        fig.add_trace(_marker(c.threshold.iloc[i], c.total_cost.iloc[i] / 1e6, f"{name}: best single cut-off", col, size=11,
                              hover=f"best single cut-off {c.threshold.iloc[i]:.1%}<br>total cost {c.total_cost.iloc[i] / 1e6:.1f}M CU<extra>{name}</extra>"))
    if rule_points:
        for name, cost in rule_points.items():
            fig.add_hline(y=cost / 1e6, line=dict(color=MODEL_COLORS.get(name, BLUE), width=1, dash="dot"), opacity=0.7)
        name0 = list(rule_points)[0]
        fig.add_annotation(x=0.49, xref="x", y=rule_points[name0] / 1e6, text="cost-based rule with product break-evens", showarrow=False,
                           yshift=-11, xanchor="right", font=dict(size=11, color=INK_2))
    head = headline if headline in curves else list(curves)[-1]
    c0 = curves[head]
    d0 = c0.iloc[(c0.threshold - default_cut).abs().argmin()]
    b0 = best[head]
    fig.add_annotation(x=d0.threshold, y=d0.total_cost / 1e6, text="0.5 cut-off<br>(approves almost all)", showarrow=True, arrowhead=0, ax=-60, ay=-40,
                       font=dict(size=11, color=INK_2), arrowcolor=AXIS)
    fig.add_annotation(x=b0.threshold, y=b0.total_cost / 1e6, text=f"cheapest single<br>cut-off: PD {b0.threshold:.1%}", showarrow=True, arrowhead=0, ax=45, ay=55,
                       font=dict(size=11, color=INK_2), arrowcolor=AXIS)
    if rule_points and head in rule_points:
        saving, what = 1 - rule_points[head] / d0.total_cost, "The cost-based rule"
    else:
        saving, what = 1 - b0.total_cost / d0.total_cost, "The cheapest single cut-off"
    y_top = 1.7 * max(float(c.iloc[(c.threshold - default_cut).abs().argmin()].total_cost) for c in curves.values()) / 1e6
    base_layout(fig, title or f"{what} cuts the cost of wrong decisions by {saving:.0%} versus the default 0.5 cut-off",
                subtitle or "Credit losses on approved bads + margin forgone on declined goods (million CU) by PD cut-off, out-of-time test Jan to Mar 2020",
                height=height)
    fig.update_xaxes(title="PD cut-off (approve if predicted PD is below)", tickformat=".0%", range=[0, 0.505])
    fig.update_yaxes(title="Total cost of decisions (M CU)", range=[0, y_top])
    return fig


def tradeoff_curve(curves: dict, points: list[dict] | None = None, x_range=(0.80, 1.0), height: int = 460, title: str | None = None) -> go.Figure:
    """Approved-book bad rate vs approval rate, one line per model (lower-right is better)."""
    fig = go.Figure()
    for name, c in curves.items():
        c = c[(c.approval_rate >= x_range[0] - 0.01)]
        fig.add_trace(go.Scatter(x=c.approval_rate, y=c.bad_rate_approved, mode="lines", name=name, line=dict(color=MODEL_COLORS.get(name, BLUE), width=2),
                                 hovertemplate="approval %{x:.1%}<br>bad rate %{y:.2%}<extra>" + name + "</extra>"))
    for p in points or []:
        fig.add_trace(_marker(p["x"], p["y"], p["label"], p.get("color", INK), text=p.get("text"), symbol=p.get("symbol", "circle"), size=11,
                              textpos=p.get("textpos", "top left"), hover=f"{p['label']}<br>approval %{{x:.1%}} · bad rate %{{y:.2%}}<extra></extra>"))
    base_layout(fig, title or "At any approval rate the challenger's approved book has a lower bad rate",
                "Bad rate of the approved book (%) vs share of applications approved, out-of-time test Jan to Mar 2020", height=height)
    fig.update_xaxes(title="Approval rate (share of booked-population applications)", tickformat=".0%", range=list(x_range))
    fig.update_yaxes(title="Bad rate of approved loans", tickformat=".1%")
    return fig


def swap_bars(swap: pd.DataFrame, height: int = 380, title: str | None = None) -> go.Figure:
    """Bad rate (with 95% CI) of each swap-set cell; bar label shows the number of applications."""
    d = swap[swap.applications > 0].copy()
    fig = go.Figure(go.Bar(
        x=d.cell.str.replace(" (", "<br>(", regex=False), y=d.bad_rate, marker_color=[SWAP_COLORS.get(c, NEUTRAL) for c in d.cell], width=0.5,
        error_y=dict(type="data", symmetric=False, array=d.bad_rate_ci_high - d.bad_rate, arrayminus=d.bad_rate - d.bad_rate_ci_low, color=INK_2, thickness=1, width=4),
        text=[f"{n:,.0f} apps" for n in d.applications], textposition="outside", textfont=dict(color=INK_2, size=11),
        customdata=np.c_[d.applications, d.share, d.bads, d.loan_amount / 1e6],
        hovertemplate="%{x}<br>bad rate %{y:.2%}<br>%{customdata[0]:,.0f} applications (%{customdata[1]:.1%})<br>%{customdata[2]:,.0f} bads · %{customdata[3]:.1f}M CU<extra></extra>"))
    base_layout(fig, title or "Swap-outs are far riskier than swap-ins", "Bad rate by swap-set cell (%), 95% intervals; labels = applications", height=height, legend=False)
    fig.update_yaxes(tickformat=".0%", rangemode="tozero", title="Bad rate")
    fig.update_xaxes(tickangle=0)
    return fig


def headroom_chart(h: pd.DataFrame, book_bad_rate: float, tail_bad_rate: float, height: int = 380) -> go.Figure:
    """New approvals affordable per declined tail loan, as a function of the (unknown) bad rate of new approvals."""
    d = h[np.isfinite(h.new_approvals_per_decline)].copy()
    fig = go.Figure(go.Scatter(x=d.swap_in_bad_rate, y=d.new_approvals_per_decline, mode="lines", line=dict(color=BLUE, width=2), name="Exchange rate",
                               hovertemplate="new approvals' bad rate %{x:.1%}<br>%{y:.1f} new approvals per declined loan<extra></extra>"))
    fig.add_hline(y=1, line=dict(color=AXIS, width=1))
    fig.add_annotation(x=tail_bad_rate, y=1, text=f"break-even: new approvals as risky as<br>the declined tail ({tail_bad_rate:.1%})", showarrow=True, arrowhead=0, ax=-70, ay=-45,
                       font=dict(size=11, color=INK_2), arrowcolor=AXIS)
    base_layout(fig, "Declining the riskiest tail buys room for more approvals only if new approvals are safer than that tail",
                f"New approvals per declined loan at an unchanged book bad rate ({book_bad_rate:.2%}), by the bad rate of the new approvals", height=height, legend=False)
    fig.update_xaxes(title="Bad rate of newly approved applicants (unknown: measure with a test)", tickformat=".0%")
    fig.update_yaxes(title="New approvals per declined loan", range=[0, min(12, float(d.new_approvals_per_decline.max()) * 1.05)])
    return fig


def tier_bars(tiers: pd.DataFrame, height: int = 360) -> go.Figure:
    """Applications per month and bad rate by tier (two panels, one axis each)."""
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Applications per month", "Bad rate before review"), horizontal_spacing=0.14)
    colors = [TIER_COLORS[t] for t in tiers.tier]
    fig.add_trace(go.Bar(x=tiers.tier, y=tiers.per_month, marker_color=colors, width=0.5, text=[f"{v:,.0f}" for v in tiers.per_month], textposition="outside",
                         textfont=dict(color=INK_2), hovertemplate="%{x}<br>%{y:,.0f} per month<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Bar(x=tiers.tier, y=tiers.bad_rate, marker_color=colors, width=0.5, text=[f"{v:.1%}" for v in tiers.bad_rate], textposition="outside",
                         textfont=dict(color=INK_2), hovertemplate="%{x}<br>bad rate %{y:.2%}<extra></extra>"), row=1, col=2)
    base_layout(fig, "Review is reserved for the grey zone", "Volume per month and bad rate by tier, out-of-time test window", height=height, legend=False)
    fig.update_xaxes(tickangle=0)
    fig.update_yaxes(rangemode="tozero")
    fig.update_yaxes(tickformat=".0%", row=1, col=2)
    fig.update_yaxes(tickformat=",.0f", row=1, col=1)
    for a in fig.layout.annotations[:2]:
        a.update(font=dict(size=12, color=INK_2))
    return fig


def fairness_bars(g: pd.DataFrame, group_label: str, height: int = 360, title: str | None = None) -> go.Figure:
    """Approval-rate ratio by group vs the four-fifths line (one panel) and approved-book bad rate (second panel)."""
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Approval-rate ratio vs most-approved group", "Bad rate of approved loans"), horizontal_spacing=0.14)
    fig.add_trace(go.Bar(x=g.group, y=g.approval_rate_ratio, marker_color=BLUE, width=0.5, text=[f"{v:.2f}" for v in g.approval_rate_ratio], textposition="outside",
                         textfont=dict(color=INK_2), customdata=np.c_[g.approval_rate, g.applications],
                         hovertemplate="%{x}<br>ratio %{y:.3f}<br>approval %{customdata[0]:.1%} · %{customdata[1]:,.0f} apps<extra></extra>"), row=1, col=1)
    fig.add_hline(y=0.8, line=dict(color=STATUS["critical"], width=1), row=1, col=1)
    fig.add_annotation(x=0, xref="x domain", y=0.8, yref="y", text="four-fifths line (0.80)", showarrow=False, yshift=9, xanchor="left", font=dict(size=10.5, color=INK_2), row=1, col=1)
    fig.add_trace(go.Bar(x=g.group, y=g.bad_rate_approved, marker_color=NEUTRAL, width=0.5,
                         error_y=dict(type="data", symmetric=False, array=g.bad_rate_approved_ci_high - g.bad_rate_approved,
                                      arrayminus=g.bad_rate_approved - g.bad_rate_approved_ci_low, color=INK_2, thickness=1, width=4),
                         hovertemplate="%{x}<br>bad rate %{y:.2%}<extra></extra>"), row=1, col=2)
    base_layout(fig, title or f"Approval rates by {group_label} stay above the four-fifths screen",
                f"Recommended policy on the out-of-time test window, by {group_label}", height=height, legend=False)
    fig.update_yaxes(range=[0, 1.12], row=1, col=1)
    fig.update_yaxes(tickformat=".0%", rangemode="tozero", row=1, col=2)
    for a in fig.layout.annotations[:2]:
        a.update(font=dict(size=12, color=INK_2))
    return fig


def monitor_lines(mon: pd.DataFrame, value: str, title: str, subtitle: str, fmt: str = ".2f", bands: tuple | None = None, height: int = 360,
                  models: list | None = None) -> go.Figure:
    """One monitoring metric by decision month and model, with optional threshold lines (e.g. PSI 0.10 / 0.25)."""
    fig = go.Figure()
    for name in models or mon.model.unique():
        g = mon[mon.model == name]
        fig.add_trace(go.Scatter(x=[_month_label(m) for m in g.decision_month], y=g[value], mode="lines+markers", name=name,
                                 line=dict(color=MODEL_COLORS.get(name, BLUE), width=2), marker=dict(size=7, line=dict(color=SURFACE, width=2)),
                                 hovertemplate="%{x}<br>" + value + " %{y:" + fmt + "}<extra>" + name + "</extra>"))
    if bands:
        for yv, label, color in bands:
            fig.add_hline(y=yv, line=dict(color=color, width=1))
            fig.add_annotation(x=1, xref="x domain", y=yv, text=label, showarrow=False, yshift=9, xanchor="right", font=dict(size=10.5, color=INK_2))
    fig.add_vrect(x0="2020-04", x1="2020-10", fillcolor="#efeee9", opacity=0.6, line_width=0, layer="below")
    base_layout(fig, title, subtitle, height=height)
    fig.update_xaxes(tickangle=-45, tickfont=dict(size=10.5))
    return fig


def breakeven_sensitivity(rows: pd.DataFrame, height: int = 380) -> go.Figure:
    """Break-even PD per product under low / base / high assumptions (dumbbell)."""
    fig = go.Figure()
    for i, r in rows.iterrows():
        fig.add_trace(go.Scatter(x=[r.low, r.high], y=[r.label, r.label], mode="lines", line=dict(color=AXIS, width=6), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=rows.low, y=rows.label, mode="markers", name="Pessimistic assumption", marker=dict(color=ORANGE, size=10, line=dict(color=SURFACE, width=2)),
                             hovertemplate="%{y}<br>break-even %{x:.1%}<extra>low</extra>"))
    fig.add_trace(go.Scatter(x=rows.high, y=rows.label, mode="markers", name="Optimistic assumption", marker=dict(color=AQUA, size=10, line=dict(color=SURFACE, width=2)),
                             hovertemplate="%{y}<br>break-even %{x:.1%}<extra>high</extra>"))
    fig.add_trace(go.Scatter(x=rows.base, y=rows.label, mode="markers", name="Base case", marker=dict(color=INK, size=9, symbol="line-ns-open", line=dict(width=2)),
                             hovertemplate="%{y}<br>base %{x:.1%}<extra></extra>"))
    base_layout(fig, "The break-even PD depends most on the margin assumption, so it is set per product",
                "Break-even PD (%) per product when one assumption moves to the end of its range (others at base case)", height=height)
    fig.update_xaxes(tickformat=".0%", title="Break-even PD (decline above this)", rangemode="tozero")
    fig.update_layout(margin=dict(l=260))
    return fig


# ---------------------------------------------------------------------------------------------------------------------
# Portfolio and explanations
# ---------------------------------------------------------------------------------------------------------------------
def segment_bad_rate(t: pd.DataFrame, segment: str, overall: float | None = None, height: int = 400) -> go.Figure:
    """Bad rate with 95% CI by segment value (left) and share of loans (right). t: value, loans, bads, bad_rate, ci_low, ci_high, share."""
    fig = make_subplots(rows=1, cols=2, column_widths=[0.62, 0.38], subplot_titles=("Bad rate (95% interval)", "Share of loans"), horizontal_spacing=0.12)
    fig.add_trace(go.Bar(x=t.value, y=t.bad_rate, marker_color=BLUE, width=0.55,
                         error_y=dict(type="data", symmetric=False, array=t.ci_high - t.bad_rate, arrayminus=t.bad_rate - t.ci_low, color=INK_2, thickness=1, width=4),
                         customdata=np.c_[t.loans, t.bads], hovertemplate="%{x}<br>bad rate %{y:.2%}<br>%{customdata[1]:,.0f} bads of %{customdata[0]:,.0f}<extra></extra>"), row=1, col=1)
    if overall is not None:
        fig.add_hline(y=overall, line=dict(color=AXIS, width=1), row=1, col=1)
        fig.add_annotation(x=0, xref="x domain", y=overall, yref="y", text=f"overall {overall:.2%}", showarrow=False, yshift=9, xanchor="left", font=dict(size=10.5, color=INK_2), row=1, col=1)
    fig.add_trace(go.Bar(x=t.value, y=t.share, marker_color=NEUTRAL, width=0.55, hovertemplate="%{x}<br>%{y:.1%} of loans<extra></extra>"), row=1, col=2)
    hi, lo = t.loc[t.bad_rate.idxmax()], t.loc[t.bad_rate.idxmin()]
    base_layout(fig, f"{segment}: bad rate ranges from {lo.bad_rate:.1%} ({lo.value}) to {hi.bad_rate:.1%} ({hi.value})",
                "Share of booked loans that defaulted (%) and share of loans by segment, for the selected period and products", height=height, legend=False)
    fig.update_yaxes(tickformat=".1%", rangemode="tozero", row=1, col=1)
    fig.update_yaxes(tickformat=".0%", rangemode="tozero", row=1, col=2)
    for a in fig.layout.annotations[:2]:
        a.update(font=dict(size=12, color=INK_2))
    return fig


def segment_trend(t: pd.DataFrame, segment: str, height: int = 380) -> go.Figure:
    """Monthly bad rate per segment value (t: decision_month, value, bad_rate, loans); categorical colours in fixed order."""
    order = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED]
    fig = go.Figure()
    for i, (val, g) in enumerate(t.groupby("value", sort=False)):
        fig.add_trace(go.Scatter(x=[_month_label(m) for m in g.decision_month], y=g.bad_rate, mode="lines", name=str(val), line=dict(color=order[i % 8], width=2),
                                 customdata=g.loans, hovertemplate="%{x}<br>" + str(val) + ": %{y:.2%} (%{customdata:,.0f} loans)<extra></extra>"))
    base_layout(fig, f"{segment}: bad rate by month", "Bad rate by decision month for the largest segments (%)", height=height)
    fig.update_layout(margin=dict(b=80))
    fig.update_yaxes(tickformat=".1%", rangemode="tozero")
    fig.update_xaxes(tickangle=-45, tickfont=dict(size=10.5))
    return fig


def explanation_bars(contrib: pd.Series, labels: dict, values: dict, top: int = 10, height: int = 440, title: str | None = None) -> go.Figure:
    """Largest SHAP contributions (log-odds) for one applicant: orange pushes risk up, blue pushes it down."""
    c = contrib.reindex(contrib.abs().sort_values(ascending=False).index).head(top).iloc[::-1]
    ylabels = [f"{labels.get(f, f)} = {values.get(f, '')}" for f in c.index]
    fig = go.Figure(go.Bar(x=c.values, y=ylabels, orientation="h", marker_color=[ORANGE if v > 0 else BLUE for v in c.values], width=0.6,
                           hovertemplate="%{y}<br>impact on log-odds %{x:+.3f}<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=AXIS, width=1))
    base_layout(fig, title or "What pushed this applicant's risk up (orange) or down (blue)",
                f"Contribution of each input to the log-odds of default vs the average applicant (SHAP), top {top}", height=height, legend=False)
    fig.update_layout(margin=dict(l=380))
    fig.update_xaxes(title="Impact on log-odds of default", zeroline=False)
    return fig


def setup_notebook_renderer() -> str:
    """Interactive charts plus a static PNG copy (so GitHub can show them) when kaleido can find Chrome; interactive only otherwise."""
    import plotly.io as pio

    try:
        go.Figure().to_image(format="png", width=10, height=10)
        pio.renderers.default = "notebook+png"
    except Exception:  # noqa: BLE001
        pio.renderers.default = "notebook"
    return pio.renderers.default
