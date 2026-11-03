"""Unit economics: the cost matrix that turns model PDs into a cut-off and into money.

Definitions follow docs/02_metric_definitions.md. All money is per loan and proportional to the loan amount A:
    approve a good  -> + margin_good * A           (profit)
    approve a bad   -> - ead_share * lgd * A       (credit loss; cost of a false negative)
    decline a good  -> forgo margin_good * A       (cost of a false positive)
    decline a bad   -> 0                            (loss avoided)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class Economics:
    margin_good: float = 0.10  # net lifetime profit of a repaid loan, share of loan amount
    ead_share: float = 0.80  # exposure at default, share of loan amount
    lgd: float = 0.75  # loss given default, share of exposure

    @classmethod
    def from_config(cls, cfg: dict) -> "Economics":
        return cls(**cfg["economics"])

    @property
    def loss_bad(self) -> float:
        """Cost of approving a borrower who defaults, as a share of the loan amount (EAD x LGD)."""
        return self.ead_share * self.lgd

    @property
    def cost_ratio(self) -> float:
        """How many good loans' margin one bad loan wipes out (FN cost / FP cost)."""
        return self.loss_bad / self.margin_good

    @property
    def breakeven_pd(self) -> float:
        """Approve when calibrated PD is below this: expected value (1-p)*m - p*L > 0  <=>  p < m / (m + L)."""
        return self.margin_good / (self.margin_good + self.loss_bad)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(loss_bad=self.loss_bad, cost_ratio=self.cost_ratio, breakeven_pd=self.breakeven_pd)
        return d


@dataclass(frozen=True)
class Review:
    cost_per_case: float = 300.0  # currency units per manual review
    bad_catch_rate: float = 0.40  # share of reviewed bads that the reviewer declines
    good_decline_rate: float = 0.10  # share of reviewed goods that the reviewer declines anyway
    capacity_share: float = 0.05  # monthly review capacity as a share of monthly applications

    @classmethod
    def from_config(cls, cfg: dict) -> "Review":
        return cls(**cfg["review"])


def expected_value_approve(pd_, amount, econ: Economics):
    """Expected profit of approving: A * [(1 - p) * m - p * L]."""
    pd_, amount = np.asarray(pd_, float), np.asarray(amount, float)
    return amount * ((1 - pd_) * econ.margin_good - pd_ * econ.loss_bad)


def expected_value_review(pd_, amount, econ: Economics, review: Review):
    """Expected profit of sending to manual review: the reviewer declines a share of bads and of goods, then we approve the rest."""
    pd_, amount = np.asarray(pd_, float), np.asarray(amount, float)
    keep_good = 1 - review.good_decline_rate
    keep_bad = 1 - review.bad_catch_rate
    return amount * ((1 - pd_) * keep_good * econ.margin_good - pd_ * keep_bad * econ.loss_bad) - review.cost_per_case


def optimal_tier_bounds(econ: Economics, review: Review, amount_ref: float) -> tuple[float, float]:
    """PD band where manual review beats both auto-approve and auto-decline, for a loan of size `amount_ref`.

    review > approve  <=>  p > (g*m + C/A) / (c*L + g*m)
    review > decline  <=>  p < ((1-g)*m - C/A) / ((1-g)*m + (1-c)*L)
    with m = margin, L = loss of a bad, c = bad catch rate, g = good decline rate, C = review cost, A = loan amount.
    If the band is empty, review never pays and both bounds collapse to the two-tier break-even PD.
    """
    m, loss, c, g = econ.margin_good, econ.loss_bad, review.bad_catch_rate, review.good_decline_rate
    k = review.cost_per_case / amount_ref
    lower = (g * m + k) / (c * loss + g * m) if (c * loss + g * m) > 0 else np.inf
    upper = ((1 - g) * m - k) / ((1 - g) * m + (1 - c) * loss)
    if not (lower < upper):
        return econ.breakeven_pd, econ.breakeven_pd
    return float(lower), float(upper)
