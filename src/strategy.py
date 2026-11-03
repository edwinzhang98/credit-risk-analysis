"""Decision-policy simulation: cut-off curves, cut-off tables, swap sets and the three-tier policy.

Everything is vectorised with cumulative sums so the dashboard can recompute on every slider move.
Inputs are numpy-compatible arrays aligned row by row: pd_ (calibrated PD), y (1 = bad), amount (loan amount).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.economics import Economics, Review
from src.metrics import wilson_interval


# --------------------------------------------------------------------------------------------------------------------
# Approve masks
# --------------------------------------------------------------------------------------------------------------------
def approve_below(pd_, threshold: float) -> np.ndarray:
    """Two-tier policy: approve when PD < threshold."""
    return np.asarray(pd_, float) < threshold


def approve_at_rate(pd_, rate: float) -> np.ndarray:
    """Approve the `rate` share of applications with the lowest PD (stable tie-break on row order)."""
    pd_ = np.asarray(pd_, float)
    k = int(round(np.clip(rate, 0, 1) * len(pd_)))
    order = np.argsort(pd_, kind="mergesort")
    mask = np.zeros(len(pd_), bool)
    mask[order[:k]] = True
    return mask


def threshold_for_rate(pd_, rate: float) -> float:
    """PD cut-off that approves (approximately) `rate` of applications."""
    pd_ = np.sort(np.asarray(pd_, float))
    k = int(round(np.clip(rate, 0, 1) * len(pd_)))
    if k <= 0:
        return float(pd_[0])
    if k >= len(pd_):
        return float(np.nextafter(pd_[-1], np.inf))
    return float((pd_[k - 1] + pd_[k]) / 2)


# --------------------------------------------------------------------------------------------------------------------
# Cut-off curves
# --------------------------------------------------------------------------------------------------------------------
class _Cum:
    """Cumulative sums over applications sorted by PD (lowest risk first)."""

    def __init__(self, pd_, y, amount):
        pd_, y, amount = np.asarray(pd_, float), np.asarray(y, float), np.asarray(amount, float)
        order = np.argsort(pd_, kind="mergesort")
        self.p = pd_[order]
        yy, aa = y[order], amount[order]
        z = np.zeros(1)
        self.n = len(yy)
        self.bad = np.concatenate([z, np.cumsum(yy)])
        self.bad_amt = np.concatenate([z, np.cumsum(aa * yy)])
        self.good_amt = np.concatenate([z, np.cumsum(aa * (1 - yy))])
        self.tot_bad, self.tot_good = self.bad[-1], self.n - self.bad[-1]
        self.tot_bad_amt, self.tot_good_amt = self.bad_amt[-1], self.good_amt[-1]


def _curve_from_k(c: _Cum, k: np.ndarray, econ: Economics) -> pd.DataFrame:
    k = np.asarray(k, int)
    approved = k.astype(float)
    declined = c.n - approved
    bads_app = c.bad[k]
    bads_dec = c.tot_bad - bads_app
    goods_dec = declined - bads_dec
    credit_loss = econ.loss_bad * c.bad_amt[k]
    forgone = econ.margin_good * (c.tot_good_amt - c.good_amt[k])
    margin_app = econ.margin_good * c.good_amt[k]
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
                "net_profit": margin_app - credit_loss,
            }
        )


def curve_by_threshold(pd_, y, amount, econ: Economics, thresholds) -> pd.DataFrame:
    """Policy metrics for 'approve if PD < t' at each threshold t."""
    c = _Cum(pd_, y, amount)
    thresholds = np.asarray(thresholds, float)
    out = _curve_from_k(c, np.searchsorted(c.p, thresholds, side="left"), econ)
    out.insert(0, "threshold", thresholds)
    return out


def curve_by_approval_rate(pd_, y, amount, econ: Economics, rates) -> pd.DataFrame:
    """Policy metrics when approving the lowest-PD share `r` of applications, for each r."""
    c = _Cum(pd_, y, amount)
    rates = np.asarray(rates, float)
    k = np.clip(np.round(rates * c.n), 0, c.n).astype(int)
    out = _curve_from_k(c, k, econ)
    out.insert(0, "threshold", np.where(k < c.n, c.p[np.minimum(k, c.n - 1)], np.inf))
    return out


def evaluate_policy(approve, y, amount, econ: Economics) -> dict:
    """Money and rates for an arbitrary approve mask (two-tier)."""
    approve, y, amount = np.asarray(approve, bool), np.asarray(y, int), np.asarray(amount, float)
    n, n_app = len(y), approve.sum()
    bads = y == 1
    credit_loss = econ.loss_bad * amount[approve & bads].sum()
    forgone = econ.margin_good * amount[~approve & ~bads].sum()
    margin_app = econ.margin_good * amount[approve & ~bads].sum()
    return {
        "applications": n,
        "approved": int(n_app),
        "approval_rate": n_app / n,
        "bad_rate_approved": (approve & bads).sum() / max(n_app, 1),
        "capture_rate": (~approve & bads).sum() / max(bads.sum(), 1),
        "false_positive_rate": (~approve & ~bads).sum() / max((~bads).sum(), 1),
        "credit_loss": credit_loss,
        "forgone_margin": forgone,
        "total_cost": credit_loss + forgone,
        "net_profit": margin_app - credit_loss,
    }


def rate_at_same_bad_rate(pd_, y, target_bad_rate: float) -> float:
    """Largest approval rate whose approved-book bad rate does not exceed `target_bad_rate`."""
    pd_, y = np.asarray(pd_, float), np.asarray(y, float)
    order = np.argsort(pd_, kind="mergesort")
    cum_bad = np.cumsum(y[order])
    k = np.arange(1, len(y) + 1)
    ok = np.nonzero(cum_bad / k <= target_bad_rate + 1e-12)[0]
    return float((ok.max() + 1) / len(y)) if len(ok) else 0.0


# --------------------------------------------------------------------------------------------------------------------
# Cut-off table (the table risk teams look at every week)
# --------------------------------------------------------------------------------------------------------------------
def cutoff_table(pd_, y, amount, econ: Economics, thresholds) -> pd.DataFrame:
    """One row per PD cut-off: approval rate, bad rate, capture, false positives, money."""
    t = curve_by_threshold(pd_, y, amount, econ, thresholds)
    lo, hi = wilson_interval(t["bad_rate_approved"] * t["approved"], t["approved"])
    t["bad_rate_ci_low"], t["bad_rate_ci_high"] = lo, hi
    return t


def score_band_table(pd_, y, amount, n_bands: int = 10) -> pd.DataFrame:
    """Applications split into equal-size PD bands (1 = safest): volume, bad rate, cumulative bad rate."""
    df = pd.DataFrame({"pd": np.asarray(pd_, float), "y": np.asarray(y, int), "amount": np.asarray(amount, float)})
    df["band"] = pd.qcut(df["pd"].rank(method="first"), n_bands, labels=range(1, n_bands + 1)).astype(int)
    g = df.groupby("band").agg(n=("y", "size"), bads=("y", "sum"), pd_min=("pd", "min"), pd_max=("pd", "max"), mean_pd=("pd", "mean"), amount=("amount", "sum")).reset_index()
    g["bad_rate"] = g["bads"] / g["n"]
    g["cum_approval_rate"] = g["n"].cumsum() / g["n"].sum()
    g["cum_bad_rate"] = g["bads"].cumsum() / g["n"].cumsum()
    g["cum_capture_if_declined_from_here"] = g["bads"][::-1].cumsum()[::-1] / g["bads"].sum()
    lo, hi = wilson_interval(g["bads"], g["n"])
    g["bad_rate_ci_low"], g["bad_rate_ci_high"] = lo, hi
    return g


# --------------------------------------------------------------------------------------------------------------------
# Swap set
# --------------------------------------------------------------------------------------------------------------------
SWAP_CELLS = ["Approved by both", "Swap-in (declined -> approved)", "Swap-out (approved -> declined)", "Declined by both"]


def swap_set(approve_current, approve_proposed, y, amount, econ: Economics) -> pd.DataFrame:
    """Cross-tab of two policies on the same applications, with bad rates and money per cell."""
    a, b = np.asarray(approve_current, bool), np.asarray(approve_proposed, bool)
    y, amount = np.asarray(y, int), np.asarray(amount, float)
    masks = [a & b, ~a & b, a & ~b, ~a & ~b]
    rows = []
    for name, m in zip(SWAP_CELLS, masks):
        n, bads = int(m.sum()), int(y[m].sum())
        lo, hi = wilson_interval(bads, n) if n else (np.nan, np.nan)
        rows.append(
            {
                "cell": name,
                "applications": n,
                "share": n / len(y),
                "bads": bads,
                "bad_rate": bads / n if n else np.nan,
                "bad_rate_ci_low": float(lo),
                "bad_rate_ci_high": float(hi),
                "loan_amount": amount[m].sum(),
                "credit_loss_if_approved": econ.loss_bad * amount[m & (y == 1)].sum(),
                "margin_if_approved": econ.margin_good * amount[m & (y == 0)].sum(),
            }
        )
    out = pd.DataFrame(rows)
    out["net_value_if_approved"] = out["margin_if_approved"] - out["credit_loss_if_approved"]
    return out


def swap_summary(approve_current, approve_proposed, y, amount, econ: Economics) -> pd.DataFrame:
    """Before/after view of the approved book for two policies."""
    cur = evaluate_policy(approve_current, y, amount, econ)
    new = evaluate_policy(approve_proposed, y, amount, econ)
    keys = ["approval_rate", "bad_rate_approved", "capture_rate", "false_positive_rate", "credit_loss", "forgone_margin", "net_profit"]
    return pd.DataFrame({"metric": keys, "current": [cur[k] for k in keys], "proposed": [new[k] for k in keys]}).assign(change=lambda d: d.proposed - d.current)


# --------------------------------------------------------------------------------------------------------------------
# Three-tier policy: auto-approve / manual review / decline
# --------------------------------------------------------------------------------------------------------------------
TIERS = ["Auto-approve", "Manual review", "Decline"]


def three_tier(pd_, y, amount, t_review: float, t_decline: float, econ: Economics, review: Review, months: float = 1.0):
    """Volumes, bad rates and money per tier. Review outcomes use expected values (no random draws), so results are reproducible.

    Returns (tier_table, totals). `months` converts volumes to a monthly run-rate for the capacity check.
    """
    pd_, y, amount = np.asarray(pd_, float), np.asarray(y, int), np.asarray(amount, float)
    t_decline = max(t_decline, t_review)
    auto = pd_ < t_review
    rev = (pd_ >= t_review) & (pd_ < t_decline)
    dec = pd_ >= t_decline
    bad = y == 1
    m, loss = econ.margin_good, econ.loss_bad
    keep_good, keep_bad = 1 - review.good_decline_rate, 1 - review.bad_catch_rate

    rows = []
    for name, mask in zip(TIERS, [auto, rev, dec]):
        n = int(mask.sum())
        goods_amt, bads_amt = amount[mask & ~bad].sum(), amount[mask & bad].sum()
        n_bad = int((mask & bad).sum())
        if name == "Auto-approve":
            approved, approved_bads = n, n_bad
            credit_loss, margin, forgone, cost = loss * bads_amt, m * goods_amt, 0.0, 0.0
        elif name == "Manual review":
            approved = (n - n_bad) * keep_good + n_bad * keep_bad
            approved_bads = n_bad * keep_bad
            credit_loss, margin = loss * bads_amt * keep_bad, m * goods_amt * keep_good
            forgone, cost = m * goods_amt * (1 - keep_good), review.cost_per_case * n
        else:
            approved, approved_bads = 0.0, 0.0
            credit_loss, margin, forgone, cost = 0.0, 0.0, m * goods_amt, 0.0
        rows.append(
            {
                "tier": name,
                "applications": n,
                "share": n / len(y),
                "per_month": n / months,
                "bads": n_bad,
                "bad_rate": n_bad / n if n else np.nan,
                "approved": approved,
                "approved_bads": approved_bads,
                "credit_loss": credit_loss,
                "margin": margin,
                "forgone_margin": forgone,
                "review_cost": cost,
                "net_profit": margin - credit_loss - cost,
            }
        )
    t = pd.DataFrame(rows)
    approved, approved_bads = t["approved"].sum(), t["approved_bads"].sum()
    capacity = review.capacity_share * len(y) / months
    totals = {
        "applications": len(y),
        "approval_rate": approved / len(y),
        "bad_rate_approved": approved_bads / max(approved, 1e-9),
        "review_rate": rev.mean(),
        "reviews_per_month": rev.sum() / months,
        "review_capacity_per_month": capacity,
        "capacity_used": (rev.sum() / months) / capacity if capacity > 0 else np.inf,
        "credit_loss": t["credit_loss"].sum(),
        "forgone_margin": t["forgone_margin"].sum(),
        "review_cost": t["review_cost"].sum(),
        "net_profit": t["net_profit"].sum(),
    }
    return t, totals


def best_tiers_under_capacity(pd_, y, amount, econ: Economics, review: Review, months: float, grid=None):
    """Grid-search (t_review, t_decline) to maximise net profit with review volume within capacity."""
    pd_ = np.asarray(pd_, float)
    if grid is None:
        qs = np.unique(np.quantile(pd_, np.linspace(0.50, 0.999, 120)))
        grid = qs
    best = None
    capacity = review.capacity_share * len(pd_)
    sorted_pd = np.sort(pd_)
    for i, lo in enumerate(grid):
        n_lo = np.searchsorted(sorted_pd, lo, side="left")
        for hi in grid[i:]:
            n_rev = np.searchsorted(sorted_pd, hi, side="left") - n_lo
            if n_rev > capacity:
                break
            _, tot = three_tier(pd_, y, amount, lo, hi, econ, review, months)
            if best is None or tot["net_profit"] > best[2]["net_profit"]:
                best = (float(lo), float(hi), tot)
    return best
