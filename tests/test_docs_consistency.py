"""Consistency checks between the pipeline's numbers and the documents people read.

The headline figures are rendered from reports/metrics.json and must appear in the README, the decision memo and the executive
summary; reports/report.html must have been built from the current metrics and template. A changed result therefore fails the
tests until the documents are updated, instead of drifting silently.
"""
import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CH = "Challenger (LightGBM)"
M = json.loads((ROOT / "reports" / "metrics.json").read_text())


def _money(x: float) -> str:
    return f"{x / 1e6:.1f}M"


def headline_figures() -> dict:
    room, mv, td = M["room"][CH], M["model_value"], M["test_design"]
    return {
        "cost of wrong decisions vs today": f"{-M['vs_today'][CH]['total_cost_change']:.0%}",
        "tightening gain": _money(room["net_gain"]),
        "share of approvals declined": f"{room['declined_share']:.1%}",
        "bad rate of the declined tail": f"{room['tail_bad_rate']:.1%}",
        "book bad rate after the rule": f"{M['loss_curve'][CH]['rule']['bad_rate_approved']:.2%}",
        "test-quarter bad rate": f"{M['data']['test_bad_rate']:.2%}",
        "extra approvals at the same bad rate": f"{100 * mv['same_bad_rate']['extra_approvals_pp']:.1f}",
        "credit-loss cut at the same approval rate": f"{-mv['same_approval_rate']['credit_loss_change_pct']:.0%}",
        "below-cut-off test size": f"{td['below_cutoff_loans_needed']:,}",
        "price of information": _money(td["price_of_information"]),
    }


DOCS = ["README.md", "docs/readout.md", "reports/executive_summary.md"]


@pytest.mark.parametrize("doc", DOCS)
def test_headline_figures_appear_in_each_document(doc):
    text = (ROOT / doc).read_text()
    missing = {k: v for k, v in headline_figures().items() if v not in text}
    assert not missing, f"{doc} does not show the current value of: {missing}"


def test_readme_shows_model_and_trial_figures():
    text = (ROOT / "README.md").read_text()
    mm, td, tt = M["models"], M["test_design"], M["three_tier"]
    for label, value in {
        "challenger Gini": f"{mm['gini_test_challenger']:.3f}",
        "scorecard Gini": f"{mm['gini_test_champion']:.3f}",
        "challenger-arm loans": f"{td['champion_challenger_loans_challenger']:,}",
        "reviews a month": f"{tt['totals']['reviews_per_month']:,.0f}",
        "review-tier gain": _money(tt["uplift_vs_two_tier"]),
        "tightening gain, sampling interval low": _money(M["uncertainty"]["room_net_gain"]["low"]),
        "tightening gain, sampling interval high": _money(M["uncertainty"]["room_net_gain"]["high"]),
    }.items():
        assert value in text, f"README.md does not show the current {label} ({value})"


def test_report_was_built_from_current_metrics_and_template():
    html = (ROOT / "reports" / "report.html").read_text()
    stamp = re.search(r"built-from metrics\.json sha256=(\w+) template sha256=(\w+)", html)
    assert stamp, "reports/report.html has no build stamp; rebuild it with `make report`"
    digest = lambda p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()  # noqa: E731
    assert stamp.group(1) == digest("reports/metrics.json"), "report.html is older than reports/metrics.json; run `make report`"
    assert stamp.group(2) == digest("src/templates/report.html.j2"), "report.html is older than its template; run `make report`"
