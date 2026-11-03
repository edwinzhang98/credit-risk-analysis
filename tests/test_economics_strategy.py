"""Unit tests for the formulas everything else depends on (run: .venv/bin/python -m pytest -q tests)."""
import numpy as np
import pandas as pd

from src.economics import Economics, Review, ev_approve, ev_review, min_amount_for_review, review_band
from src.metrics import psi, wilson_interval
from src.strategy import (approve_ev_positive, assign_tiers, curve_by_approval_rate, curve_by_threshold, evaluate_policy,
                          headroom_table, rate_at_same_bad_rate, swap_set)


def _toy(n=20000, seed=0):
    rng = np.random.default_rng(seed)
    p = rng.beta(1, 25, n)
    y = (rng.random(n) < p).astype(int)
    amount = rng.lognormal(10, 0.6, n)
    product = rng.choice(["CAL", "COL", "REL"], n)
    return p, y, amount, product


def test_breakeven_matches_ev_sign_change():
    e = Economics()
    for prod in ["CAL", "COL", "REL"]:
        b = e.breakeven_pd(prod)
        g, l = e.per_loan([1000.0], [prod])
        assert ev_approve([b - 1e-9], g, l)[0] > 0 > ev_approve([b + 1e-9], g, l)[0]
    assert abs(e.breakeven_pd("CAL") - 0.25) < 1e-12
    assert abs(e.breakeven_pd("COL") - 0.05 / 0.65) < 1e-12


def test_review_band_matches_brute_force():
    e, r = Economics(), Review()
    m, L, A = 0.10, e.loss_rate, 35000.0
    lo, hi = review_band(m, L, r, A)
    grid = np.linspace(0.0005, 0.5, 20000)
    g, l = np.full_like(grid, m * A), np.full_like(grid, L * A)
    best = np.argmax(np.vstack([ev_approve(grid, g, l), ev_review(grid, g, l, r), np.zeros_like(grid)]), axis=0)
    rev = grid[best == 1]
    assert abs(rev.min() - lo) < 1e-3 and abs(rev.max() - hi) < 1e-3
    assert np.isnan(review_band(m, L, r, min_amount_for_review(m, L, r) * 0.99)[0])


def test_curves_match_direct_evaluation():
    p, y, amount, product = _toy()
    g, l = Economics().per_loan(amount, product)
    t = 0.07
    direct = evaluate_policy(p < t, y, g, l)
    row = curve_by_threshold(p, y, g, l, [t]).iloc[0]
    for k in ["approval_rate", "bad_rate_approved", "capture_rate", "false_positive_rate", "credit_loss", "forgone_margin", "net_profit", "total_cost"]:
        assert np.isclose(row[k], direct[k]), k
    by_rate = curve_by_approval_rate(p, y, g, l, [direct["approval_rate"]]).iloc[0]
    assert np.isclose(by_rate["bad_rate_approved"], direct["bad_rate_approved"], atol=2e-4)


def test_profit_identity_and_ev_rule_is_optimal_in_expectation():
    p, y, amount, product = _toy()
    g, l = Economics().per_loan(amount, product)
    # expected-value bookkeeping with true p: EV rule beats any single cut-off in expectation
    ev = ev_approve(p, g, l)
    best_single = max(ev[p < t].sum() for t in np.linspace(0.01, 0.4, 200))
    assert ev[approve_ev_positive(p, g, l)].sum() >= best_single - 1e-6
    res = evaluate_policy(approve_ev_positive(p, g, l), y, g, l)
    assert np.isclose(res["net_profit"], g[y == 0].sum() - res["total_cost"])


def test_same_bad_rate_and_swap_set_partition():
    p, y, amount, product = _toy()
    g, l = Economics().per_loan(amount, product)
    target = y[p < 0.05].mean()
    r = rate_at_same_bad_rate(p, y, target)
    assert 0 < r <= 1
    s = swap_set(p < 0.05, p < 0.06, y, amount, g, l)
    assert s["applications"].sum() == len(y) and s.loc[2, "applications"] == 0  # tighter -> looser has no swap-outs


def test_headroom_formula():
    h = headroom_table(0.044, 0.20, 1000, [0.10, 0.20, 0.03]).set_index("swap_in_bad_rate")
    assert np.isclose(h.loc[0.10, "new_approvals_per_decline"], (0.20 - 0.044) / (0.10 - 0.044))
    assert np.isclose(h.loc[0.20, "net_change_in_approvals"], 0.0)
    assert np.isinf(h.loc[0.03, "new_approvals_per_decline"])


def test_tiers_respect_capacity():
    p, y, amount, product = _toy()
    g, l = Economics().per_loan(amount, product)
    t = assign_tiers(p, g, l, Review(), capacity=100)
    assert (t == 1).sum() <= 100


def test_monthly_capacity_holds_in_every_month():
    p, y, amount, product = _toy()
    g, l = Economics().per_loan(amount, product)
    months = np.where(np.arange(len(p)) < len(p) // 3, 202001, 202002)
    uncapped = assign_tiers(p, g, l, Review(), capacity=None)
    t = assign_tiers(p, g, l, Review(), capacity_share=0.01, groups=months)
    for m in np.unique(months):
        assert (t[months == m] == 1).sum() <= int(0.01 * (months == m).sum())
    # a month with spare capacity keeps every review it wants; loans not sent to review keep their two-tier decision
    roomy = assign_tiers(p, g, l, Review(), capacity_share=1.0, groups=months)
    assert np.array_equal(roomy, uncapped)
    two_tier = assign_tiers(p, g, l, Review(), capacity=0)
    assert np.array_equal(t[t != 1], two_tier[t != 1])


def test_psi_and_wilson():
    rng = np.random.default_rng(1)
    a = rng.normal(size=50000)
    assert psi(a, rng.normal(size=50000)) < 0.01
    assert psi(a, rng.normal(0.5, 1, 50000)) > 0.1
    lo, hi = wilson_interval(5, 100)
    assert 0.02 < lo < 0.05 < hi < 0.12
