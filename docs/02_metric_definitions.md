# 02 · Metric definitions

Written before the analysis so that every number in the repo has one meaning. Code: `src/metrics.py`, `src/economics.py`, `src/strategy.py`.

## Grain and population

| Term | Definition |
|---|---|
| **Application / case** | One row of `train_base` (`case_id`). Every case in the data is a **booked loan** (it has an outcome). |
| **Evaluation population** | Cases in a given time window. Headline numbers use the **out-of-time test window: decisions dated 2020-01-01 to 2020-03-31** (MONTH 202001 to 202003). |
| **Decision month / vintage** | `MONTH` of `date_decision` (YYYYMM). A vintage is all loans booked in the same month. |
| **Loan amount** | `credamount_770A`: loan amount or card limit at origination, local currency units (CU). |
| **Bad (default)** | `target = 1` as supplied by Home Credit. The exact delinquency definition and outcome horizon are not disclosed; we treat it as "the loan defaulted". **Good** = `target = 0`. |

## Policy metrics (the ones the business sees)

A *policy* is a rule that maps each application to approve / review / decline, e.g. "approve if PD < 8%".

| Metric | Formula | Notes |
|---|---|---|
| **Approval rate** | approved ÷ applications in the population | Simulated on booked loans: the share of *historically approved* applicants the policy would approve. Not the company's through-the-door approval rate. |
| **Decline rate** | 1 − approval rate (two-tier); declined ÷ applications (three-tier) | |
| **Review rate** | routed to manual review ÷ applications | Three-tier policy only. |
| **Bad rate (approved book)** | bads among approved ÷ approved | The number the business means by "坏账率". Count-based. |
| **Bad rate (population)** | bads ÷ applications | Base rate; 3.14% over all 1.53M cases. |
| **Capture rate** | bads declined ÷ all bads | Share of defaults the policy keeps off the book (recall on bads). |
| **False positive rate (good-decline rate)** | goods declined ÷ all goods | Share of good customers turned away. |
| **Decline precision** | bads declined ÷ declined | Bad rate inside the declined group. |
| **Review hit rate** | bads among reviewed ÷ reviewed | |

## Money metrics (cost matrix)

All amounts are per loan and scale with the loan amount *A*. Assumption values and sources: `docs/assumptions.md` and `config.yaml`.

| Metric | Formula |
|---|---|
| **Margin of a good loan** (m) | net lifetime profit as a share of A after funding and operating cost. Base case m = 10%. |
| **Loss of a bad loan** (L) | EAD share × LGD. Base case 0.80 × 0.75 = 60% of A. |
| **Cost of a false negative** (approve a bad) | L × A (credit loss) |
| **Cost of a false positive** (decline a good) | m × A (forgone margin) |
| **Credit loss** | Σ over approved bads of L × A |
| **Forgone margin** | Σ over declined goods of m × A |
| **Total decision cost** | credit loss + forgone margin (+ review cost in the three-tier policy). The README "loss curve" plots this. |
| **Net profit** | Σ over approved goods of m × A − credit loss − review cost. Equals (margin of all goods) − total decision cost, so minimising one maximises the other. |
| **Break-even PD** | p* = m ÷ (m + L). Approving a loan with calibrated PD p has expected value A·[(1−p)·m − p·L], which is positive exactly when p < p*. Base case p* = 0.10 ÷ 0.70 = **14.3%**. |
| **Review cost** | reviews × cost per review (base case 300 CU). |

## Model metrics (secondary; used in the model card)

| Metric | Definition |
|---|---|
| **PD** | Model-predicted probability of default. Both models are recalibrated on the validation window (Platt scaling) so that PDs are comparable and usable in the break-even rule. |
| **Scorecard points** | points = 600 + 20/ln(2) · ln(odds ÷ 50), where odds = (1 − PD) ÷ PD (good:bad). Higher points = lower risk; +20 points doubles the good:bad odds (PDO = 20); 600 points = odds of 50:1 (PD ≈ 2%). |
| **AUC / Gini** | Probability a random bad scores riskier than a random good; Gini = 2·AUC − 1. |
| **KS** | Max distance between the cumulative score distributions of bads and goods. |
| **Calibration-in-the-large** | mean predicted PD ÷ observed bad rate (1.00 = perfect). |
| **Calibration by decile** | mean PD vs observed bad rate inside each predicted-PD decile, with 95% Wilson intervals. |
| **Brier score** | mean of (PD − outcome)². |

## Swap set

Two policies are compared on the same applications (e.g. champion at its current cut-off vs challenger at a new cut-off):

| Cell | Definition |
|---|---|
| **Approved by both** | approved under the current and the proposed policy |
| **Swap-in** | declined by the current policy, approved by the proposed policy ("从拒变批") |
| **Swap-out** | approved by the current policy, declined by the proposed policy ("从批变拒") |
| **Declined by both** | declined under both |

Each cell reports count, share, bads, bad rate with 95% CI, loan amount and expected credit loss. A good swap has swap-in bad rate well below swap-out bad rate.

## Stability and monitoring

| Metric | Definition | Thresholds |
|---|---|---|
| **PSI** (population stability index) of the score | Σᵢ (Aᵢ − Eᵢ) · ln(Aᵢ ÷ Eᵢ) over 10 bins set at the **training-window** score deciles; Eᵢ = training share, Aᵢ = share in the month being monitored. | < 0.10 stable · 0.10 to 0.25 investigate · > 0.25 act |
| **CSI** (characteristic stability index) | PSI applied to one input feature (missing values get their own bin). | same |
| **Monthly Gini** | Gini within each decision month. | alert if more than 5 points below the validation Gini |
| **Calibration ratio by month** | mean PD ÷ observed bad rate per month. | alert outside 0.8 to 1.25 |
| **Vintage bad rate** | bads ÷ loans booked in the vintage month. | |
| **Vintage curve** (full definition) | cumulative bad rate of a vintage by months on book (MOB 1, 2, 3, ...). Needs the date of default; **not available in this dataset**, which only has a final default flag, so vintages are compared on their final bad rate. | |

## Fairness

| Metric | Definition | Threshold |
|---|---|---|
| **Approval-rate ratio** (adverse impact ratio) | approval rate of a group ÷ approval rate of the most-approved group | flag < 0.80 (four-fifths screen) |
| **Bad rate among approved by group** | as above, per group | large gaps mean the same cut-off carries different risk by group |
| **Calibration by group** | mean PD ÷ observed bad rate per group | over- or under-prediction for a group |

Groups: sex (`sex_738L`) and age band at decision (from the applicant's birth date `birth_259D`). Both are used **only to test** the policy, never as model inputs.
