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
SPLIT_LABELS = {"train": "Train", "valid": "Valid", "test": "OOT test", "monitor": "Monitoring (Apr-Oct 2020)"}


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
    base_layout(fig, title or _monthly_title(monthly),
                "Loans per decision month and share that defaulted (%); shaded = validation, test and monitoring windows" + _partial_month_note(monthly),
                height=540, legend=False)
    fig.update_yaxes(tickformat=",.0f", row=1, col=1)
    fig.update_yaxes(tickformat=".1%", rangemode="tozero", row=2, col=1)
    fig.update_xaxes(tickangle=-45, tickfont=dict(size=10.5))
    for a in fig.layout.annotations[:2]:
        a.update(font=dict(size=12, color=INK_2), x=0, xanchor="left")
    return fig


def _partial_month_note(monthly: pd.DataFrame) -> str:
    """'; 2020-10 covers 1 to 5 October only' when the last month in the data is incomplete."""
    if "last_day" not in monthly or monthly.empty:
        return ""
    last = monthly.iloc[-1]
    d = pd.Timestamp(last["last_day"])
    if d.day < d.days_in_month:
        return f"; {_month_label(last['decision_month'])} covers 1 to {d.day} {d.strftime('%B')} only"
    return ""


def _monthly_title(monthly: pd.DataFrame) -> str:
    """Takeaway for the monthly chart, computed from the data (peak bad rate, the April 2020 break, recovery of volume)."""
    try:
        t = monthly.set_index("decision_month")
        peak = t.bad_rate.idxmax()
        pre, post = t.loc[202001:202003], t.loc[202004:]
        ratio = post.bads.sum() / post.n.sum() / (pre.bads.sum() / pre.n.sum())
        fall = "halved" if 0.4 <= ratio <= 0.6 else f"fell to {post.bads.sum() / post.n.sum():.1%}"
        drop = 1 - t.loc[202004, "n"] / t.loc[202003, "n"]
        back = [m for m in post.index if m > 202004 and t.loc[m, "n"] >= t.loc[202003, "n"]]
        vol = f"volume fell {drop:.0%} in April" + (f" and was back to March's level by {pd.Timestamp(year=back[0] // 100, month=back[0] % 100, day=1).strftime('%B')}" if back else "")
        return f"Bad rate peaked at {t.loc[peak, 'bad_rate']:.1%} ({_month_label(peak)}) and {fall} from April 2020; {vol}"
    except (KeyError, ValueError, ZeroDivisionError):
        return "Loans and bad rate by decision month"


PROCESS_DATES = {"responsedate_1012D", "responsedate_4527233D", "responsedate_4917613D", "assignmentdate_238D", "assignmentdate_4527235D", "assignmentdate_4955616D"}


FIELD_LABELS = {
    "lastactivateddate_801D": "Last contract activation", "maxdpdinstldate_3546855D": "Instalment with the worst lateness",
    "creationdate_885D": "Earlier application created", "dtlastpmt_581D": "Last payment", "lastapprdate_640D": "Last approval",
    "firstnonzeroinstldate_307D": "First instalment of an earlier loan", "datelastunpaid_3546854D": "Last unpaid instalment",
    "lastrejectdate_50D": "Last rejection", "lastdelinqdate_224D": "Last delinquency", "firstclxcampaign_1125D": "First marketing campaign",
    "lastapplicationdate_877D": "Last application", "dtlastpmtallstes_3545839D": "Last payment, all contracts",
    "dtlastpmtallstes_4499206D": "Last payment, all contracts", "validfrom_1069D": "Start of the active campaign",
}


