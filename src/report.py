"""Build reports/report.html (one self-contained file, opens offline) and the static PNG figures used in the README.

Every number comes from reports/metrics.json or the cached tables written by the notebooks, and every chart is drawn by
the same functions the dashboard uses (src/charts.py), so the report, the notebooks and the app always agree.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from jinja2 import Environment, FileSystemLoader
from plotly.offline import get_plotlyjs

from src import charts
from src.config import ROOT, load_config
from src.economics import PRODUCT_NAMES

CH, CP = "Challenger (LightGBM)", "Champion (scorecard)"


# ---------------------------------------------------------------------------------------------------------------------
# formatting helpers used in the template
# ---------------------------------------------------------------------------------------------------------------------
def pct(x, d=1):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * float(x):.{d}f}%"


def pp(x, d=1):
    return f"{100 * float(x):+.{d}f} pp"


def money(x):
    return charts.fmt_money(float(x))


def num(x, d=0):
    return f"{float(x):,.{d}f}"


def table(df: pd.DataFrame, formats: dict | None = None, index: bool = False) -> str:
    """Pandas -> compact HTML table with per-column formatting."""
    df = df.copy()
    for col, f in (formats or {}).items():
        if col in df:
            df[col] = df[col].map(lambda v, f=f: "" if v is None or (isinstance(v, float) and np.isnan(v)) else f(v))
    return df.to_html(index=index, classes="tbl", border=0, escape=True)


def fig_html(fig: go.Figure) -> str:
    fig.update_layout(autosize=True)
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displaylogo": False, "responsive": True})


# ---------------------------------------------------------------------------------------------------------------------
def build_report(cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    cache = Path(cfg["processed_dir"]) / "dashboard"
    reports = Path(cfg["reports_dir"])
    figdir = reports / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    m = json.loads((reports / "metrics.json").read_text())
    L = lambda name: pd.read_parquet(cache / f"{name}.parquet")  # noqa: E731

    F = {}  # figures (HTML snippets)
    curves = {CP: L("loss_curve_champion"), CH: L("loss_curve_challenger")}
    trade = {CP: L("tradeoff_champion"), CH: L("tradeoff_challenger")}
    loss_fig = charts.loss_curve(curves, rule_points={CH: m["loss_curve"][CH]["rule"]["total_cost"]}, headline=CH, baseline_cost=m["approve_all"]["total_cost"])
    F["loss"] = fig_html(loss_fig)
    F["monthly"] = fig_html(charts.monthly_volume_bad_rate(L("dq_time_range"), cfg["split"]))
    F["offset"] = fig_html(charts.snapshot_offset_chart(L("dq_snapshot_offset")))
    F["pit"] = fig_html(charts.point_in_time_chart(L("dq_point_in_time")))
    feat = L("feature_screening")
    top = feat.head(15).iloc[::-1]
    f_iv = go.Figure(go.Bar(x=top.iv_train, y=top.label, orientation="h", marker_color=charts.BLUE, width=0.6,
                            hovertemplate="%{y}<br>IV %{x:.3f}<extra></extra>"))
    charts.base_layout(f_iv, "Repayment behaviour carries most of the univariate signal",
                       "Information Value on the training window, top 15 of 90 features (0.1 = medium, 0.3 = strong)", height=470, legend=False)
    f_iv.update_layout(margin=dict(l=300))
    F["iv"] = fig_html(f_iv)

    abl = L("leakage_ablation")
    t = abl[abl.split == "test"].reset_index(drop=True)
    f_abl = go.Figure(go.Bar(x=t.model, y=t.gini, marker_color=[charts.BLUE, charts.ORANGE, charts.NEUTRAL], width=0.5,
                             text=[f"{v:.3f}" for v in t.gini], textposition="outside", textfont=dict(color=charts.INK)))
    charts.base_layout(f_abl, f"Used as provided, the snapshot would overstate the model by {100 * (t.gini[1] - t.gini[0]):.1f} Gini points",
                       "Out-of-time test Gini of the same LightGBM set-up with different inputs", height=400, legend=False)
    f_abl.update_yaxes(range=[max(0, float(t.gini.min()) - 0.06), float(t.gini.max()) + 0.03], title="Gini")
    F["ablation"] = fig_html(f_abl)

    cal = L("calibration_test")
    f_cal = go.Figure()
    lim = float(max(cal.mean_pd.max(), cal.bad_rate.max())) * 1.08
    f_cal.add_trace(go.Scatter(x=[0, lim], y=[0, lim], mode="lines", line=dict(color=charts.AXIS, width=1), name="Perfect calibration", hoverinfo="skip"))
    for name in [CP, CH]:
        c = cal[cal.model == name]
        f_cal.add_trace(go.Scatter(x=c.mean_pd, y=c.bad_rate, mode="lines+markers", name=name, line=dict(color=charts.MODEL_COLORS[name], width=2),
                                   marker=dict(size=8, line=dict(color=charts.SURFACE, width=2))))
    charts.base_layout(f_cal, "Both models rank well but under-predict the test quarter's higher default level",
                       "Observed bad rate vs mean predicted PD by PD decile, Jan to Mar 2020", height=430)
    f_cal.update_xaxes(title="Mean predicted PD", tickformat=".0%", range=[0, lim])
    f_cal.update_yaxes(title="Observed bad rate", tickformat=".0%", range=[0, lim])
    F["calibration"] = fig_html(f_cal)

    imp = L("shap_global")
    grp = imp.groupby("group").share.sum().sort_values(ascending=False)
    track = float(grp.get("Repayment history", 0) + grp.get("Previous applications", 0))
    top_s = imp.head(15).iloc[::-1]
    f_shap = go.Figure(go.Bar(x=top_s.mean_abs_shap, y=top_s.label, orientation="h", marker_color=charts.BLUE, width=0.6,
                              hovertemplate="%{y}<br>mean |SHAP| %{x:.3f}<extra></extra>"))
    charts.base_layout(f_shap, f"The client's track record carries {track:.0%} of the challenger's impact; no single input dominates",
                       "Average absolute impact on the log-odds of default (mean |SHAP|), top 15 inputs", height=500, legend=False)
    f_shap.update_layout(margin=dict(l=310))
    F["shap"] = fig_html(f_shap)

    F["breakeven"] = fig_html(charts.breakeven_sensitivity(L("breakeven_sensitivity")))
    rm = m["room"][CH]
    F["headroom"] = fig_html(charts.headroom_chart(L("headroom"), m["data"]["test_bad_rate"], rm["tail_bad_rate"]))
    mv = m["model_value"]
    pts = [{"x": mv["status_quo"]["approval_rate"], "y": mv["status_quo"]["bad_rate_approved"], "label": "Champion, cost-based rule", "color": charts.ORANGE, "text": "champion rule"},
           {"x": mv["same_bad_rate"]["approval_rate"], "y": mv["status_quo"]["bad_rate_approved"], "label": "Challenger at the same bad rate", "color": charts.BLUE,
            "text": "same bad rate", "symbol": "diamond", "textpos": "bottom right"},
           {"x": m["loss_curve"][CH]["rule"]["approval_rate"], "y": m["loss_curve"][CH]["rule"]["bad_rate_approved"], "label": "Challenger, cost-based rule",
            "color": charts.BLUE, "text": "challenger rule", "textpos": "bottom left"}]
    trade_fig = charts.tradeoff_curve(trade, pts, x_range=(0.85, 1.0))
    F["tradeoff"] = fig_html(trade_fig)
    swap_rule = L("swap_its_own_costbased_rule")
    swap_fig = charts.swap_bars(swap_rule, title="Under the recommended policy, swap-outs default about twice as often as swap-ins")
    F["swap"] = fig_html(swap_fig)
    tiers = L("tiers")
    F["tiers"] = fig_html(charts.tier_bars(tiers))
    fair = L("fairness")
    rec = fair[fair.policy == "Challenger cost rule (recommended)"].copy()
    sex = rec[rec.attribute == "Sex"].assign(group=lambda d: d.group.map({"F": "Female", "M": "Male"}))
    age = rec[rec.attribute == "Age band"]
    F["fair_sex"] = fig_html(charts.fairness_bars(sex, "sex", title=f"Approval rates by sex are virtually equal (ratio {sex.approval_rate_ratio.min():.2f})"))
    F["fair_age"] = fig_html(charts.fairness_bars(age, "age band", title=f"Lowest approval-rate ratio by age band is {age.approval_rate_ratio.min():.2f}, above the 0.80 screen"))
    mon = L("monitoring_monthly")
    F["psi"] = fig_html(charts.monitor_lines(mon, "psi", "The challenger's score PSI stayed below 0.10; the scorecard's crossed it from May 2020",
                                             "Population stability index of each model's PD vs the training window, by decision month (shaded = monitoring window)",
                                             fmt=".3f", bands=((0.10, "investigate 0.10", charts.STATUS["warning"]), (0.25, "act 0.25", charts.STATUS["critical"]))))
    F["calratio"] = fig_html(charts.monitor_lines(mon, "calibration_ratio", "The PD level drifted: too low before COVID, too high after",
                                                  "Mean predicted PD ÷ observed bad rate by decision month (1.0 = calibrated)", fmt=".2f",
                                                  bands=((0.8, "0.80", charts.STATUS["warning"]), (1.25, "1.25", charts.STATUS["warning"]))))
    F["gini"] = fig_html(charts.monitor_lines(mon[mon.decision_month >= 201911], "gini", "Rank-ordering held up through the shock",
                                              "Gini by decision month, out-of-sample months only (from Nov 2019)", fmt=".3f"))

    # static images for README / executive summary (kaleido needs a local Chrome/Chromium; the HTML report does not)
    try:
        for name, fig, h in [("loss_curve", loss_fig, 470), ("tradeoff_curve", trade_fig, 460), ("swap_set", swap_fig, 380)]:
            fig.write_image(str(figdir / f"{name}.png"), width=1100, height=h, scale=2)
        charts.snapshot_offset_chart(L("dq_snapshot_offset")).write_image(str(figdir / "snapshot_offset.png"), width=1100, height=400, scale=2)
    except Exception as e:  # noqa: BLE001
        print(f"[report] static PNG export skipped ({type(e).__name__}: {e}); install Chrome or run `plotly_get_chrome` to enable it")

    T = {}  # tables
    T["loss_view"] = table(L("loss_view")[["model", "policy", "approval_rate", "bad_rate_approved", "credit_loss", "forgone_margin", "total_cost", "net_profit", "cost_vs_default_0_5"]],
                           {"approval_rate": pct, "bad_rate_approved": lambda v: pct(v, 2), "credit_loss": money, "forgone_margin": money, "total_cost": money,
                            "net_profit": money, "cost_vs_default_0_5": lambda v: f"{100 * v:+.0f}%"})
    be = L("breakeven")
    T["breakeven"] = table(be[["product_name", "margin_good", "loss_bad", "cost_ratio", "breakeven_pd", "loans", "bad_rate", "median_amount"]],
                           {"margin_good": lambda v: pct(v, 0), "loss_bad": lambda v: pct(v, 0), "cost_ratio": lambda v: f"{v:.1f}×", "breakeven_pd": pct,
                            "loans": num, "bad_rate": lambda v: pct(v, 2), "median_amount": num})
    ct = L("cutoff_table")
    ct = ct[ct.model == CH][["threshold", "approval_rate", "bad_rate_approved", "bad_rate_ci_low", "bad_rate_ci_high", "capture_rate", "false_positive_rate", "credit_loss", "forgone_margin", "net_profit"]]
    T["cutoff"] = table(ct, {"threshold": pct, "approval_rate": pct, "bad_rate_approved": lambda v: pct(v, 2), "bad_rate_ci_low": lambda v: pct(v, 2),
                             "bad_rate_ci_high": lambda v: pct(v, 2), "capture_rate": pct, "false_positive_rate": pct, "credit_loss": money, "forgone_margin": money, "net_profit": money})
    rp = L("rule_by_product")
    T["by_product"] = table(rp[["product", "model", "breakeven_pd", "applications", "approval_rate", "bad_rate_approved", "net_profit"]],
                            {"breakeven_pd": pct, "applications": num, "approval_rate": pct, "bad_rate_approved": lambda v: pct(v, 2), "net_profit": money})
    swap_fmt = {"applications": num, "share": pct, "bads": num, "bad_rate": lambda v: pct(v, 2), "bad_rate_ci_low": lambda v: pct(v, 2), "bad_rate_ci_high": lambda v: pct(v, 2),
                "loan_amount": money, "credit_loss_if_approved": money, "net_value_if_approved": money}
    swap_cols = ["cell", "applications", "share", "bads", "bad_rate", "bad_rate_ci_low", "bad_rate_ci_high", "loan_amount", "credit_loss_if_approved", "net_value_if_approved"]
    room_sw = L("room_swap_challenger")
    T["room"] = table(room_sw[room_sw.applications > 0][swap_cols], swap_fmt)
    hp = L("headroom_points")
    T["headroom"] = table(hp[["swap_in_bad_rate", "swap_in_bad_rate_vs_book", "new_approvals_per_decline", "net_change_per_month"]],
                          {"swap_in_bad_rate": pct, "swap_in_bad_rate_vs_book": lambda v: f"{v:.2f}×", "new_approvals_per_decline": lambda v: f"{v:.2f}",
                           "net_change_per_month": lambda v: f"{v:+,.0f}"})
    T["swap_same_rate"] = table(L("swap_the_same_approval_rate")[swap_cols], swap_fmt)
    T["swap_same_bad"] = table(L("swap_the_same_bad_rate")[swap_cols], swap_fmt)
    T["swap_rule"] = table(swap_rule[swap_cols], swap_fmt)
    T["profile"] = table(L("swap_profile"), {"applications": num, "bad_rate": lambda v: pct(v, 2), "median_amount": num, "share_cash": pct, "share_pos": pct,
                                            "share_new_to_lender": pct, "mean_pd_champion": lambda v: pct(v, 2), "mean_pd_challenger": lambda v: pct(v, 2)})
    T["tiers"] = table(tiers[["tier", "applications", "share", "per_month", "bad_rate", "median_amount", "credit_loss", "forgone_margin", "review_cost", "net_profit"]],
                       {"applications": num, "share": pct, "per_month": num, "bad_rate": lambda v: pct(v, 2), "median_amount": num, "credit_loss": money,
                        "forgone_margin": money, "review_cost": money, "net_profit": money})
    grid = L("review_grid").pivot(index="bad_catch_rate", columns="good_decline_rate", values="net_profit_uplift_vs_two_tier")
    grid.index = [f"catch {v:.0%}" for v in grid.index]
    grid.columns = [f"good declined {v:.0%}" for v in grid.columns]
    T["grid"] = table(grid.reset_index().rename(columns={"index": "reviewer catch rate"}), {c: money for c in grid.columns})
    T["fair"] = table(fair[["policy", "attribute", "group", "applications", "approval_rate", "approval_rate_ratio", "observed_bad_rate", "bad_rate_approved", "calibration_ratio"]],
                      {"applications": num, "approval_rate": pct, "approval_rate_ratio": lambda v: f"{v:.2f}", "observed_bad_rate": lambda v: pct(v, 2),
                       "bad_rate_approved": lambda v: pct(v, 2), "calibration_ratio": lambda v: f"{v:.2f}"})
    mm = L("model_metrics")
    T["models"] = table(mm[["model", "window", "loans", "bad_rate", "mean_pd", "calibration_ratio", "auc", "gini", "ks", "brier"]],
                        {"loans": num, "bad_rate": lambda v: pct(v, 2), "mean_pd": lambda v: pct(v, 2), "calibration_ratio": lambda v: f"{v:.2f}",
                         "auc": lambda v: f"{v:.3f}", "gini": lambda v: f"{v:.3f}", "ks": lambda v: f"{v:.3f}", "brier": lambda v: f"{v:.4f}"})
    biz = L("model_business_comparison")
    T["biz"] = table(biz[["model", "policy", "approval_rate", "bad_rate_approved", "capture_rate", "false_positive_rate", "credit_loss", "forgone_margin", "net_profit"]],
                     {"approval_rate": pct, "bad_rate_approved": lambda v: pct(v, 2), "capture_rate": pct, "false_positive_rate": pct, "credit_loss": money,
                      "forgone_margin": money, "net_profit": money})
    seg = L("segment_metrics")
    T["segments"] = table(seg[["segment", "model", "loans", "share_of_test", "bad_rate", "calibration_ratio", "gini"]],
                          {"loans": num, "share_of_test": pct, "bad_rate": lambda v: pct(v, 2), "calibration_ratio": lambda v: f"{v:.2f}", "gini": lambda v: f"{v:.3f}"})
    imb = L("imbalance_experiment")
    T["imbalance"] = table(imb[["approach", "test_auc", "mean_pd_raw", "observed_bad_rate", "approval_rate_if_cutoff_on_raw_output", "net_profit_if_cutoff_on_raw_output",
                                "approval_rate_after_recalibration", "net_profit_after_recalibration"]],
                           {"test_auc": lambda v: f"{v:.3f}", "mean_pd_raw": lambda v: pct(v, 1), "observed_bad_rate": lambda v: pct(v, 2),
                            "approval_rate_if_cutoff_on_raw_output": pct, "net_profit_if_cutoff_on_raw_output": money, "approval_rate_after_recalibration": pct,
                            "net_profit_after_recalibration": money})
    lb = L("leakage_business")
    T["leak_business"] = table(lb, {"approval_rate": pct, "expected_bad_rate_of_approved": lambda v: pct(v, 2), "observed_bad_rate_of_approved": lambda v: pct(v, 2), "net_profit": money})
    lg = L("leakage_ablation_groups").pivot_table(index="model", columns="group", values="gini").reset_index()
    T["leak_groups"] = table(lg, {c: (lambda v: f"{v:.3f}") for c in lg.columns if c != "model"})
    T["dq_rows"] = table(L("dq_row_counts"), {"n_rows": num, "n_cases": num, "share_of_base_cases": pct, "n_orphan_cases": num})
    T["dq_keys"] = table(L("dq_keys"))
    T["offset"] = table(L("dq_snapshot_offset"), {"match_rate": pct})
    T["csi"] = table(L("csi_flags"), {"max_csi": lambda v: f"{v:.2f}"})
    T["drift"] = table(L("calibration_drift")[["view", "mean_pd", "observed_bad_rate", "calibration_ratio", "rule_approval_rate", "rule_bad_rate_of_approved", "rule_net_profit"]],
                       {"mean_pd": lambda v: pct(v, 2), "observed_bad_rate": lambda v: pct(v, 2), "calibration_ratio": lambda v: f"{v:.2f}", "rule_approval_rate": pct,
                        "rule_bad_rate_of_approved": lambda v: pct(v, 2), "rule_net_profit": money})
    T["sens"] = table(L("economics_sensitivity"), {"breakeven_cash": pct, "breakeven_pos": pct, "breakeven_revolving": pct, "approval_rate": pct,
                                                   "bad_rate_approved": lambda v: pct(v, 2), "net_profit": money, "net_profit_gain_vs_approve_all": money})
    T["sizes"] = table(L("test_sizes"), {"loans_needed": num})
    cc = L("champion_checks")
    T["champion_checks"] = table(cc, {"valid_gini": lambda v: f"{v:.3f}", "test_gini": lambda v: f"{v:.3f}"})
    bi = L("bootstrap_intervals")
    U = {k: (r["low"], r["high"]) for k, r in bi.iterrows()}
    coefs = L("scorecard_coefficients").sort_values("iv", ascending=False)
    T["scorecard"] = table(coefs[["label", "feature", "iv", "coefficient"]], {"iv": lambda v: f"{v:.3f}", "coefficient": lambda v: f"{v:.3f}"})
    proxy = L("proxy_check")
    T["proxy"] = table(proxy, {"auc_from_model_inputs": lambda v: f"{v:.2f}"})
    sample = L("explain_sample")
    ex = sample[sample.decision_challenger == "Decline"].sort_values("pd_challenger", ascending=False).iloc[len(sample) // 20]
    example = {
        "case_id": int(ex.case_id), "product": PRODUCT_NAMES.get(ex.product_type, ex.product_type), "amount": ex.loan_amount, "pd": ex.pd_challenger,
        "breakeven": ex.breakeven_pd, "reasons": [ex[f"reason_{i}"] for i in range(1, 5) if ex[f"reason_{i}"]], "sc_reasons": [ex[f"sc_reason_{i}"] for i in range(1, 5)],
        "points": ex.score_champion, "outcome": "defaulted" if ex.target == 1 else "did not default",
    }
    fs, fa = sex.set_index("group"), age.set_index("group")
    notebooks = [(n, f"{n}.html") for n in ["01_data_audit", "02_feature_eng", "03_modeling", "04_threshold_and_strategy"]]

    env = Environment(loader=FileSystemLoader(str(ROOT / "src" / "templates")), autoescape=False)
    env.filters.update(pct=pct, pp=pp, money=money, num=num)
    html = env.get_template("report.html.j2").render(
        m=m, F=F, T=T, CH=CH, CP=CP, plotly_js=get_plotlyjs(), today=date.today().isoformat(), example=example, track=track,
        grp=grp.to_dict(), fs=fs, fa=fa, notebooks=notebooks, mon=mon, imp=imp, U=U, cc=cc,
        psi_cp_max=float(mon[(mon.model == CP) & (mon.decision_month >= 202004)].psi.max()),
        psi_ch_max=float(mon[(mon.model == CH) & (mon.decision_month >= 202004)].psi.max()),
    )
    out = reports / "report.html"
    out.write_text(html)
    return out


if __name__ == "__main__":
    print(build_report())
