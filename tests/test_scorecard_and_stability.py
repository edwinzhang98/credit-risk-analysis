"""Regression tests for the scorecard's points and reason codes, and for the stability index of categorical inputs."""
import numpy as np
import pandas as pd

from src.metrics import psi_categorical
from src.modeling import fit_scorecard, scorecard_points, scorecard_reason_codes


def _toy_applications(n=6000, seed=1):
    rng = np.random.default_rng(seed)
    x1 = rng.normal(0, 1, n)                      # higher = riskier
    x2 = rng.gamma(2.0, 1.0, n)                   # higher = safer
    cat = rng.choice(["a", "b", "c"], n, p=[0.5, 0.3, 0.2])
    logit = -3 + 0.9 * x1 - 0.5 * x2 + np.where(cat == "c", 0.8, 0.0)
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    X = pd.DataFrame({"avg_dpd_24m": x1, "employment_years": x2, "product_type": cat})
    X.loc[rng.random(n) < 0.15, "avg_dpd_24m"] = np.nan        # history field with no record
    X.loc[rng.random(n) < 0.10, "employment_years"] = np.nan   # form field not provided
    return X, y


def test_points_add_up_to_the_score_and_missing_reasons_are_labelled():
    X, y = _toy_applications()
    res = fit_scorecard(X, y, numeric=["avg_dpd_24m", "employment_years"], categorical=["product_type"], max_features=3)
    pts = scorecard_points(res, X)
    score = res.scorecard.score(X[res.selected])
    assert np.max(np.abs(pts.sum(axis=1).to_numpy() - score)) < 1e-6
    reasons = scorecard_reason_codes(res, X, {c: c for c in X.columns}, top_k=len(res.selected))
    lost = reasons[[c for c in reasons.columns if c.endswith("_points_lost")]].to_numpy()
    assert (lost >= -1e-9).all()  # never more points than the best bin
    first = reasons["reason_1"]
    if "avg_dpd_24m" in res.selected:
        assert not first[X.avg_dpd_24m.isna() & first.str.startswith("avg_dpd_24m")].str.contains("not provided").any()
        assert first[X.avg_dpd_24m.isna() & first.str.startswith("avg_dpd_24m")].str.endswith("(no record)").all()
    if "employment_years" in res.selected:
        assert first[X.employment_years.isna() & first.str.startswith("employment_years")].str.endswith("(not provided)").all()


def test_categorical_psi():
    a = ["x"] * 50 + ["y"] * 50
    assert psi_categorical(a, a) == 0.0
    shifted = ["x"] * 80 + ["y"] * 20
    expected = (0.8 - 0.5) * np.log(0.8 / 0.5) + (0.2 - 0.5) * np.log(0.2 / 0.5)
    assert abs(psi_categorical(a, shifted) - expected) < 1e-9
    assert psi_categorical(a + [None] * 10, a + [None] * 10) == 0.0  # missing is its own category
    assert psi_categorical(a, a + ["z"] * 10) > 0  # a new category counts as a shift