def point_in_time_chart(pit: pd.DataFrame, min_share: float = 0.01, min_n: int = 50_000, top: int = 14) -> go.Figure:
    """Bad rate of loans whose dated 'last event' falls after vs on/before the decision (event fields with enough volume).

    Tax-authority response/assignment dates are excluded here: they are process timestamps (always decision + 14 days),
    handled separately in the audit, not client events.
    """
    d = pit[(pit.share_after_decision >= min_share) & pit.bad_rate_if_on_or_before.notna() & (pit.n_non_null >= min_n) & ~pit.field.isin(PROCESS_DATES)].copy()
    d = d.sort_values("share_after_decision", ascending=True).tail(top)
    d["label"] = [f"{FIELD_LABELS.get(f, f)}{' (per earlier application)' if t == 'applprev_1' else ''}  ({100 * s:.1f}% after)"
                  for f, t, s in zip(d.field, d.source_table, d.share_after_decision)]
    fig = go.Figure()
    for i, r in enumerate(d.itertuples()):
        fig.add_trace(go.Scatter(x=[r.bad_rate_if_on_or_before, r.bad_rate_if_after], y=[r.label, r.label], mode="lines",
                                 line=dict(color=AXIS, width=2), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=d.bad_rate_if_on_or_before, y=d.label, mode="markers", name="Event on or before the decision", customdata=d.field,
                             marker=dict(color=BLUE, size=10, line=dict(color=SURFACE, width=2)), hovertemplate="%{y}<br>%{customdata}<br>bad rate %{x:.2%}<extra>on/before</extra>"))
    fig.add_trace(go.Scatter(x=d.bad_rate_if_after, y=d.label, mode="markers", name="Event after the decision (not knowable at decision time)", customdata=d.field,
                             marker=dict(color=ORANGE, size=10, line=dict(color=SURFACE, width=2)), hovertemplate="%{y}<br>%{customdata}<br>bad rate %{x:.2%}<extra>after</extra>"))
    higher = int((d.bad_rate_if_after > d.bad_rate_if_on_or_before).sum())
    lead = f"For all {len(d)} dated fields" if higher == len(d) else f"For {higher} of {len(d)} dated fields"
    base_layout(fig, f"{lead}, loans whose date falls after the decision defaulted more often",
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
    colors = [BLUE if o == 0 else INK_2 for o in d.offset]
    fig = go.Figure(go.Scatter(x=d.label, y=d.match_rate, mode="markers+text", marker=dict(color=colors, size=16, line=dict(color=SURFACE, width=2)),
                               text=[f"{v:.1%}" for v in d.match_rate], textposition="top center", textfont=dict(color=INK, size=12.5),
                               hovertemplate="%{x}<br>match rate %{y:.2%}<extra></extra>"))
    base_layout(fig, "The provided '30-day applications' count includes days after the decision",
                "Exact match between the provided count and our recount over the 30 days ending on each date (% of loans; dots, axis starts at 85%)",
                height=400, legend=False)
    fig.update_xaxes(tickangle=0)
    fig.update_yaxes(tickformat=".0%", range=[0.85, 1.005], title="Exact match rate")
    return fig


# ---------------------------------------------------------------------------------------------------------------------
# Cut-off and strategy
# ---------------------------------------------------------------------------------------------------------------------
def loss_curve(curves: dict, rule_points: dict | None = None, default_cut: float = 0.5, height: int = 470, title: str | None = None,
               subtitle: str | None = None, headline: str | None = None, baseline_cost: float | None = None) -> go.Figure:
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
    far_right = "today's policy ≈ 0.5 cut-off<br>(approves almost all)" if baseline_cost is not None else "0.5 cut-off<br>(approves almost all)"
    fig.add_annotation(x=d0.threshold, y=d0.total_cost / 1e6, text=far_right, showarrow=True, arrowhead=0, ax=-70, ay=-40,
                       font=dict(size=11, color=INK_2), arrowcolor=AXIS)
    fig.add_annotation(x=b0.threshold, y=b0.total_cost / 1e6, text=f"cheapest single<br>cut-off: PD {b0.threshold:.1%}", showarrow=True, arrowhead=0, ax=45, ay=55,
                       font=dict(size=11, color=INK_2), arrowcolor=AXIS)
    base = baseline_cost if baseline_cost is not None else d0.total_cost
    against = "today's policy (approve every booked loan)" if baseline_cost is not None else "the default 0.5 cut-off"
    if rule_points and head in rule_points:
        saving, what = 1 - rule_points[head] / base, "The cost-based rule"
    else:
        saving, what = 1 - b0.total_cost / base, "The cheapest single cut-off"
    y_top = 1.7 * max(float(c.iloc[(c.threshold - default_cut).abs().argmin()].total_cost) for c in curves.values()) / 1e6
    base_layout(fig, title or f"{what} cuts the cost of wrong decisions by {saving:.0%} versus {against}",
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
    base_layout(fig, title or "From 80% to just under 100% approval, the challenger's approved book has a lower bad rate",
                "Bad rate of the approved book (%) vs share approved, out-of-time test Jan to Mar 2020. Lines = one PD cut-off for all products; "
                "the cost-based rule uses a different cut-off per product, so its dots sit just off the lines", height=height)
    fig.update_xaxes(title="Approval rate (share of booked-population applications)", tickformat=".0%", range=list(x_range))
    fig.update_yaxes(title="Bad rate of approved loans", tickformat=".1%")
    return fig


def _swap_title(d: pd.DataFrame) -> str:
    """Takeaway comparing swap-outs with swap-ins, computed from the cells (falls back to a neutral label)."""
    out = d[d.cell.str.startswith("Swap-out")]
    inn = d[d.cell.str.startswith("Swap-in")]
    if out.empty or inn.empty:
        return "Bad rate by swap-set cell"
    o, i = out.iloc[0], inn.iloc[0]
    if i.bad_rate > 0 and o.bad_rate_ci_low > i.bad_rate_ci_high:
        return f"Swap-outs default {o.bad_rate / i.bad_rate:.1f} times as often as swap-ins ({o.bad_rate:.1%} vs {i.bad_rate:.1%})"
    if o.bad_rate > i.bad_rate:
        return f"Swap-outs default a little more often than swap-ins ({o.bad_rate:.1%} vs {i.bad_rate:.1%}; intervals overlap)"
    return f"Swap-ins default as often as swap-outs or more ({i.bad_rate:.1%} vs {o.bad_rate:.1%}): this swap does not pay"


def swap_bars(swap: pd.DataFrame, height: int = 400, title: str | None = None, subtitle: str | None = None) -> go.Figure:
    """Bad rate (with 95% CI) of each swap-set cell; the category label carries the number of applications."""
    d = swap[swap.applications > 0].copy()
    xlab = [c.replace(" (", "<br>(") + f"<br>{n:,.0f} apps" for c, n in zip(d.cell, d.applications)]
    fig = go.Figure(go.Bar(
        x=xlab, y=d.bad_rate, marker_color=[SWAP_COLORS.get(c, NEUTRAL) for c in d.cell], width=0.5,
        error_y=dict(type="data", symmetric=False, array=d.bad_rate_ci_high - d.bad_rate, arrayminus=d.bad_rate - d.bad_rate_ci_low, color=INK_2, thickness=1, width=4),
        customdata=np.c_[d.applications, d.share, d.bads, d.loan_amount / 1e6],
        hovertemplate="%{x}<br>bad rate %{y:.2%}<br>%{customdata[0]:,.0f} applications (%{customdata[1]:.1%})<br>%{customdata[2]:,.0f} bads · %{customdata[3]:.1f}M CU<extra></extra>"))
    base_layout(fig, title or _swap_title(d), subtitle or "Bad rate by swap-set cell (%) with 95% intervals; axis labels give the number of applications",
                height=height, legend=False)
    fig.update_yaxes(tickformat=".0%", rangemode="tozero", title="Bad rate")
    fig.update_xaxes(tickangle=0)
    fig.update_layout(margin=dict(b=96))
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


def tier_bars(tiers: pd.DataFrame, height: int = 360, title: str | None = None) -> go.Figure:
    """Applications per month and bad rate by tier (two panels, one axis each)."""
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Applications per month", "Bad rate before review"), horizontal_spacing=0.14)
    colors = [TIER_COLORS[t] for t in tiers.tier]
    fig.add_trace(go.Bar(x=tiers.tier, y=tiers.per_month, marker_color=colors, width=0.5, text=[f"{v:,.0f}" for v in tiers.per_month], textposition="outside",
                         textfont=dict(color=INK_2), hovertemplate="%{x}<br>%{y:,.0f} per month<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Bar(x=tiers.tier, y=tiers.bad_rate, marker_color=colors, width=0.5, text=["–" if pd.isna(v) else f"{v:.1%}" for v in tiers.bad_rate],
                         textposition="outside", textfont=dict(color=INK_2), hovertemplate="%{x}<br>bad rate %{y:.2%}<extra></extra>"), row=1, col=2)
    if title is None:
        t = tiers.set_index("tier")
        if t.loc["Manual review", "applications"] == 0:
            title = "No application goes to manual review with these settings"
        else:
            title = (f"Review takes {t.loc['Manual review', 'share']:.1%} of applications, between auto-approve "
                     f"({t.loc['Auto-approve', 'bad_rate']:.1%} bad rate) and decline ({t.loc['Decline', 'bad_rate']:.1%})")
    base_layout(fig, title, "Applications per month and bad rate before review, by tier (out-of-time test window)", height=height, legend=False)
    fig.update_xaxes(tickangle=0)
    fig.update_yaxes(rangemode="tozero")
    fig.update_yaxes(tickformat=".0%", row=1, col=2)
    fig.update_yaxes(tickformat=",.0f", row=1, col=1)
    for a in fig.layout.annotations[:2]:
        a.update(font=dict(size=12, color=INK_2))
    return fig


def fairness_bars(g: pd.DataFrame, group_label: str, height: int = 360, title: str | None = None, subtitle: str | None = None) -> go.Figure:
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
                subtitle or f"Out-of-time test window (Jan to Mar 2020), by {group_label}", height=height, legend=False)
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


def _trend_title(t: pd.DataFrame, segment: str) -> str:
    """Says whether the riskiest group stays the riskiest month after month."""
    piv = t.pivot_table(index="decision_month", columns="value", values="bad_rate", observed=True)
    if piv.shape[1] < 2 or piv.empty:
        return f"{segment}: bad rate by month"
    top = piv.idxmax(axis=1)
    lead, k = top.value_counts().index[0], int(top.value_counts().iloc[0])
    if k == len(top):
        return f"{segment}: {lead} has the highest bad rate in every month"
    if k >= 0.8 * len(top):
        return f"{segment}: {lead} has the highest bad rate in {k} of {len(top)} months"
    return f"{segment}: no group has the highest bad rate in most months"


def segment_trend(t: pd.DataFrame, segment: str, height: int = 380) -> go.Figure:
    """Monthly bad rate per segment value (t: decision_month, value, bad_rate, loans); categorical colours in fixed order."""
    order = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED]
    fig = go.Figure()
    for i, (val, g) in enumerate(t.groupby("value", sort=False)):
        fig.add_trace(go.Scatter(x=[_month_label(m) for m in g.decision_month], y=g.bad_rate, mode="lines", name=str(val), line=dict(color=order[i % 8], width=2),
                                 customdata=g.loans, hovertemplate="%{x}<br>" + str(val) + ": %{y:.2%} (%{customdata:,.0f} loans)<extra></extra>"))
    base_layout(fig, _trend_title(t, segment), "Bad rate by decision month for the largest segments (%)", height=height)
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
    if title is None:
        up, down = contrib[contrib > 0], contrib[contrib < 0]
        if len(up):
            f = up.idxmax()
            title = f"{labels.get(f, f)} ({values.get(f, '')}) raised this applicant's risk the most"
        elif len(down):
            f = down.idxmin()
            title = f"{labels.get(f, f)} ({values.get(f, '')}) lowered this applicant's risk the most"
        else:
            title = "No input moved this applicant's risk"
    base_layout(fig, title,
                f"Contribution of each input to the log-odds of default vs the average applicant (SHAP; orange raises risk, blue lowers it), top {top}",
                height=height, legend=False)
    fig.update_layout(margin=dict(l=380))
    fig.update_xaxes(title="Impact on log-odds of default", zeroline=False)
    return fig


