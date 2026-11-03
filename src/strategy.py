"""Decision-policy simulation: cut-off curves, cut-off tables, swap sets, headroom and the three-tier policy.

Inputs are arrays aligned row by row:
    pd_   calibrated probability of default
    y     1 = bad (defaulted), 0 = good
    gain  money earned if the loan is approved and repays   (margin x amount, currency units)
    loss  money lost if the loan is approved and defaults   (EAD x LGD x amount, currency units)
Everything is vectorised (cumulative sums), so the dashboard can recompute on every slider move.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.economics import Review, ev_approve, ev_review
from src.metrics import wilson_interval


# ---------------------------------------------------------------------------------------------------------------------
# Approve masks
# ---------------------------------------------------------------------------------------------------------------------
def approve_below(pd_, threshold) -> np.ndarray:
    """Two-tier policy: approve when PD < threshold (threshold may be a per-loan array, e.g. product break-evens)."""
    return np.asarray(pd_, float) < np.asarray(threshold, float)


def approve_ev_positive(pd_, gain, loss) -> np.ndarray:
    """Cost-based rule: approve when the expected profit of approving is positive (= product-specific break-even PD)."""
    return ev_approve(pd_, gain, loss) > 0


def approve_at_rate(pd_, rate: float) -> np.ndarray:
    """Approve the `rate` share of applications with the lowest PD (stable tie-break on row order)."""
    pd_ = np.asarray(pd_, float)
    k = int(round(np.clip(rate, 0, 1) * len(pd_)))
    mask = np.zeros(len(pd_), bool)
    mask[np.argsort(pd_, kind="mergesort")[:k]] = True
    return mask


def threshold_for_rate(pd_, rate: float) -> float:
    """PD cut-off that approves (approximately) the `rate` share of applications."""
    s = np.sort(np.asarray(pd_, float))
    k = int(round(np.clip(rate, 0, 1) * len(s)))
    if k <= 0:
        return float(s[0])
    if k >= len(s):
        return float(np.nextafter(s[-1], np.inf))
    return float((s[k - 1] + s[k]) / 2)


# ---------------------------------------------------------------------------------------------------------------------
# Policy evaluation
# ---------------------------------------------------------------------------------------------------------------------
def evaluate_policy(approve, y, gain, loss, amount=None) -> dict:
    """Rates and money for an approve mask (two-tier)."""
    a, y = np.asarray(approve, bool), np.asarray(y, int)
    gain, loss = np.asarray(gain, float), np.asarray(loss, float)
    bad = y == 1
    n, n_app = len(y), int(a.sum())
    out = {
        "applications": n,
        "approved": n_app,
        "approval_rate": n_app / n,
        "bad_rate_approved": (a & bad).sum() / max(n_app, 1),
        "capture_rate": (~a & bad).sum() / max(bad.sum(), 1),
        "false_positive_rate": (~a & ~bad).sum() / max((~bad).sum(), 1),
        "credit_loss": loss[a & bad].sum(),
        "forgone_margin": gain[~a & ~bad].sum(),
        "net_profit": gain[a & ~bad].sum() - loss[a & bad].sum(),
    }
    out["total_cost"] = out["credit_loss"] + out["forgone_margin"]
    if amount is not None:
        amount = np.asarray(amount, float)
        out["bad_rate_approved_by_amount"] = amount[a & bad].sum() / max(amount[a].sum(), 1e-9)
        out["approved_amount"] = amount[a].sum()
    return out


class _Cum:
    """Cumulative sums over applications sorted by PD (lowest risk first)."""

    def __init__(self, pd_, y, gain, loss):
        order = np.argsort(np.asarray(pd_, float), kind="mergesort")
        self.p = np.asarray(pd_, float)[order]
        yy = np.asarray(y, float)[order]
        gg, ll = np.asarray(gain, float)[order], np.asarray(loss, float)[order]
        z = np.zeros(1)
        self.n = len(yy)
        self.bad = np.concatenate([z, np.cumsum(yy)])
        self.loss_bad = np.concatenate([z, np.cumsum(ll * yy)])
        self.gain_good = np.concatenate([z, np.cumsum(gg * (1 - yy))])
        self.tot_bad, self.tot_good = self.bad[-1], self.n - self.bad[-1]
        self.tot_gain_good = self.gain_good[-1]


def _curve_from_k(c: _Cum, k) -> pd.DataFrame:
    k = np.asarray(k, int)
    approved = k.astype(float)
    declined = c.n - approved
    bads_app = c.bad[k]
    bads_dec = c.tot_bad - bads_app
    goods_dec = declined - bads_dec
    credit_loss = c.loss_bad[k]
    forgone = c.tot_gain_good - c.gain_good[k]
    with np.errstate(divide="ignore", invalid="ignore"):
        return pd.DataFrame(
            {
                "approval_rate": approved / c.n,
                "approved": approved,
                "bad_rate_approved": np.where(approved > 0, bads_app / approved, np.nan),
                "capture_rate": bads_dec / max(c.tot_bad, 1),
                "false_positive_rate": goods_dec / max(c.tot_good, 1),
                "decline_precision": np.where(declined > 0, bads_dec / declined, np.nan),
                "credit_loss": credit_loss,
                "forgone_margin": forgone,
                "total_cost": credit_loss + forgone,
                "net_profit": c.gain_good[k] - credit_loss,
            }
        )


def curve_by_threshold(pd_, y, gain, loss, thresholds) -> pd.DataFrame:
    """Policy metrics for 'approve if PD < t' for each single cut-off t (same t for every product)."""
    c = _Cum(pd_, y, gain, loss)
    t = np.asarray(thresholds, float)
    out = _curve_from_k(c, np.searchsorted(c.p, t, side="left"))
    out.insert(0, "threshold", t)
    return out


def curve_by_approval_rate(pd_, y, gain, loss, rates) -> pd.DataFrame:
    """Policy metrics when approving the lowest-PD share r of applications, for each r."""
    c = _Cum(pd_, y, gain, loss)
    rates = np.asarray(rates, float)
    k = np.clip(np.round(rates * c.n), 0, c.n).astype(int)
    out = _curve_from_k(c, k)
    out.insert(0, "threshold", np.where(k < c.n, c.p[np.minimum(k, c.n - 1)], np.inf))
    return out


def rate_at_same_bad_rate(pd_, y, target_bad_rate: float) -> float:
    """Largest approval rate whose approved-book bad rate does not exceed `target_bad_rate`."""
    order = np.argsort(np.asarray(pd_, float), kind="mergesort")
    cum_bad = np.cumsum(np.asarray(y, float)[order])
    k = np.arange(1, len(order) + 1)
    ok = np.nonzero(cum_bad / k <= target_bad_rate + 1e-12)[0]
    return float((ok.max() + 1) / len(order)) if len(ok) else 0.0


def cutoff_table(pd_, y, gain, loss, thresholds) -> pd.DataFrame:
    """One row per single PD cut-off: approval rate, bad rate (95% CI), capture, false positives, money."""
    t = curve_by_threshold(pd_, y, gain, loss, thresholds)
    lo, hi = wilson_interval(t["bad_rate_approved"] * t["approved"], t["approved"])
    t["bad_rate_ci_low"], t["bad_rate_ci_high"] = lo, hi
    return t


def score_band_table(score, y, bands) -> pd.DataFrame:
    """Score/odds table for a points scorecard: volume, bad rate, good:bad odds and cumulative figures by points band.

    `bands` are ascending band edges in points; rows are listed from the riskiest (lowest points) band upward, and the
    cumulative columns read as "decline everything at or below this band".
    """
    s = np.asarray(score, float)
    df = pd.DataFrame({"band": pd.cut(s, bins=bands, right=False), "y": np.asarray(y, int)})
    g = df.groupby("band", observed=False)["y"].agg(applications="size", bads="sum").reset_index()
    g = g[g.applications > 0].copy()
    g["goods"] = g["applications"] - g["bads"]
    g["bad_rate"] = g["bads"] / g["applications"]
    g["odds_good_bad"] = g["goods"] / g["bads"].replace(0, np.nan)
    g["share"] = g["applications"] / g["applications"].sum()
    g["cum_decline_rate"] = g["applications"].cumsum() / g["applications"].sum()
    g["cum_bads_declined"] = g["bads"].cumsum() / g["bads"].sum()
    rest_n = g["applications"].sum() - g["applications"].cumsum()
    rest_b = g["bads"].sum() - g["bads"].cumsum()
    g["bad_rate_if_cutoff_above_band"] = rest_b / rest_n.replace(0, np.nan)
    lo, hi = wilson_interval(g["bads"], g["applications"])
    g["bad_rate_ci_low"], g["bad_rate_ci_high"] = lo, hi
    g["band"] = g["band"].astype(str)
    return g.reset_index(drop=True)


# ---------------------------------------------------------------------------------------------------------------------
# Swap set and headroom
# ---------------------------------------------------------------------------------------------------------------------
SWAP_CELLS = ["Approved by both", "Swap-in (declined -> approved)", "Swap-out (approved -> declined)", "Declined by both"]


def swap_set(approve_current, approve_proposed, y, amount, gain, loss) -> pd.DataFrame:
    """2x2 cross-tab of two policies on the same applications with bad rates and money per cell."""
    a, b = np.asarray(approve_current, bool), np.asarray(approve_proposed, bool)
    y, amount = np.asarray(y, int), np.asarray(amount, float)
    gain, loss = np.asarray(gain, float), np.asarray(loss, float)
    rows = []
    for name, m in zip(SWAP_CELLS, [a & b, ~a & b, a & ~b, ~a & ~b]):
        n, bads = int(m.sum()), int(y[m].sum())
        lo, hi = wilson_interval(bads, n) if n else (np.nan, np.nan)
        rows.append(
            {
                "cell": name, "applications": n, "share": n / len(y), "bads": bads,
                "bad_rate": bads / n if n else np.nan, "bad_rate_ci_low": float(lo), "bad_rate_ci_high": float(hi),
                "loan_amount": amount[m].sum(),
                "credit_loss_if_approved": loss[m & (y == 1)].sum(),
                "margin_if_approved": gain[m & (y == 0)].sum(),
            }
        )
    out = pd.DataFrame(rows)
    out["net_value_if_approved"] = out["margin_if_approved"] - out["credit_loss_if_approved"]
    return out


def swap_summary(approve_current, approve_proposed, y, gain, loss, amount=None) -> pd.DataFrame:
    cur = evaluate_policy(approve_current, y, gain, loss, amount)
    new = evaluate_policy(approve_proposed, y, gain, loss, amount)
    keys = ["approval_rate", "bad_rate_approved", "capture_rate", "false_positive_rate", "credit_loss", "forgone_margin", "net_profit"]
    return pd.DataFrame({"metric": keys, "current": [cur[k] for k in keys], "proposed": [new[k] for k in keys]}).assign(change=lambda d: d.proposed - d.current)


def headroom_table(book_bad_rate: float, tail_bad_rate: float, tail_count: int, swap_in_bad_rates) -> pd.DataFrame:
    """How many new approvals each declined tail loan pays for at a constant book bad rate.

    Decline d loans with bad rate t from a book with bad rate B, then add s swap-ins with bad rate r.
    Constant bad rate requires s * (r - B) = d * (t - B)  ->  s/d = (t - B) / (r - B)  (r > B).
    Net approvals change by s - d, positive only when r < t. r is unobservable here (no rejected applicants in the data).
    """
    B, t, d = book_bad_rate, tail_bad_rate, tail_count
    rows = []
    for r in np.asarray(swap_in_bad_rates, float):
        if r <= B:
            ratio = np.inf
        else:
            ratio = (t - B) / (r - B)
        rows.append({"swap_in_bad_rate": r, "new_approvals_per_decline": ratio, "swap_ins_affordable": ratio * d if np.isfinite(ratio) else np.inf,
                     "net_change_in_approvals": (ratio - 1) * d if np.isfinite(ratio) else np.inf})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------------------------------
# Three-tier policy: auto-approve / manual review / decline, chosen per loan by expected value, within review capacity
# ---------------------------------------------------------------------------------------------------------------------
TIERS = ["Auto-approve", "Manual review", "Decline"]


def _most_valuable(idx: np.ndarray, value: np.ndarray, cap: int) -> np.ndarray:
    """The `cap` entries of `idx` with the largest `value` (stable order for ties)."""
    if len(idx) <= cap:
        return idx
    return idx[np.argsort(-value[idx], kind="mergesort")[:cap]]


def assign_tiers(pd_, gain, loss, review: Review, capacity: float | None = None,
                 capacity_share: float | None = None, groups=None) -> np.ndarray:
    """0 = auto-approve, 1 = manual review, 2 = decline.

    Each loan gets the action with the highest expected profit: approve (1-p)g - pL, decline 0, or review
    (reviewer removes a share of bads and of goods, at a fixed cost per case). If more loans want review than the team
    can handle, the reviews with the largest gain over the next-best action are kept. Capacity is either
    `capacity` (max number of reviews in total) or `capacity_share` (max reviews as a share of applications), applied
    separately within each value of `groups` (e.g. the application month), so no month exceeds its own cap.
    """
    eva = ev_approve(pd_, gain, loss)
    evr = ev_review(pd_, gain, loss, review)
    best_auto = np.maximum(eva, 0.0)
    value_of_review = evr - best_auto
    tier = np.where(eva > 0, 0, 2)
    want = np.nonzero(value_of_review > 0)[0]
    if capacity_share is not None:
        grp = np.zeros(len(tier), dtype=int) if groups is None else pd.factorize(np.asarray(groups))[0]
        caps = np.bincount(grp)
        keep = np.concatenate([_most_valuable(want[grp[want] == k], value_of_review, int(capacity_share * caps[k]))
                               for k in range(len(caps))] + [np.array([], dtype=int)])
    elif capacity is not None:
        keep = _most_valuable(want, value_of_review, int(capacity))
    else:
        keep = want
    tier[keep] = 1
    return tier


def tier_outcomes(tier, y, gain, loss, amount, review: Review, months: float = 1.0) -> tuple[pd.DataFrame, dict]:
    """Volumes, bad rates and money per tier (review outcomes as expected values, so results are reproducible)."""
    tier, y = np.asarray(tier, int), np.asarray(y, int)
    gain, loss, amount = np.asarray(gain, float), np.asarray(loss, float), np.asarray(amount, float)
    bad = y == 1
    keep_good, keep_bad = 1 - review.good_decline_rate, 1 - review.bad_catch_rate
    rows = []
    for i, name in enumerate(TIERS):
        m = tier == i
        n, n_bad = int(m.sum()), int((m & bad).sum())
        g_good, l_bad = gain[m & ~bad].sum(), loss[m & bad].sum()
        if i == 0:
            approved, appr_bads, credit_loss, margin, forgone, cost = n, n_bad, l_bad, g_good, 0.0, 0.0
        elif i == 1:
            approved = (n - n_bad) * keep_good + n_bad * keep_bad
            appr_bads = n_bad * keep_bad
            credit_loss, margin = l_bad * keep_bad, g_good * keep_good
            forgone, cost = g_good * (1 - keep_good), review.cost_per_case * n
        else:
            approved, appr_bads, credit_loss, margin, forgone, cost = 0.0, 0.0, 0.0, 0.0, g_good, 0.0
        rows.append({
            "tier": name, "applications": n, "share": n / len(y), "per_month": n / months, "bads": n_bad,
            "bad_rate": n_bad / n if n else np.nan, "median_amount": float(np.median(amount[m])) if n else np.nan,
            "approved": approved, "approved_bads": appr_bads, "credit_loss": credit_loss, "margin": margin,
            "forgone_margin": forgone, "review_cost": cost, "net_profit": margin - credit_loss - cost,
        })
    t = pd.DataFrame(rows)
    approved, approved_bads = t["approved"].sum(), t["approved_bads"].sum()
    totals = {
        "applications": len(y),
        "approval_rate": approved / len(y),
        "bad_rate_approved": approved_bads / max(approved, 1e-9),
        "review_rate": float((tier == 1).mean()),
        "reviews_per_month": float((tier == 1).sum() / months),
        "credit_loss": t["credit_loss"].sum(),
        "forgone_margin": t["forgone_margin"].sum(),
        "review_cost": t["review_cost"].sum(),
        "net_profit": t["net_profit"].sum(),
    }
    return t, totals
