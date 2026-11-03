"""Unit economics: the cost matrix that turns model PDs into a cut-off and into money.

Per loan with amount A and product k (definitions in docs/02_metric_definitions.md):
    approve a good  -> + m_k * A                 (net lifetime margin; also the cost of wrongly declining a good = FP cost)
    approve a bad   -> - EAD * LGD * A           (credit loss; the cost of a false negative)
    decline a good  -> forgo m_k * A
    decline a bad   -> 0
Expected value of approving a loan with calibrated PD p:  A * [(1 - p) * m_k - p * L],  L = EAD * LGD,
which is positive exactly when p < m_k / (m_k + L): the product's break-even PD.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

PRODUCT_NAMES = {"CAL": "Cash loan", "COL": "Point-of-sale loan", "REL": "Revolving (card)"}


@dataclass
class Economics:
    lgd: float = 0.75
    ead_share: float = 0.80
    margin_by_product: dict = field(default_factory=lambda: {"CAL": 0.20, "COL": 0.05, "REL": 0.10})
    margin_default: float = 0.10

    @classmethod
    def from_config(cls, cfg: dict) -> "Economics":
        e = cfg["economics"]
        return cls(lgd=e["lgd"], ead_share=e["ead_share"], margin_by_product=dict(e["margin_by_product"]), margin_default=e["margin_default"])

    def replace(self, **kw) -> "Economics":
        d = {"lgd": self.lgd, "ead_share": self.ead_share, "margin_by_product": dict(self.margin_by_product), "margin_default": self.margin_default}
        d.update(kw)
        return Economics(**d)

    @property
    def loss_rate(self) -> float:
        """Cost of approving a borrower who defaults, as a share of the loan amount (EAD x LGD)."""
        return self.ead_share * self.lgd

    def margin(self, product) -> np.ndarray:
        s = pd.Series(np.asarray(product, dtype=object))
        return s.map(self.margin_by_product).fillna(self.margin_default).to_numpy(float)

    def breakeven_pd(self, product: str | None = None) -> float:
        m = self.margin_by_product.get(product, self.margin_default) if product else self.margin_default
        return m / (m + self.loss_rate)

    def breakeven_table(self) -> pd.DataFrame:
        rows = [
            {"product": k, "product_name": PRODUCT_NAMES.get(k, k), "margin_good": m, "loss_bad": self.loss_rate,
             "cost_ratio": self.loss_rate / m, "breakeven_pd": m / (m + self.loss_rate)}
            for k, m in self.margin_by_product.items()
        ]
        return pd.DataFrame(rows)

    def per_loan(self, amount, product) -> tuple[np.ndarray, np.ndarray]:
        """(gain if approved and good, loss if approved and bad) in currency units for each loan."""
        amount = np.asarray(amount, float)
        return self.margin(product) * amount, self.loss_rate * amount

    def breakeven_per_loan(self, product) -> np.ndarray:
        m = self.margin(product)
        return m / (m + self.loss_rate)

    def to_dict(self) -> dict:
        return {
            "lgd": self.lgd, "ead_share": self.ead_share, "loss_rate": self.loss_rate,
            "margin_by_product": dict(self.margin_by_product), "margin_default": self.margin_default,
            "breakeven_by_product": {k: self.breakeven_pd(k) for k in self.margin_by_product},
        }


@dataclass
class Review:
    cost_per_case: float = 300.0  # currency units per manual review
    bad_catch_rate: float = 0.40  # share of reviewed bads that the reviewer declines
    good_decline_rate: float = 0.10  # share of reviewed goods that the reviewer declines anyway
    capacity_share: float = 0.05  # review capacity as a share of applications

    @classmethod
    def from_config(cls, cfg: dict) -> "Review":
        return cls(**cfg["review"])


def ev_approve(pd_, gain, loss) -> np.ndarray:
    """Expected profit of approving (currency units)."""
    p = np.asarray(pd_, float)
    return (1 - p) * np.asarray(gain, float) - p * np.asarray(loss, float)


def ev_review(pd_, gain, loss, review: Review) -> np.ndarray:
    """Expected profit of manual review: the reviewer declines a share of bads (and of goods); the rest is approved."""
    p = np.asarray(pd_, float)
    keep_good, keep_bad = 1 - review.good_decline_rate, 1 - review.bad_catch_rate
    return (1 - p) * keep_good * np.asarray(gain, float) - p * keep_bad * np.asarray(loss, float) - review.cost_per_case


def review_band(margin: float, loss_rate: float, review: Review, amount: float) -> tuple[float, float]:
    """PD band where review beats both approve and decline for one product and loan size (closed form).

    review > approve  <=>  p > (g*m + C/A) / (c*L + g*m)
    review > decline  <=>  p < ((1-g)*m - C/A) / ((1-g)*m + (1-c)*L)
    (m margin, L loss rate, c bad catch rate, g good decline rate, C review cost, A amount). Empty band -> (nan, nan).
    """
    m, L, c, g = margin, loss_rate, review.bad_catch_rate, review.good_decline_rate
    k = review.cost_per_case / amount
    lower = (g * m + k) / (c * L + g * m) if (c * L + g * m) > 0 else np.inf
    upper = ((1 - g) * m - k) / ((1 - g) * m + (1 - c) * L)
    return (float(lower), float(upper)) if lower < upper else (np.nan, np.nan)


def min_amount_for_review(margin: float, loss_rate: float, review: Review) -> float:
    """Smallest loan for which a review band exists (the two bounds meet)."""
    lo, hi = 1.0, 1e9
    for _ in range(200):
        mid = (lo * hi) ** 0.5
        if np.isnan(review_band(margin, loss_rate, review, mid)[0]):
            lo = mid
        else:
            hi = mid
    return hi