# ---------------------------------------------------------------------------------------------------------------------
# Model charts shared by the app and the report
# ---------------------------------------------------------------------------------------------------------------------
def calibration_deciles(cal: pd.DataFrame, height: int = 430, title: str | None = None) -> go.Figure:
    """Observed bad rate vs mean predicted PD by PD decile, one line per model (cal: model, n, bads, mean_pd, bad_rate)."""
    fig = go.Figure()
    lim = float(max(cal.mean_pd.max(), cal.bad_rate.max())) * 1.08
    fig.add_trace(go.Scatter(x=[0, lim], y=[0, lim], mode="lines", line=dict(color=AXIS, width=1), name="Perfect calibration", hoverinfo="skip"))
    ratios = {}
    for name in [n for n in MODEL_COLORS if n in set(cal.model)]:
        c = cal[cal.model == name]
        ratios[name] = float((c.mean_pd * c.n).sum() / c.bads.sum())
        err = (dict(type="data", symmetric=False, array=c.ci_high - c.bad_rate, arrayminus=c.bad_rate - c.ci_low, color=MODEL_COLORS[name], thickness=1, width=0)
               if {"ci_low", "ci_high"} <= set(c.columns) else None)
        fig.add_trace(go.Scatter(x=c.mean_pd, y=c.bad_rate, mode="lines+markers", name=name, line=dict(color=MODEL_COLORS[name], width=2), error_y=err,
                                 marker=dict(size=8, line=dict(color=SURFACE, width=2)), hovertemplate="predicted %{x:.2%}<br>observed %{y:.2%}<extra>" + name + "</extra>"))
    if title is None:
        lo, hi = min(ratios.values()), max(ratios.values())
        title = (f"Both models rank well but under-predict the test quarter: mean PD is {1 - hi:.0%} to {1 - lo:.0%} below the observed bad rate"
                 if hi < 1 else "Observed bad rate vs predicted PD by decile")
    base_layout(fig, title, "Observed bad rate vs mean predicted PD by PD decile, out-of-time test Jan to Mar 2020 (%; 95% intervals)", height=height)
    fig.update_xaxes(title="Mean predicted PD", tickformat=".0%", range=[0, lim])
    fig.update_yaxes(title="Observed bad rate", tickformat=".0%", range=[0, lim])
    return fig


