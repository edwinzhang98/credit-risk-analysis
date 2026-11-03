# Cut-off and swap-set pack

**Owner:** Credit Risk Analyst · **For:** credit-policy committee (Head of Credit Policy; sign-off from Model Risk / Validation, Finance, Underwriting Operations and Compliance) · **Written:** 2026-11-03

**Sources.** Every number comes from [notebook 04](../notebooks/04_threshold_and_strategy.ipynb), [reports/metrics.json](../reports/metrics.json) and the tables notebooks 03 and 04 write to `data/processed/dashboard/` (rebuilt by `make all`; the file behind each table is named in its title). Definitions: [metric definitions](02_metric_definitions.md). Assumptions and their ranges: [assumptions log](assumptions.md). Bad rates carry 95% Wilson intervals; the headline changes in money and approval rate carry 95% bootstrap intervals (200 loan-level resamples of the test quarter, fixed seed; `bootstrap_intervals.parquet`).

## 1. Purpose and set-up

This is the cut-off table a credit-risk team brings to the policy committee, built for the Head of Credit Policy's question ([request and scope](01_request_and_scope.md)): the business wants a higher approval rate, but the bad rate must not go up. Is there room on the current cut-off, who moves from declined to approved and back, and how much money is at stake? The pack shows what each cut-off does to approvals, bad rate and money, who swaps in and out, how much goes to manual review, and what has to be tested before any change is scaled.