def shap_importance(imp: pd.DataFrame, top: int = 15, height: int = 520) -> go.Figure:
    """Mean |SHAP| of the top inputs (imp: feature, label, group, mean_abs_shap, share), sorted by impact."""
    grp = imp.groupby("group").share.sum()
    track = float(grp.get("Repayment history", 0) + grp.get("Previous applications", 0))
    t = imp.head(top).iloc[::-1]
    fig = go.Figure(go.Bar(x=t.mean_abs_shap, y=t.label, orientation="h", marker_color=BLUE, width=0.6, customdata=np.c_[t.group, t.share],
                           hovertemplate="%{y}<br>%{customdata[0]}<br>mean |SHAP| %{x:.3f} (%{customdata[1]:.1%} of total)<extra></extra>"))
    base_layout(fig, f"The client's track record carries {track:.0%} of the challenger's impact; the largest single input carries {imp.share.iloc[0]:.0%}",
                f"Average absolute impact on the log-odds of default (mean |SHAP|), top {top} inputs, out-of-time test sample", height=height, legend=False)
    fig.update_layout(margin=dict(l=310))
    fig.update_xaxes(title="Mean |SHAP| (log-odds)")
    return fig


def iv_bars(feat: pd.DataFrame, top: int = 15, height: int = 470) -> go.Figure:
    """Information Value on the training window for the top inputs (feat: label, group, iv_train), sorted by IV."""
    t = feat.sort_values("iv_train", ascending=False).head(top)
    lead = t.group.value_counts()
    title = f"{lead.index[0]} inputs make up {lead.iloc[0]} of the {top} strongest univariate signals"
    t = t.iloc[::-1]
    fig = go.Figure(go.Bar(x=t.iv_train, y=t.label, orientation="h", marker_color=BLUE, width=0.6, customdata=t.group,
                           hovertemplate="%{y}<br>%{customdata}<br>IV %{x:.3f}<extra></extra>"))
    base_layout(fig, title, f"Information Value on the training window, top {top} of {len(feat)} features (0.1 = medium, 0.3 = strong)", height=height, legend=False)
    fig.update_layout(margin=dict(l=300))
    fig.update_xaxes(title="Information Value")
    return fig


def ablation_dots(t: pd.DataFrame, height: int = 400) -> go.Figure:
    """Out-of-time Gini of the same LightGBM set-up with different inputs (t: model, gini; first row = ours). Dots, so a zoomed axis is honest."""
    t = t.reset_index(drop=True)
    colors = [BLUE, ORANGE, NEUTRAL][: len(t)]
    fig = go.Figure(go.Scatter(x=t.model, y=t.gini, mode="markers+text", marker=dict(color=colors, size=16, line=dict(color=SURFACE, width=2)),
                               text=[f"{v:.3f}" for v in t.gini], textposition="top center", textfont=dict(color=INK, size=12.5),
                               hovertemplate="%{x}<br>Gini %{y:.3f}<extra></extra>"))
    base_layout(fig, f"Used as provided, the snapshot would overstate the model by {100 * (t.gini[1] - t.gini[0]):.1f} Gini points",
                "Out-of-time test Gini of the same LightGBM set-up with different inputs (dots; axis zoomed to the range shown)", height=height, legend=False)
    fig.update_yaxes(range=[float(t.gini.min()) - 0.03, float(t.gini.max()) + 0.03], title="Gini")
    fig.update_xaxes(tickangle=0)
    return fig


WINDOW_LABELS = {"train": "Train (in-sample)", "valid": "Validation", "test": "Out-of-time test", "monitor": "Monitoring (Apr-Oct 2020)"}