| Item | Set-up |
|---|---|
| Population | Out-of-time test (Jan to Mar 2020): decisions 2020-01-01 to 2020-03-31, **222,681 booked loans** (74,227 a month), bad rate **4.41%** |
| Products | Cash loans 55,330 (bad rate 5.17%) · revolving (card) 32,656 (bad rate 3.58%) · point-of-sale loans 134,695 (bad rate 4.30%) |
| Models | Champion: the 16-variable WOE logistic-regression scorecard (out-of-time Gini 0.462). Challenger: LightGBM on 90 point-in-time features (Gini 0.578). Both give a PD calibrated on the Nov-Dec 2019 validation window (Platt scaling). |
| Question 1 status quo | Today's policy, which approved every loan in this data: 100% of booked loans approved, bad rate 4.41%, net profit 899.5M CU over the quarter (a 0.5 PD cut-off lands in the same place: it declines 3 loans with the champion and 55 with the challenger) |
| Question 2 status quo | The champion scorecard applying the cost-based rule (a rebuilt scorecard, not the lender's own incumbent): approval rate 92.5%, bad rate of approved 3.57%, net profit 945.5M CU |
| Proposed policy | The challenger applying the cost-based rule (90.7% approved, bad rate 3.17%, net profit 991.8M CU), plus a capacity-bound manual-review tier (3,711 reviews a month, the team's full capacity; expected 90.9% approved, bad rate 3.04%, net profit 1,003.6M CU) |
| Units | Money in the dataset's undisclosed currency units (CU), summed over the test quarter unless marked "a month". "A month" is the quarter divided by three, in booked loans. Margins, LGD, EAD and review effectiveness are assumptions. |

> **Selection bias. Read every approval rate in this pack as a share of previously approved applicants.** Every loan in the data was approved by the historical policy, so the applicants it rejected are not in the data and their bad rate is unknown. An approval rate of 90.7% means 90.7% of the applicants the old policy approved, not 90.7% of everyone who applied. Tightening (declining some of today's approvals) can be measured exactly; loosening (approving some of today's rejects) cannot. Sections 5 and 9 show what would have to be true for loosening to work and how to measure it.

**What the committee is asked to approve**

1. The cost matrix behind the cut-offs (Finance) and the break-even PDs it gives: cash 25.0%, revolving 14.3%, point-of-sale 7.7% (Section 2).
2. The challenger with the cost-based rule and a capacity-bound manual-review tier, introduced through a champion/challenger test under a pre-registered decision rule (Table 9.2) rather than a full switch (Sections 6 to 9).
3. A below-cut-off test before any loosening of today's approval line (Sections 5 and 9).

## 2. Unit economics and break-even PDs

Approving a loan of amount A with calibrated PD p is worth A × [(1 − p) × m − p × L] in expectation, where m is the product's net lifetime margin on a repaid loan and L is the loss on a bad loan: EAD 80% × LGD 75% = 60% of the amount. The value is positive exactly when p is below the **break-even PD** m ÷ (m + L). Approving only then is the **cost-based rule**.

**Table 2.1 · Break-even PD by product** (`breakeven.parquet`)

| Product | Margin on a good loan (m) | Loss on a bad loan (L) | L ÷ m | Break-even PD | Test loans | Bad rate | Median amount |
|---|---|---|---|---|---|---|---|
| Cash loan | 20% | 60% | 3× | **25.0%** | 55,330 | 5.17% | 60,000 CU |
| Revolving (card) | 10% | 60% | 6× | **14.3%** | 32,656 | 3.58% | 54,380 CU |
| Point-of-sale loan | 5% | 60% | 12× | **7.7%** | 134,695 | 4.30% | 27,504 CU |

One rule prints as three cut-offs: a bad point-of-sale loan costs twelve times what a good one earns (thin margins, many 0%-interest promotions), so point-of-sale gets the tightest cut-off, while a cash loan can carry a PD of up to 25%. L ÷ m is also the break-even good:bad odds: approve when the expected odds are better than 3:1 (cash), 6:1 (revolving) or 12:1 (point-of-sale).

**Table 2.2 · How far each assumption moves the break-even PD** (`breakeven_sensitivity.parquet`; ranges from the [assumptions log](assumptions.md))

| Assumption moved (range tested) | Break-even at the first value | Base | Break-even at the second value |
|---|---|---|---|
| Cash loan: margin 12% to 28% | 16.7% | 25.0% | 31.8% |
| Cash loan: LGD 90% to 60% | 21.7% | 25.0% | 29.4% |
| Cash loan: EAD 100% to 70% | 21.1% | 25.0% | 27.6% |
| Revolving (card): margin 5% to 15% | 7.7% | 14.3% | 20.0% |
| Point-of-sale loan: margin 2% to 9% | 3.2% | 7.7% | 13.0% |
| Point-of-sale loan: LGD 90% to 60% | 6.5% | 7.7% | 9.4% |
| Point-of-sale loan: EAD 100% to 70% | 6.3% | 7.7% | 8.7% |

The margin assumption moves the break-even most (point-of-sale: 3.2% to 13.0%); LGD and EAD move it by a few points. Finance's sign-off on margins is the assumption that matters.

**Table 2.3 · The challenger's cost-based rule under low, base and high margins** (`economics_sensitivity.parquet`)

| Margin scenario (cash / revolving / point-of-sale) | Break-even PD (cash / revolving / point-of-sale) | Approval rate | Bad rate of approved | Net profit | Gain vs approving every booked loan |
|---|---|---|---|---|---|
| Margins at the low end (12% / 5% / 2%) | 16.7% / 7.7% / 3.2% | 75.7% | 2.60% | 460.0M CU | +147.7M CU |
| Base case (20% / 10% / 5%) | 25.0% / 14.3% / 7.7% | 90.7% | 3.17% | 991.8M CU | +92.3M CU |
| Margins at the high end (28% / 15% / 9%) | 31.8% / 20.0% / 13.0% | 95.7% | 3.60% | 1,593.1M CU | +56.6M CU |

The level of profit moves with the margins, but the rule beats approving every booked loan in all three scenarios, by 56.6M to 147.7M CU a quarter. With low-end margins the rule approves only 75.7%, so the margin sign-off decides how hard the policy tightens.

## 3. Cut-off tables

A single PD cut-off applies one cut-off to every product: approve when the calibrated PD is below it. Column definitions ([metric definitions](02_metric_definitions.md)): **capture rate** = share of all bads that are declined; **false positive rate** = share of all goods that are declined; **credit loss** = loss on approved loans that defaulted (60% of the amount); **forgone margin** = margin on declined loans that would have repaid; **total cost of wrong decisions** = credit loss + forgone margin; **net profit** = margin on approved good loans − credit loss. Bad rates carry 95% Wilson intervals. The bold row has the lowest total cost on this grid.

**Table 3.1 · Challenger (LightGBM), single PD cut-offs, money in CU over the quarter** (`cutoff_table.parquet`)

| PD cut-off | Approval rate | Approved loans | Bad rate of approved (95% CI) | Capture rate | False positive rate | Credit loss | Forgone margin | Total cost | Net profit |
|---|---|---|---|---|---|---|---|---|---|
| 2.0% | 46.1% | 102,669 | 1.09% (1.02–1.15%) | 88.7% | 52.3% | 39.3M | 751.3M | 790.6M | 502.2M |
| 3.0% | 59.3% | 132,156 | 1.43% (1.37–1.50%) | 80.7% | 38.8% | 69.2M | 554.7M | 623.9M | 668.9M |
| 4.0% | 69.0% | 153,541 | 1.79% (1.72–1.85%) | 72.1% | 29.2% | 101.1M | 415.8M | 516.9M | 775.9M |
| 5.0% | 75.9% | 168,980 | 2.08% (2.02–2.15%) | 64.2% | 22.3% | 129.9M | 315.2M | 445.1M | 847.8M |
| 6.0% | 81.0% | 180,284 | 2.37% (2.30–2.44%) | 56.6% | 17.3% | 157.2M | 243.9M | 401.1M | 891.7M |
| 7.5% | 86.0% | 191,574 | 2.68% (2.61–2.75%) | 47.7% | 12.4% | 191.6M | 171.3M | 362.9M | 929.9M |
| 10.0% | 91.1% | 202,803 | 3.07% (3.00–3.15%) | 36.6% | 7.6% | 233.7M | 98.7M | 332.4M | 960.4M |
| 12.5% | 94.0% | 209,376 | 3.37% (3.29–3.45%) | 28.2% | 4.9% | 266.6M | 60.0M | 326.6M | 966.2M |
| **15.0%** | **95.9%** | **213,508** | **3.57% (3.50–3.65%)** | **22.4%** | **3.3%** | **289.0M** | **37.3M** | **326.4M** | **966.5M** |
| 20.0% | 97.9% | 218,021 | 3.90% (3.82–3.98%) | 13.6% | 1.6% | 325.1M | 17.9M | 343.0M | 949.8M |
| 25.0% | 98.9% | 220,203 | 4.08% (4.00–4.17%) | 8.5% | 0.8% | 347.6M | 9.0M | 356.6M | 936.3M |
| 30.0% | 99.4% | 221,400 | 4.22% (4.14–4.30%) | 5.0% | 0.4% | 365.7M | 4.5M | 370.2M | 922.6M |
| 50.0% | >99.9% | 222,626 | 4.41% (4.32–4.49%) | 0.2% | <0.1% | 391.4M | 0.2M | 391.7M | 901.1M |

The last row is today's policy in practice: today's policy approved every loan in this book, and a 0.5 cut-off lands in the same place (it declines 55 loans, approves 99.98% and leaves the bad rate at 4.41%). Total cost falls as the cut-off moves down until about 12.5% to 15.0%, then rises again as the margin lost on declined good customers outgrows the losses avoided.

**Table 3.2 · Champion (scorecard), single PD cut-offs, money in CU over the quarter** (`cutoff_table.parquet`)

| PD cut-off | Approval rate | Approved loans | Bad rate of approved (95% CI) | Capture rate | False positive rate | Credit loss | Forgone margin | Total cost | Net profit |
|---|---|---|---|---|---|---|---|---|---|
| 2.0% | 38.3% | 85,303 | 1.52% (1.44–1.60%) | 86.8% | 60.5% | 67.4M | 717.9M | 785.2M | 507.6M |
| 3.0% | 58.2% | 129,614 | 1.99% (1.91–2.06%) | 73.8% | 40.3% | 121.8M | 463.6M | 585.4M | 707.4M |
| 4.0% | 71.5% | 159,122 | 2.45% (2.38–2.53%) | 60.3% | 27.1% | 176.1M | 310.7M | 486.7M | 806.1M |
| 5.0% | 78.7% | 175,307 | 2.72% (2.64–2.80%) | 51.5% | 19.9% | 212.9M | 224.2M | 437.2M | 855.7M |
| 6.0% | 83.5% | 185,950 | 2.94% (2.87–3.02%) | 44.4% | 15.2% | 240.0M | 167.8M | 407.8M | 885.0M |
| 7.5% | 88.3% | 196,708 | 3.22% (3.14–3.30%) | 35.6% | 10.6% | 272.9M | 113.0M | 386.0M | 906.8M |
| **10.0%** | **93.4%** | **207,979** | **3.62% (3.54–3.70%)** | **23.4%** | **5.8%** | **316.5M** | **60.0M** | **376.6M** | **916.3M** |
| 12.5% | 96.0% | 213,857 | 3.88% (3.80–3.96%) | 15.6% | 3.4% | 343.0M | 34.5M | 377.5M | 915.3M |
| 15.0% | 97.6% | 217,268 | 4.06% (3.98–4.14%) | 10.3% | 2.1% | 361.7M | 20.1M | 381.8M | 911.0M |
| 20.0% | 99.0% | 220,538 | 4.24% (4.16–4.32%) | 4.9% | 0.8% | 378.6M | 8.1M | 386.8M | 906.0M |
| 25.0% | 99.6% | 221,852 | 4.34% (4.25–4.42%) | 2.1% | 0.3% | 387.0M | 3.3M | 390.3M | 902.5M |
| 30.0% | 99.9% | 222,365 | 4.38% (4.30–4.47%) | 0.8% | 0.1% | 390.9M | 1.2M | 392.1M | 900.7M |
| 50.0% | >99.9% | 222,678 | 4.41% (4.33–4.50%) | 0.0% | <0.1% | 393.3M | 0.03M | 393.3M | 899.5M |

The champion's lowest-cost grid point sits lower (10.0%) and costs more (376.6M CU against 326.4M CU for the challenger); at 0.5 it declines 3 loans. Because the two models put different shares of loans below the same PD, compare them at an equal approval rate or an equal bad rate (Section 6), not at an equal PD.

**Table 3.3 · Today's policy vs best single cut-off vs cost-based rule** (`loss_view.parquet`; today's policy from `reports/metrics.json` `approve_all`, and the change in total cost against it from `vs_today` for the cost-based rule; money in CU over the quarter; best single cut-offs read off the test quarter itself on a 0.25-point grid, a hindsight benchmark that favours them: 10.75% champion, 14.75% challenger)

| Model | Policy | Approval rate | Bad rate of approved | Credit loss | Forgone margin | Total cost | Total cost vs today's policy | Net profit |
|---|---|---|---|---|---|---|---|---|
| Either | Today's policy (approve every booked loan) | 100% | 4.41% | 393.3M | 0 | 393.3M | reference | 899.5M |
| Champion | Best single cut-off (PD 10.8%) | 94.3% | 3.70% | 325.3M | 50.3M | 375.6M | −4.5% | 917.2M |
| Challenger | Best single cut-off (PD 14.8%) | 95.7% | 3.55% | 287.0M | 39.3M | 326.3M | −17.0% | 966.5M |
| Champion | Cost-based rule (product break-evens) | 92.5% | 3.57% | 318.7M | 28.6M | 347.4M | −11.7% | 945.5M |
| Challenger | Cost-based rule (product break-evens) | 90.7% | 3.17% | 254.1M | 46.9M | 301.0M | −23.5% | 991.8M |

The cost-based rule beats the best single cut-off for both models (challenger: 301.0M vs 326.3M CU total cost) because each product gets its own break-even. Against today's policy, the challenger's rule cuts the total cost of wrong decisions by 23% and credit losses by 35% (the champion's rule: 12% and 19%). A 0.5 cut-off is the same comparator in practice: it declines 3 loans with the champion and 55 with the challenger (last row of Tables 3.1 and 3.2), within 1.6M CU of today's total cost.

**Table 3.4 · The cost-based rule by product** (`rule_by_product.parquet`, money in CU over the quarter)

| Product (break-even PD) | Model | Approval rate | Bad rate of approved (count) | Bad rate of approved (amount) | Capture rate | False positive rate | Credit loss | Forgone margin | Net profit |
|---|---|---|---|---|---|---|---|---|---|
| Cash loan · 25.0% | Champion | 99.6% | 5.10% | 5.59% | 1.8% | 0.4% | 148.8M | 2.3M | 689.2M |
| Cash loan · 25.0% | Challenger | 99.6% | 5.09% | 5.53% | 1.9% | 0.3% | 147.2M | 2.7M | 690.4M |
| Revolving (card) · 14.3% | Champion | 98.2% | 3.29% | 3.89% | 9.7% | 1.6% | 48.9M | 2.6M | 152.4M |
| Revolving (card) · 14.3% | Challenger | 96.8% | 2.94% | 3.17% | 20.4% | 2.5% | 38.7M | 6.7M | 158.3M |
| Point-of-sale loan · 7.7% | Champion | 88.2% | 2.93% | 4.29% | 40.0% | 10.5% | 121.0M | 23.8M | 103.9M |
| Point-of-sale loan · 7.7% | Challenger | 85.6% | 2.31% | 2.62% | 54.0% | 12.6% | 68.2M | 37.5M | 143.0M |

Most of the tightening, and most of the challenger's gain, is in point-of-sale loans: the challenger declines 14.4% of them (champion 11.8%) and keeps 54.0% of point-of-sale bads off the book (champion 40.0%), cutting point-of-sale credit losses from 121.0M to 68.2M CU (by amount, the bad rate of approved point-of-sale loans falls from 4.29% to 2.62%). On cash loans the two models are almost identical (under 0.5% declined). The amount-based bad rate of approved cash loans is higher than the count-based one (5.53% vs 5.09%) because the cash loans that default are larger than those that repay, and cash loans are the largest loans in the book (median 60,000 CU), so they carry more of the loss than their count suggests.

## 4. Scorecard points view

Policy committees usually sign the scorecard cut-off in points. Points = 600 + 20 ÷ ln 2 × ln(odds ÷ 50), where odds = good:bad from the scorecard's raw PD: 600 points means odds of 50:1, and every 20 extra points doubles the odds. The cut-off in points is the score at which the champion's calibrated PD equals the product's break-even.

**Table 4.1 · Champion cut-off in points by product** (`reports/metrics.json` `scorecard_cutoff_points`; volumes recomputed from `predictions_test.parquet`)

| Product | Break-even PD | Break-even good:bad odds | Approve when the score is above | Approval rate | Bad rate of approved | Declined loans | Bad rate of declined (95% CI) |
|---|---|---|---|---|---|---|---|
| Cash loan | 25.0% | 3:1 | **524 points** (523.6) | 99.6% | 5.10% | 248 | 20.97% (16.36–26.46%) |
| Revolving (card) | 14.3% | 6:1 | **544 points** (543.9) | 98.2% | 3.29% | 602 | 18.77% (15.85–22.08%) |
| Point-of-sale loan | 7.7% | 12:1 | **564 points** (564.2) | 88.2% | 2.93% | 15,845 | 14.64% (14.09–15.19%) |

Applied in points at the unrounded cut-offs (523.6, 543.9, 564.2), the rule reproduces the champion's cost-based decisions exactly (checked loan by loan on the test quarter); the point-of-sale line sits about 41 points above the cash line, so the same score can be approved for a cash loan and declined for a point-of-sale loan. Only 248 cash loans score below their line, so read their bad rate with the interval.

**Table 4.2 · Score / odds table, champion scorecard, all products** (`odds_table.parquet`; 20-point bands; the last three columns describe setting the cut-off at the top of the band, i.e. declining that band and everything below it)

| Score band (points) | Loans | Share | Bad rate (95% CI) | Good:bad odds | Cumulative decline rate | Share of all bads declined | Bad rate of the book that remains |
|---|---|---|---|---|---|---|---|
| below 500 | 25 | <0.1% | 20.00% (8.86–39.13%) | 4.0:1 | <0.1% | 0.1% | 4.41% |
| 500–519 | 518 | 0.2% | 25.48% (21.92–29.41%) | 2.9:1 | 0.2% | 1.4% | 4.36% |
| 520–539 | 3,969 | 1.8% | 18.27% (17.10–19.50%) | 4.5:1 | 2.0% | 8.8% | 4.11% |
| 540–559 | 14,772 | 6.6% | 13.39% (12.85–13.95%) | 6.5:1 | 8.7% | 28.9% | 3.44% |
| 560–579 | 32,520 | 14.6% | 7.72% (7.43–8.01%) | 12.0:1 | 23.3% | 54.4% | 2.62% |
| 580–599 | 62,254 | 28.0% | 4.21% (4.06–4.37%) | 22.7:1 | 51.2% | 81.1% | 1.71% |
| 600–619 | 68,696 | 30.8% | 2.13% (2.02–2.24%) | 46.0:1 | 82.1% | 96.0% | 0.99% |
| 620–639 | 37,147 | 16.7% | 1.01% (0.92–1.12%) | 97.5:1 | 98.8% | 99.8% | 0.65% |
| 640–659 | 2,742 | 1.2% | 0.66% (0.42–1.04%) | 151.3:1 | >99.9% | 100.0% | 0.00% |
| 660 and above | 38 | <0.1% | 0.00% (0.00–9.18%) | no bads | 100.0% | 100.0% | none left |

Good:bad odds roughly double every 20 points from 540 to 640 (6.5:1 to 97.5:1), as the points scale is built to show; the two edge bands (25 and 38 loans) should not be read on their own. The cut-off is set per product (Table 4.1) because the break-even odds differ (3:1, 6:1, 12:1); this pooled table shows how steeply risk falls with score.

## 5. Question 1: is there room on the current cut-off?

Status quo: today's policy, which approved every booked loan (bad rate 4.41%; a 0.5 PD cut-off lands in the same place). Tightening means declining part of today's book; loosening means approving applicants today's policy rejects.

### 5.1 Tightening today's book

**Table 5.1 · What the cost-based rule would decline from today's book** (`room_swap_challenger.parquet`, `room_swap_champion.parquet`; the swap-in and declined-by-both cells are empty because the status quo approves everyone)

| | Challenger, cost-based rule | Champion, cost-based rule |
|---|---|---|
| Kept (approved by both) | 202,054 loans, bad rate 3.17% (3.09–3.25%) | 205,986 loans, bad rate 3.57% (3.49–3.65%) |
| Declined (swap-outs) | 20,627 loans (9.3%), 6,876 a month | 16,695 loans (7.5%), 5,565 a month |
| Bads among the declined | 3,426 | 2,484 |
| Bad rate of the declined (95% CI) | **16.61% (16.11–17.12%)** | **14.88% (14.35–15.43%)** |
| Loan amount declined | 1,062.4M CU | 636.9M CU |
| Credit loss avoided | 139.2M CU | 74.6M CU |
| Margin forgone on declined good loans | 46.9M CU | 28.6M CU |
| **Net gain over the quarter** (95% bootstrap interval) | **+92.3M CU** (86.0M to 98.7M) | **+45.9M CU** |
| Approval rate (share of booked loans) | 100% → 90.7% | 100% → 92.5% |
| Book bad rate | 4.41% → **3.17%** | 4.41% → **3.57%** |

There is room to tighten, and it is fully observable because these loans were booked: the challenger's tail defaults at 16.61%, 3.8 times the book, and declining it is worth 92.3M CU a quarter, about twice the champion's 45.9M CU (23% less total cost of wrong decisions and 35% less credit loss than today's policy, Table 3.3). The 92.3M CU is uncertain in two ways: sampling (95% bootstrap interval 86.0M to 98.7M CU) and assumptions (56.6M to 147.7M CU across the margin range, Table 2.3); by month it was 29.4M, 37.0M and 25.8M CU. The price is 9.3 pp of approval rate, the opposite of what the business asked for; Sections 5.2 and 6 show how that room can be spent.

### 5.2 Loosening: how far the room stretches (headroom)

Decline d tail loans with bad rate t from a book with bad rate B, then approve s new applicants with bad rate r. The book's bad rate stays where it is when:

```text
new approvals per declined tail loan   s ÷ d = (t − B) ÷ (r − B)        (r above B)
net change in approvals                s − d = d × (t − r) ÷ (r − B)
```

With the challenger's rule: B = 4.41% (today's book), t = 16.61% (the 20,627 loans the rule declines), d = 20,627. r, the bad rate of the newly approved applicants, is not in the data.

**Table 5.2 · Exchange rate at an unchanged book bad rate, for a range of r** (`headroom_points.parquet`; volumes are booked-loan volumes)

| Bad rate of the new approvals (r) | r ÷ today's book bad rate | New approvals per declined tail loan | New approvals the room pays for (quarter) | Net change in approvals (quarter) | Net change a month |
|---|---|---|---|---|---|
| 8.83% | 2.00× | 2.8 | 56,991 | +36,364 | +12,121 |
| 12.46% | 2.82× (= 0.75 × the tail: the below-cut-off test's pass threshold) | 1.5 | 31,276 | +10,649 | +3,550 |
| 13.24% | 3.00× | 1.4 | 28,495 | +7,868 | +2,623 |
| 16.61% | 3.76× (= the tail) | 1.0 | 20,627 | 0 | 0 |

**In plain English.** Read each row as: if the applicants we start approving default at r, every risky loan we stop approving makes room for this many of them while the book's bad rate stays at today's 4.41%. If they default at 8.83% (twice the book), each declined tail loan pays for 2.8 new approvals; at 12.46%, the bad rate the below-cut-off test in Section 9 is sized to detect, 1.5, about 10,600 more approvals a quarter; if they default like the tail (16.61%), it is one for one and approvals cannot rise, and above that loosening pushes the bad rate up. Three limits: the table holds the bad rate constant, not profit; the top rows are upper bounds, because the volume is capped by how many applicants the lender rejects today (through-the-door volume), which this data does not show; and r is unknown, because the applicants the lender rejected were never booked. Section 9 sizes the test that measures it.

## 6. Question 2: champion vs challenger

Status quo: the champion applying the cost-based rule (205,986 loans approved, 92.5%; bad rate 3.57%; credit loss 318.7M CU; net profit 945.5M CU). The champion is a rebuilt scorecard, so every uplift in this section is against a rebuilt scorecard applying the same cost-based rule, not against today's book (Section 5) and not against the lender's own incumbent. Both swap groups were booked by the historical policy, so the bad rates of swap-ins and swap-outs below are observed, unlike the loosening case in 5.2.

**Headline (out-of-time test, Jan to Mar 2020).** At the champion's bad rate (3.57%), the challenger approves 95.8% instead of 92.5%: **+3.3 pp (95% bootstrap interval 2.9 to 3.6 pp), about 2,458 more booked loans a month**. At the champion's approval rate (92.5%), its credit losses are **22% lower (20% to 23% lower)**, −68.9M CU a quarter. Under the recommended policy (each model on its own cost-based rule), swap-outs default at 14.70% and swap-ins at 7.08%, a gap of 7.6 pp (6.6 to 8.6 pp).

**Where the gap between the models comes from** (`champion_checks.parquet`). On the test quarter the champion scores Gini 0.462, LightGBM on the scorecard's own 16 inputs 0.489 and the challenger on all 90 inputs 0.578: of the 11.6-point gap, 2.7 points come from the algorithm and 8.9 from more inputs. Refitting the scorecard closes little of it: lifting the 18-variable cap (23 variables, same IV, correlation and sign rules) gives 0.490, 2.8 points or 24% of the gap, and empirical WOE for missing values gives 0.464 (+0.2 points).

**Table 6.1 · Three ways to use the challenger, against the champion's cost-based rule** (from the three swap tables below; ties out to `reports/metrics.json` `model_value`)

| Policy | Approval rate | Bad rate of approved | Swap-ins | Swap-outs | Credit loss | Net profit | Credit loss vs status quo | Net profit vs status quo |
|---|---|---|---|---|---|---|---|---|
| Status quo: champion, cost-based rule | 92.5% | 3.57% | 0 | 0 | 318.7M | 945.5M | reference | reference |
| Challenger at the same approval rate | 92.5% (unchanged) | 3.22% | 7,786 | 7,786 | 249.8M | 963.9M | −68.9M (−21.6%) | +18.4M |
| Challenger at the same bad rate | 95.8% (+3.3 pp) | 3.57% | 10,836 | 3,462 | 288.3M | 966.2M | −30.4M (−9.5%) | +20.8M |
| Challenger at its own cost-based rule (recommended) | 90.7% (−1.8 pp) | 3.17% | 4,776 | 8,708 | 254.1M | 991.8M | −64.6M (−20.3%) | +46.3M |

The business's goal, more approvals at a flat bad rate, is reachable with the challenger, but under these margins it earns less than half of what the challenger's own rule earns (+20.8M vs +46.3M CU a quarter). The equal-bad-rate policy is one PD cut-off of 14.9% for every product: it approves 12,386 loans whose PD is above their product's break-even (12,305 of them point-of-sale), which lose money in expectation, and declines 1,080 cash loans the rule would approve; the recommended policy approves 1.8 pp fewer than the champion's rule and cuts the bad rate to 3.17%.

In the 2x2 tables below, rows are the champion's decision under its cost-based rule and columns the challenger's decision. Shares are of all 222,681 test loans. **Loan amount** is the total amount of the cell's loans. **Credit loss if approved** is 60% of the amount of the cell's loans that defaulted. **Net value if approved** is the margin the cell's good loans would earn minus that credit loss: what approving the whole cell is worth. The change in net profit equals the net value of the swap-ins minus the net value of the swap-outs.

**Table 6.2 · Challenger at the same approval rate (92.5%)** (`swap_the_same_approval_rate.parquet`)

| Champion's rule ↓ · Challenger → | Challenger approves | Challenger declines |
|---|---|---|
| **Champion approves** | **Approved by both**<br>198,200 loans (89.0%)<br>bad rate 3.02% (2.95–3.10%)<br>loan amount 10,582.9M CU<br>credit loss if approved 236.8M CU<br>net value if approved +965.1M CU | **Swap-out (approved → declined)**<br>7,786 loans (3.5%)<br>bad rate 17.42% (16.59–18.27%)<br>loan amount 649.7M CU<br>credit loss if approved 81.9M CU<br>net value if approved −19.6M CU |
| **Champion declines** | **Swap-in (declined → approved)**<br>7,786 loans (3.5%)<br>bad rate 8.19% (7.61–8.82%)<br>loan amount 241.0M CU<br>credit loss if approved 13.0M CU<br>net value if approved −1.2M CU | **Declined by both**<br>8,909 loans (4.0%)<br>bad rate 20.72% (19.89–21.57%)<br>loan amount 395.9M CU<br>credit loss if approved 61.6M CU<br>net value if approved −44.8M CU |

Net effect: approvals unchanged (205,986); bad rate of approved 3.57% → 3.22%; credit loss −68.9M CU (−21.6%); net profit +18.4M CU. Same volume, better selection: 7,786 loans that default at 17.42% swap out for the same number that default at 8.19%; the swap-ins are still slightly loss-making (−1.2M CU) because holding the approval rate at 92.5% means a single PD cut-off of 11.1%, and 3,248 of the swap-ins are point-of-sale loans above the 7.7% break-even.

**Table 6.3 · Challenger at the same bad rate (3.57%)** (`swap_the_same_bad_rate.parquet`)

| Champion's rule ↓ · Challenger → | Challenger approves | Challenger declines |
|---|---|---|
| **Champion approves** | **Approved by both**<br>202,524 loans (90.9%)<br>bad rate 3.24% (3.16–3.32%)<br>loan amount 10,905.2M CU<br>credit loss if approved 265.9M CU<br>net value if approved +971.6M CU | **Swap-out (approved → declined)**<br>3,462 loans (1.6%)<br>bad rate 22.56% (21.20–23.98%)<br>loan amount 327.4M CU<br>credit loss if approved 52.8M CU<br>net value if approved −26.2M CU |
| **Champion declines** | **Swap-in (declined → approved)**<br>10,836 loans (4.9%)<br>bad rate 9.63% (9.08–10.20%)<br>loan amount 347.6M CU<br>credit loss if approved 22.4M CU<br>net value if approved −5.4M CU | **Declined by both**<br>5,859 loans (2.6%)<br>bad rate 24.59% (23.51–25.71%)<br>loan amount 289.3M CU<br>credit loss if approved 52.2M CU<br>net value if approved −40.6M CU |

Net effect: approvals +7,374 (+3.3 pp, 2,458 a month); bad rate of approved unchanged at 3.57%; credit loss −30.4M CU (−9.5%); net profit +20.8M CU. This is the business's request met: 10,836 applicants swap in at 9.63% and 3,462 swap out at 22.56%, so approvals rise and the bad rate does not.

**Table 6.4 · Challenger at its own cost-based rule (recommended)** (`swap_its_own_costbased_rule.parquet`)

| Champion's rule ↓ · Challenger → | Challenger approves | Challenger declines |
|---|---|---|
| **Champion approves** | **Approved by both**<br>197,278 loans (88.6%)<br>bad rate 3.07% (3.00–3.15%)<br>loan amount 10,656.6M CU<br>credit loss if approved 247.2M CU<br>net value if approved +989.9M CU | **Swap-out (approved → declined)**<br>8,708 loans (3.9%)<br>bad rate 14.70% (13.97–15.46%)<br>loan amount 576.0M CU<br>credit loss if approved 71.5M CU<br>net value if approved −44.4M CU |
| **Champion declines** | **Swap-in (declined → approved)**<br>4,776 loans (2.1%)<br>bad rate 7.08% (6.38–7.84%)<br>loan amount 150.4M CU<br>credit loss if approved 6.9M CU<br>net value if approved +1.9M CU | **Declined by both**<br>11,919 loans (5.4%)<br>bad rate 18.00% (17.33–18.70%)<br>loan amount 486.5M CU<br>credit loss if approved 67.6M CU<br>net value if approved −47.9M CU |

Net effect: approvals −3,932 (−1.8 pp); bad rate of approved 3.57% → 3.17%; credit loss −64.6M CU (−20.3%); net profit +46.3M CU. Swap-outs default 2.1 times as often as swap-ins (14.70% vs 7.08%; a gap of 7.6 pp, 95% bootstrap interval 6.6 to 8.6 pp) and are larger loans: declining them is worth 44.4M CU, and approving the swap-ins adds 1.9M CU.

### 6.5 Who swaps in and who swaps out (recommended policy)

**Table 6.5 · Profile of each cell** (`swap_profile.parquet`; revolving share and the new-to-lender counts recomputed from `predictions_test.parquet`)

| | Approved by both | Swap-in | Swap-out | Declined by both |
|---|---|---|---|---|
| Loans (quarter) | 197,278 | 4,776 | 8,708 | 11,919 |
| Loans a month | 65,759 | 1,592 | 2,903 | 3,973 |
| Observed bad rate | 3.07% | 7.08% | 14.70% | 18.00% |
| Mean PD, champion | 2.91% | 11.75% | 5.59% | 13.61% |
| Mean PD, challenger | 2.72% | 6.02% | 13.42% | 17.00% |
| Median loan amount | 38,796 CU | 23,018 CU | 41,620 CU | 26,436 CU |
| Cash loans | 27.8% | 4.1% | 1.7% | 0.5% |
| Point-of-sale loans | 56.3% | 89.9% | 90.0% | 96.9% |
| Revolving (card) | 15.9% | 6.0% | 8.3% | 2.7% |
| New to the lender | 19.4% | 0.0% | 9.0% | 0.0% |

Both swap groups are about 90% point-of-sale, and swap-ins are smaller loans than swap-outs (median 23,018 vs 41,620 CU). The challenger's PDs are closer to what happened in both groups: swap-ins 6.02% predicted vs 7.08% observed (champion 11.75%), swap-outs 13.42% vs 14.70% (champion 5.59%). Every swap-in is an existing client: the champion declines no new-to-lender applicant in the test quarter (its highest PD for a new client is 7.57%, just under the 7.69% point-of-sale break-even), while the challenger declines 781 of them, all swap-outs (17.6% of the test quarter is new to the lender).

## 7. Three tiers: volumes, costs and capacity

Each application goes to the action with the highest expected value: auto-approve, decline, or manual review. A review costs 300 CU, and a reviewer is assumed to decline 40% of the bad applicants (the reviewer catch rate) and 10% of the good ones ([assumptions log](assumptions.md), R1 to R4). Reviews are capped at 5% of applications (3,711 a month on booked-loan volume; the queue itself is set on through-the-door volume, larger by the share the lender rejects today), keeping the most valuable first. Review outcomes are expected values, not observed decisions.

**Table 7.1 · Volumes by tier, challenger** (`tiers.parquet`)

| Tier | Loans (quarter) | Share | Loans a month | Bads | Bad rate (95% CI) | Median amount |
|---|---|---|---|---|---|---|
| Auto-approve | 192,817 | 86.6% | 64,272 | 5,344 | 2.77% (2.70–2.85%) | 35,792 CU |
| Manual review | 11,134 | 5.0% | 3,711 | 1,360 | 12.21% (11.62–12.84%) | 96,955 CU |
| Decline | 18,730 | 8.4% | 6,243 | 3,125 | 16.68% (16.16–17.23%) | 28,000 CU |
| Total | 222,681 | 100% | 74,227 | 9,829 | 4.41% | |

**Table 7.2 · Money by tier vs the two-tier rule** (`tiers.parquet`, `reports/metrics.json` `three_tier`; money in CU over the quarter)

| Tier | Approved (expected) | Bads approved (expected) | Margin earned | Credit loss | Forgone margin | Review cost | Net profit |
|---|---|---|---|---|---|---|---|
| Auto-approve | 192,817 | 5,344 | 1,146.7M | 184.7M | 0 | 0 | 962.0M |
| Manual review | 9,613 | 816 | 98.8M | 53.9M | 11.0M | 3.3M | 41.6M |
| Decline | 0 | 0 | 0 | 0 | 36.4M | 0 | 0 |
| **Three-tier total** | 202,430 (90.9%) | 6,160 (3.04%) | 1,245.5M | 238.6M | 47.3M | 3.3M | **1,003.6M** |
| Two-tier (challenger, cost-based rule) | 202,054 (90.7%) | 6,403 (3.17%) | 1,245.9M | 254.1M | 46.9M | 0 | 991.8M |

The review tier takes 5.0% of applications (3,711 a month, all of the assumed capacity) and adds 11.8M CU a quarter over the two-tier rule, if reviewers decline 40% of the bad applicants they see. Reviewed applications are large (median 96,955 CU) and default at 12.21% (the review hit rate), between the auto-approve and decline tiers; with the 40% catch rate that is 4.9% bads stopped per review (544 of 11,134).

**Table 7.3 · Tiers by product** (`tier_by_product.parquet`; PD = challenger calibrated PD)

| Product | Tier | Loans (quarter) | Share of product | Bad rate (95% CI) | PD range | Smallest loan | Median loan |
|---|---|---|---|---|---|---|---|
| Cash loan | Auto-approve | 51,879 | 93.8% | 4.44% (4.27–4.62%) | 0.10% to 24.81% | 2,000 CU | 60,000 CU |
| Cash loan | Manual review | 3,377 | 6.1% | 15.78% (14.59–17.05%) | 8.08% to 32.20% | 15,000 CU | 100,000 CU |
| Cash loan | Decline | 74 | 0.1% | 33.78% (24.05–45.12%) | 25.59% to 57.19% | 5,328 CU | 69,432 CU |
| Revolving (card) | Auto-approve | 29,276 | 89.6% | 2.30% (2.13–2.47%) | 0.06% to 14.27% | 2,000 CU | 51,355 CU |
| Revolving (card) | Manual review | 2,710 | 8.3% | 12.62% (11.42–13.92%) | 4.66% to 19.09% | 18,935 CU | 100,000 CU |
| Revolving (card) | Decline | 670 | 2.1% | 23.13% (20.10–26.48%) | 14.33% to 56.75% | 2,000 CU | 68,411 CU |
| Point-of-sale loan | Auto-approve | 111,662 | 82.9% | 2.12% (2.04–2.21%) | 0.05% to 7.69% | 2,055 CU | 26,160 CU |
| Point-of-sale loan | Manual review | 5,047 | 3.7% | 9.61% (8.83–10.45%) | 2.76% to 10.70% | 35,900 CU | 79,998 CU |
| Point-of-sale loan | Decline | 17,986 | 13.4% | 16.37% (15.84–16.92%) | 7.69% to 62.12% | 2,000 CU | 27,800 CU |

Review is amount-aware: a 300 CU review can pay for itself only on loans of at least 6,667 CU (cash), 11,667 CU (revolving) and 21,667 CU (point-of-sale), and because capacity keeps the most valuable cases, the smallest loans actually reviewed are larger (15,000, 18,935 and 35,900 CU); that is also why PD ranges overlap between tiers. Point-of-sale holds 96.0% of all declines, and the 74 declined cash loans are a small cell (see the interval).

**Table 7.4 · Value of the review tier vs the two-tier rule, by reviewer effectiveness** (`review_grid.parquet`; extra net profit in CU over the quarter, with the share of applications sent to review in brackets)

| Reviewer catch rate (share of bad applicants the reviewer declines) | Reviewer declines 5% of goods | Reviewer declines 10% of goods | Reviewer declines 15% of goods | Reviewer declines 20% of goods |
|---|---|---|---|---|
| 20% | +4.2M (3.6%) | +1.8M (1.0%) | +0.04M (0.1%) | no reviews |
| 30% | +12.6M (5.0%) | +4.2M (3.9%) | +2.4M (1.7%) | +1.1M (0.6%) |
| 40% | +21.8M (5.0%) | **+11.8M (5.0%)** | +5.8M (4.6%) | +3.3M (2.6%) |
| 50% | +31.7M (5.0%) | +22.0M (5.0%) | +12.9M (5.0%) | +7.4M (5.0%) |
| 60% | +42.4M (5.0%) | +31.7M (5.0%) | +22.4M (5.0%) | +14.8M (5.0%) |

At the assumed 40% / 10% (bold) the tier adds 11.8M CU a quarter. With the same 10% of goods declined, a reviewer who catches only 20% of bads leaves few applications worth reviewing (1.0%) and adds 1.8M CU, while one who catches 60% adds 31.7M CU. The catch rate is not in the data, so review outcomes must be logged before the tier is scaled.

**Table 7.5 · Capacity** (`reports/metrics.json` `three_tier`)

| Item | Value |
|---|---|
| Review capacity (5% of applications) | 3,711 a month |
| Applications where a review pays, before the cap | 5,988 a month |
| Reviews routed | 3,711 a month (100% of capacity) |
| Review cost | 3.3M CU a quarter (11,134 reviews × 300 CU) |
| Smallest loan where a review can pay | cash 6,667 CU · revolving 11,667 CU · point-of-sale 21,667 CU |

Capacity binds: 5,988 applications a month would be worth reviewing against a capacity of 3,711. Underwriting Operations should confirm the 5% capacity and the 300 CU cost per case; extra capacity would be used, but each extra review is worth less than the ones already kept.

## 8. Recommended cut-off policy

**The rule.** For each application, take the challenger's calibrated PD p, the loan amount A and the product margin m (cash 20%, revolving 10%, point-of-sale 5%); the loss on a bad loan is L = 60% of A.

1. **Manual review** if the expected value of a review, A × [(1 − p) × (1 − g) × m − p × (1 − c) × L] − C, is higher than both approving and declining, where c = 40% (share of bad applicants the reviewer declines), g = 10% (share of good applicants declined anyway) and C = 300 CU. This happens only near the break-even and only for larger loans. Keep the most valuable reviews, up to 5% of applications (3,711 a month).
2. Otherwise **auto-approve** when p is below the product's break-even PD: **cash 25.0%, revolving 14.3%, point-of-sale 7.7%**.
3. Otherwise **decline**, with the model's main decline reasons recorded.

If Model Risk has not yet approved the challenger, run the same rule on the champion in points (Table 4.1): approve cash loans above 524, revolving above 544 and point-of-sale above 564 points. On its own that is worth 45.9M CU a quarter against today's book (Table 5.1). The challenger itself goes live through the champion/challenger test in Section 9.

**Where the cut-off sits in the decision flow.** The rule applies after the lender's policy (knock-out) rules: an application that fails a policy rule is declined before it is scored, so in production the rule's approval rate is a share of applicants that reach the score (in this pack, of previously approved applicants). Overrides of the rule are allowed only with a logged reason and a named owner, capped (for example at 5% of decisions) and monitored: the override rate, and the bad rate of overridden approvals against model-approved loans (Table 8.3).

**Table 8.1 · The rule by product, as expected on the test quarter** (`tier_by_product.parquet`, `rule_by_product.parquet`)

| Product | Auto-approve when challenger PD is below | Champion fallback: approve above | Auto-approve | Manual review | Decline | Two-tier approval rate | Two-tier bad rate of approved |
|---|---|---|---|---|---|---|---|
| Cash loan | 25.0% | 524 points | 93.8% | 6.1% | 0.1% | 99.6% | 5.09% |
| Revolving (card) | 14.3% | 544 points | 89.6% | 8.3% | 2.1% | 96.8% | 2.94% |
| Point-of-sale loan | 7.7% | 564 points | 82.9% | 3.7% | 13.4% | 85.6% | 2.31% |
| All products | | | 86.6% | 5.0% | 8.4% | 90.7% | 3.17% |

Point-of-sale takes the declines (13.4% of its applications) and revolving the largest review share (8.3%); cash loans are almost all approved or reviewed (0.1% declined).

**Table 8.2 · How sensitive the rule is to the PD level** (`calibration_drift.parquet`; challenger, two-tier rule)

| PD view | Mean PD | Calibration ratio (mean PD ÷ bad rate) | Approval rate | Bad rate of approved | Net profit |
|---|---|---|---|---|---|
| As calibrated on Nov-Dec 2019 | 3.97% | 0.90 | 90.7% | 3.17% | 991.8M CU |
| Hindsight: intercept refitted on the test quarter (level only) | 4.41% | 1.00 | 89.3% | 3.08% | 993.2M CU |
| Stress: PD odds +25% before applying the rule | 4.84% | 1.10 | 87.9% | 2.99% | 994.0M CU |

The test quarter defaulted more than the calibration window, so PDs ran about 10% low (calibration ratio 0.90), but the calibration slope is 0.99: the spread of risk is right and only the level moved (intercept shift +0.12 in log-odds). Under the stress view the rule approves 2.9 pp fewer and net profit moves by +0.2%, so the policy holds under a calibration error of this size; recalibrate on the latest mature vintage before go-live.

**Table 8.3 · What to watch** (thresholds from the monitoring plan in notebook 04, section 10, and [metric definitions](02_metric_definitions.md); expected levels from this pack)

| Metric | Expected level | Frequency | Investigate | Act | Owner |
|---|---|---|---|---|---|
| Approval rate under the rule | 90.7% of previously approved applicants (test months 90.2% to 91.0%); re-set the plan on through-the-door applications in the first month | weekly | ± 3 pp vs plan | ± 5 pp | Credit policy |
| Calibration ratio, mature vintages | 0.90 on the test quarter | monthly | outside 0.8 to 1.25 | two months in a row | Model validation |
| Early delinquency (30+ days past due at month 3) vs the level expected from the PDs | not in this dataset; set at go-live | monthly | +20% | +40% | Risk analytics |
| Score PSI vs the development sample | at most 0.008 in the test quarter (challenger); 0.08 at its back-test peak, while the scorecard's reached 0.15 | monthly | ≥ 0.10 | ≥ 0.25 | Risk analytics |
| Feature CSI: the 12 most influential inputs, every categorical input and every input that already shifted between training and test (22 inputs) | in the test quarter, above 0.10 for loan term in 2020-01 (0.12), the five credit-bureau enquiry inputs (0.14 to 0.18 in 2020-02 and 2020-03) and the reason for the last rejection (0.18 and 0.20); the other inputs below 0.10 | monthly | ≥ 0.10 | ≥ 0.25 | Risk analytics |
| Gini, mature vintages | 0.578 on the test quarter (validation 0.582) | quarterly | 5 points below validation | 10 points below | Model validation |
| Reviewer catch rate (1 − bads among review approvals ÷ bads expected in the reviewed pool) | 40% assumed; with a review hit rate of 12.2% that stops 4.9% bads per review (544 of 11,134 reviews a quarter) | monthly, as outcomes mature | below 30% (25% under the assumption) | no separate act level | Underwriting operations |
| Override rate and override bad rate | not modelled in this pack | monthly | > 5% of decisions | override bad rate above model-approved | Credit policy |

The April to October 2020 back-test is the reason for the outcome rows: the challenger's score PSI stayed below 0.10 (peak 0.08) and the approval rate under the rule stayed between 91.3% and 92.7%, while the bad rate dropped in one step in April 2020 (to 1.96% to 2.45% a month) and then stayed flat, and predicted PDs ran up to 66% above actual. The scorecard's PSI did move (0.108 to 0.146 from May 2020), in step with the employment field's fill-rate collapse (employment-years CSI 0.86). A stable score distribution and a stable approval rate do not mean stable risk; calibration and early delinquency do the catching. The back-test is illustrative, because the cause of the drop is not known (Section 10). It is also not blind: two employment fields (`empl_industry_691L`, `empl_employedtotal_800L`) were dropped in notebook 02 partly because their collection stopped in June 2020, inside the back-test window, and the six inputs that had already shifted between training and test (PSI above 0.10 in notebook 02: the reason for the last rejection and five credit-bureau enquiry inputs) were put on the CSI list with that knowledge.

On the inputs, counting only the 12 months after the training window (`csi_flags.parquet`): 12 of the 22 monitored inputs crossed 0.10 at least once, including all six already-shifted inputs. Employment years was above 0.10 in every month from 2020-04 (peak 0.86 in 2020-05), a data-capture break that CSI caught at once; loan term crossed it in 7 months (peak 0.23 in 2019-11); the five credit-bureau enquiry inputs in 9 to 10 months from 2019-12 or 2020-02 (peak 0.37). The reason for the last rejection, a categorical input, was above 0.10 in all 9 months from 2020-02 (peak 0.24 in 2020-07): a data-definition drift, as new reject codes (from February 2019) replace old ones.

## 9. Tests needed before scaling

**Table 9.1 · Test sizes** (`test_sizes.parquet`, `reports/metrics.json` `test_design`; two-sided 5% test, 80% power; the champion/challenger arms are 1:4, sized with the unequal-allocation formula of Fleiss, Levin & Paik)

| Test | Question | Design | Size | Cost and time |
|---|---|---|---|---|
| Below-cut-off test | Do applicants just below today's approval line (applicants the current policy rejects) default at 25% less than the declined tail (16.61% vs 12.46%)? | Approve a random sample of applicants that today's policy rejects, just below its approval line (not below the new line), with capped amounts | **589 approved test loans** | Expected net loss about 4,474 CU a loan, so a price of information of about 2.6M CU; both are floors (see below). Duration depends on today's through-the-door reject volume, which is not in this data. |
| Champion / challenger | Is the challenger's approved-book bad rate lower (3.57% vs 3.17%)? | Random assignment at application, 20% of traffic on the challenger, stratified by product; decision rule signed before the start (Table 9.2) | **20,544 approved loans in the challenger arm and 82,176 in the champion arm** | About 1.5 months of the test quarter's booked-loan volume (re-set on through-the-door volume at the start), then the outcome window; 30+ days past due at month 3 gives an early read |

The below-cut-off test is the only way to learn r in Table 5.2. What a pass buys (`reports/metrics.json` `test_pass`): if the test loans default at 12.46% or less (25% below the tail's 16.61%), each declined tail loan funds about 1.5 new approvals, about 10,600 more loans a quarter at an unchanged book bad rate; a fail means the room in Section 5.1 is spent on a lower bad rate, not on volume. Its cost per loan, 4,474 CU, is the average net loss of the declined tail (92.3M CU ÷ 20,627 loans; net of the margin the test loans that repay will earn), so 2.6M CU is a floor: the sample is drawn from applicants today's policy rejects, who are probably riskier than the declined tail.

**Table 9.2 · Pre-registered decision rule for the champion/challenger test** (a proposal for the committee; sample from Table 9.1, stop thresholds from Table 8.3 and the four-fifths screen; signed before the first application is assigned and not changed once the test starts)

| Item | Rule |
|---|---|
| Primary metric | Bad rate of the approved book in each arm. Early read: share 30+ days past due at month 3 on book. Final read: the default flag once the outcome window has passed. |
| Comparison and margin | Adopt the challenger only if (1) its arm's bad rate is not worse than the champion arm's by more than a tolerance of **0.2 pp (a proposal, to be agreed before launch)**, i.e. the upper end of the 95% interval for challenger minus champion is below +0.2 pp, and (2) its net profit per application, on the cost matrix Finance signs off, is higher. Otherwise the champion stays. The expected difference is 0.40 pp in the challenger's favour (3.17% vs 3.57%, Table 6.1); the Table 9.1 sample, sized to detect it, is more than this comparison needs. |
| Minimum sample | 20,544 approved loans in the challenger arm and 82,176 in the champion arm, about 1.5 months of booked-loan volume. No final read before both are reached and the outcome window has passed. |
| Stop rules (any one; checked monthly, the approval rate weekly) | Challenger score PSI at or above 0.25; approval-rate ratio below 0.80 for any sex or age-band group in the challenger arm; challenger-arm approval rate more than 5 pp above or below plan; early delinquency 40% or more above the level expected from the PDs. A stop pauses the challenger arm and goes to Model Risk. The early read can stop the test for harm, not end it early for success. |
| Who signs | Model Risk / Validation, Credit Policy and Compliance: the rule before launch, the result after the final read. |

**Table 9.3 · Other checks before scaling**

| Check | Why | Owner |
|---|---|---|
| Log review outcomes (bads declined, goods declined, cost per case) for the first months | The review tier's value moves from +1.8M to +31.7M CU a quarter across the reviewer catch rates in Table 7.4 | Underwriting operations |
| Sign off the margins, LGD and EAD | The break-evens and the share declined move most with the margins (Tables 2.2, 2.3) | Finance |
| Recalibrate the challenger on the latest mature vintage | Test-quarter PDs ran about 10% low (Table 8.2) | Model validation |
| Review the age and sex results and the decline-reason library | The model under-predicts risk for men (calibration ratio 0.73) and 18-24s (0.73); Section 10 | Compliance |

## 10. Caveats

- **Selection bias.** Every loan in the data was approved by the historical policy. Approval rates are shares of previously approved applicants, and the bad rate of past rejects is unknown. Tightening results (Section 5.1) and swap sets (Section 6) are observed on booked loans; loosening (Section 5.2) is a formula until the below-cut-off test reports.
- **Assumptions drive the money.** Margins, LGD, EAD, the reviewer catch rate, the review cost and the review capacity are assumptions ([assumptions log](assumptions.md)). The cost-based rule beats today's policy in all three margin scenarios (Table 2.3), but the CU amounts move with them. The champion is a rebuilt scorecard: the +3.3 pp and the 22% lower credit losses are against that scorecard applying the same rule, and if the lender's own incumbent is stronger, the challenger's uplift is overstated.
- **Calibration.** PDs were calibrated on a 3.51% window and tested on a 4.41% quarter; they ran about 10% low (Table 8.2).
- **A quarter before the April 2020 break.** The cut-offs are set on January to March 2020. In April 2020 the bad rate dropped in one step, to 1.96% to 2.45% a month, then stayed flat; volume fell by about 86% that month (60,748 loans in March, 8,289 in April) and was back to March's level by September (61,905; October 2020 covers 1 to 5 October only). The drop may reflect COVID-era measures, the lender's own tightening or loans too recent to have defaulted (the outcome horizon is not disclosed); the data cannot separate these, so the Section 8 back-test is illustrative and a cut-off change should wait for mature vintages.
- **Target and currency.** The default definition and horizon are Home Credit's and are not disclosed; vintages up to March 2020 are treated as mature. Amounts are in undisclosed currency units.
- **Volumes.** "A month" figures (3,711 reviews, about 2,458 extra approvals, the months the tests need) are booked loans per month in the test quarter (74,227), not through-the-door applications; the production review queue and test durations are set on through-the-door volume, larger by the share the lender rejects today. Review outcomes are expected values, not observed decisions.
- **Fair lending.** Under the recommended policy approval rates are 90.8% for women and 90.6% for men; the lowest age-band ratio is 0.89 (18-24, who default at 7.57%), above the 0.80 screen. The model under-predicts the risk of men (calibration ratio 0.73) and of 18-24s (0.73). The screen is a trigger for review, not a legal conclusion.
- **Small cells.** The two edge score bands (Table 4.2, 25 and 38 loans) and the declined cash loans (Table 4.1, 248 loans; Table 7.3, 74 loans) carry wide intervals.
- **Associations, not causes.** Swap profiles and segment differences describe who moves and how risk is distributed in approved loans; they do not say why.