def gini_by_window(met: pd.DataFrame, height: int = 430) -> go.Figure:
    """Gini by time window and model (met: model, window, gini). The training window is in-sample and flagged as such."""
    piv = met.pivot_table(index="window", columns="model", values="gini").reindex(list(WINDOW_LABELS))
    fig = go.Figure()
    for name in [n for n in MODEL_COLORS if n in piv.columns][::-1]:
        fig.add_trace(go.Bar(x=[WINDOW_LABELS[w] for w in piv.index], y=piv[name], name=name, marker_color=MODEL_COLORS[name],
                             hovertemplate="%{x}: Gini %{y:.3f}<extra>" + name + "</extra>"))
    oos = piv.drop(index="train")
    ch, cp = "Challenger (LightGBM)", "Champion (scorecard)"
    title = ("The challenger ranks better in every out-of-sample window" if (oos[ch] > oos[cp]).all()
             else "Gini by window: neither model leads in every out-of-sample window")
    base_layout(fig, title, "Gini by time window (rank-ordering; the money view decides). Training bars are in-sample and flatter the challenger", height=height)
    fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0.1)
    fig.update_yaxes(range=[0, max(0.7, float(piv.max().max()) + 0.05)], title="Gini")
    return fig


def calibration_drift_title(mon: pd.DataFrame, test=(202001, 202003), monitor_from: int = 202004) -> str:
    """Takeaway for the monthly calibration-ratio chart: how far predicted PDs were from actual in the test months and after."""
    t = mon[(mon.decision_month >= test[0]) & (mon.decision_month <= test[1])].calibration_ratio
    a = mon[mon.decision_month >= monitor_from].calibration_ratio
    if t.empty or a.empty:
        return "Mean predicted PD ÷ observed bad rate by month"
    return (f"Predicted PDs ran {1 - t.max():.0%} to {1 - t.min():.0%} below actual in Jan to Mar 2020 "
            f"and {a.min() - 1:.0%} to {a.max() - 1:.0%} above it from April 2020")


def setup_notebook_renderer() -> str:
    """Interactive charts plus a static PNG copy (so GitHub can show them) when kaleido can find Chrome; interactive only otherwise."""
    import plotly.io as pio

    try:
        go.Figure().to_image(format="png", width=10, height=10)
        pio.renderers.default = "notebook+png"
    except Exception:  # noqa: BLE001
        pio.renderers.default = "notebook"
    return pio.renderers.default
