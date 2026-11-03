# 02 · Metric definitions

Written before the analysis so that every number in the repo has one meaning; the base-case values quoted below were filled in from the results afterwards. Code: `src/metrics.py`, `src/economics.py`, `src/strategy.py`.

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
| **Bad rate by amount** | loan amount of approved bads ÷ loan amount approved | Shown next to the count-based rate where products differ in size (in this book larger loans default more often, within every product, so the amount-based rate is higher: 5.52% vs 4.41% on the test quarter's booked loans). |
| **Bad rate (population)** | bads ÷ applications | Base rate; 3.14% over all 1.53M cases. |
| **Capture rate** | bads declined ÷ all bads | Share of defaults the policy keeps off the book (recall on bads). |
| **False positive rate (good-decline rate)** | goods declined ÷ all goods | Share of good customers turned away. |
| **Decline precision** | bads declined ÷ declined | Bad rate inside the declined group. |
| **Review hit rate** | bads among reviewed ÷ reviewed | The bad rate of the review queue (12.3% in the base case). |
| **Reviewer catch rate** | share of the bad applicants in review that the reviewer declines | An assumption (40%) until measured. Declined applicants have no outcome, so it is estimated as 1 − bads among review approvals ÷ bads expected in the reviewed pool (from calibrated PDs). |
| **Bads stopped per review** | review hit rate × reviewer catch rate | 4.9% in the base case (about 548 expected defaults stopped across 11,133 reviews in the test quarter). |

## Money metrics (cost matrix)

All amounts are per loan and scale with the loan amount *A*. Assumption values and sources: `docs/assumptions.md` and `config.yaml`.

| Metric | Formula |
|---|---|
| **Margin of a good loan** (m) | net lifetime profit as a share of A after funding and operating cost, **by product**: cash loans 20%, revolving 10%, point-of-sale 5%. |
| **Loss of a bad loan** (L) | EAD share × LGD. Base case 0.80 × 0.75 = 60% of A (all products). |
| **Cost of a false negative** (approve a bad) | L × A (credit loss) |
| **Cost of a false positive** (decline a good) | m × A (forgone margin) |
| **Credit loss** | Σ over approved bads of L × A |
| **Forgone margin** | Σ over declined goods of m × A |
| **Total cost of wrong decisions** | credit loss + forgone margin (+ review cost in the three-tier policy). The loss curve in the README plots it by PD cut-off. |
| **Net profit** | Σ over approved goods of m × A − credit loss − review cost. Equals (margin of all goods) − total cost of wrong decisions, so minimising one maximises the other. |
| **Break-even PD** | p* = m ÷ (m + L). Approving a loan with calibrated PD p has expected value A·[(1−p)·m − p·L], which is positive exactly when p < p*. Base case: cash **25.0%**, revolving **14.3%**, point-of-sale **7.7%**. |
| **Cost-based policy** | approve when expected value > 0, i.e. PD below the loan's product break-even. Compared against today's policy, which approved every booked loan (a 0.5 PD cut-off lands in almost the same place), and against single cut-offs (one PD cut-off for every product). |
| **Review cost** | reviews × cost per review (base case 300 CU). |
| **Expected value of review** | A·[(1−p)·(1−g)·m − p·(1−c)·L] − C, where c = share of bads the reviewer declines, g = share of goods the reviewer declines, C = cost per review. A loan goes to review only when this beats both approving and declining, and only up to the team's capacity (largest gain over the next-best action first; the cap binds in the base case, assumption R4). |

**Intervals.** Rates (bad rates by segment, cut-off, swap-set cell or decile) carry 95% Wilson intervals. Headline money and uplift figures carry a 95% **sampling interval**: the 2.5th to 97.5th percentile over 200 loan-level bootstrap resamples of the test quarter (fixed seed). It covers sampling noise only. The **assumption range** repeats the calculation with every margin at the low and at the high end of its range (`docs/assumptions.md`, E1 and E7). For the gain from tightening (92.3M CU a quarter) they are 86.0M to 98.7M and 56.6M to 147.7M CU.

## Headroom (answering "can approvals go up without the bad rate going up?")

Only approved loans have outcomes, so the bad rate of applicants we would *newly* approve (r) cannot be measured. The policy question is framed as an exchange: decline a tail of *d* current loans whose bad rate is *t*, from a book with bad rate *B*, and use the room to approve *s* new applicants with bad rate *r*.

| Metric | Formula |
|---|---|
| **New approvals per declined loan at a constant bad rate** | s ÷ d = (t − B) ÷ (r − B), for r > B |
| **Net change in approvals** | s − d = d·(t − r) ÷ (r − B): positive only if the newly approved applicants are less risky than the declined tail (r < t) |
| **What decides it** | r, which only a controlled below-cut-off test can measure (see the test design in `docs/cutoff_and_swap_set.md`) |

## Test sizing

Champion/challenger test: two-sided 5% significance and 80% power (z = 1.96 and 0.84, rounded; the sizes below use the unrounded 1.95996 and 0.84162). Below-cut-off test: exact one-sided 2.5% binomial test with at least 80% power. Code in `notebooks/04_threshold_and_strategy.ipynb`, section 11.

| Test | Loans needed |
|---|---|
| **Below-cut-off test**: do applicants just below today's approval line default at r = 0.75·t, against the declined tail's t? | Exact binomial test of r = t against r = 0.75·t (one-sided 2.5%). Exact power saw-tooths as n grows, so n is the smallest size from which the power stays at or above 80% for the next 100 sizes: **610 approved test loans** for 16.6% vs 12.5% (the normal approximation n = [1.96·√(t(1 − t)) + 0.84·√(r(1 − r))]² ÷ (t − r)² gives 589, where the exact power is 78%). The test passes if at most 83 loans default (13.6%), which happens 82% of the time if r = 12.5%. **Price of information** = n × the average net loss of approving one tail loan (4,474 CU), about 2.7M CU on the declined tail's economics; likely more if today's rejects are riskier than the tail. |
| **Champion/challenger test**: is the challenger's approved-book bad rate p₁ below the champion's p₀? | Unequal allocation (Fleiss, Levin & Paik 2003, ch. 4). With k = champion arm ÷ challenger arm and p̄ = (p₁ + k·p₀) ÷ (1 + k), the challenger arm needs n₁ = [1.96·√(p̄(1 − p̄)(1 + 1/k)) + 0.84·√(p₁(1 − p₁) + p₀(1 − p₀)/k)]² ÷ (p₀ − p₁)² approved loans and the champion arm k·n₁ (k = 1 is the even split). With 20% of traffic on the challenger, k = 4: 20,544 and 82,176 approved loans for 3.17% vs 3.57%, about 1.5 months of booked-loan volume (the slower arm sets the duration). |

## Model metrics (secondary; used in the model card)

| Metric | Definition |
|---|---|
| **PD** | Model-predicted probability of default. Both models are recalibrated on the validation window (November to December 2019; Platt scaling) so that PDs are comparable and usable in the break-even rule. |
| **Scorecard points** | points = 600 + 20/ln(2) · ln(odds ÷ 50), where odds = (1 − PD) ÷ PD (good:bad) from the scorecard's own, pre-calibration PD. Higher points = lower risk; +20 points doubles the good:bad odds (PDO = 20); 600 points = raw odds of 50:1, which after calibration on the validation window is a PD of about 2.4%. Cut-offs in points are translated from the calibrated break-even PDs (notebook 04). Points per variable add up to the score; missing values score as a neutral WOE of 0. |
| **AUC / Gini** | Probability a random bad scores riskier than a random good; Gini = 2·AUC − 1. Differences are quoted in Gini points (0.01 = one point). |
| **KS** | Max distance between the cumulative score distributions of bads and goods. |
| **Calibration-in-the-large** | mean predicted PD ÷ observed bad rate (1.00 = perfect). |
| **Calibration by decile** | mean PD vs observed bad rate inside each predicted-PD decile, with 95% Wilson intervals. |
| **Calibration slope** | coefficient of a logistic regression of the outcome on the model's log-odds in a given window. 1.0 = the model spreads risk correctly (only the level may be off); below 1 = predictions too extreme; above 1 = too timid. |
| **Brier score** | mean of (PD − outcome)². |

## Swap set

Two policies are compared on the same applications (e.g. today's policy vs the cost-based rule, or the champion vs the challenger under the same rule):

| Cell | Definition |
|---|---|
| **Approved by both** | approved under the current and the proposed policy |
| **Swap-in** | declined by the current policy, approved by the proposed policy ("从拒变批") |
| **Swap-out** | approved by the current policy, declined by the proposed policy ("从批变拒") |
| **Declined by both** | declined under both |

Each cell reports count, share, bads, bad rate with 95% CI, loan amount, and the credit loss and margin the cell would bring if approved (from observed outcomes). A good swap has swap-in bad rate well below swap-out bad rate.

Model comparisons can also hold one side fixed. **At the same bad rate:** the challenger approves its lowest-PD applicants up to the largest share whose approved-book bad rate does not exceed the champion's; the gain is the extra approval rate in percentage points (pp). **At the same approval rate:** the challenger approves the same share as the champion, lowest PD first; the gain is the change in credit loss.

## Stability and monitoring

| Metric | Definition | Thresholds |
|---|---|---|
| **PSI** (population stability index) of the score | Σᵢ (A′ᵢ − E′ᵢ) · ln(A′ᵢ ÷ E′ᵢ) over 10 bins set at the **training-window** score deciles; Eᵢ = training share, Aᵢ = share in the month being monitored. Shares are floored before the formula: E′ = max(E, 10⁻⁶), A′ = max(A, 10⁻⁶). | < 0.10 stable · 0.10 to 0.25 investigate · ≥ 0.25 act |
| **CSI** (characteristic stability index) | PSI applied to one input feature (missing values get their own bin; categorical inputs are compared by category share). For categorical inputs, bins are the union of categories seen in either period; an absent category gets share 0 before the floor. | same |
| **Monthly Gini** | Gini within each decision month. | investigate at 5 points below the validation Gini, act at 10 (reviewed quarterly on mature vintages) |
| **Early delinquency** (proposed, not in this dataset) | share of a vintage that is 30+ days past due at month 3 on book, compared with the share expected for those PDs. The fastest outcome signal; the dataset only carries a final default flag. | investigate at +20% vs expected, act at +40%; proposals in `config.yaml` (`proposals.early_delinquency_investigate` / `proposals.early_delinquency_act`), to be agreed before go-live |
| **Calibration ratio by month** | mean PD ÷ observed bad rate per month. | alert outside 0.8 to 1.25 |
| **Vintage bad rate** | bads ÷ loans booked in the vintage month. | |
| **Vintage curve** (full definition) | cumulative bad rate of a vintage by months on book (MOB 1, 2, 3, ...). Needs the date of default; **not available in this dataset**, which only has a final default flag, so vintages are compared on their final bad rate. | |
| **Override rate** | share of decisions where the final decision differs from the policy's; **override bad rate** = bad rate of loans approved against the policy. | investigate above 5% of decisions; act if the override bad rate exceeds that of policy-approved loans |

## Fairness

| Metric | Definition | Threshold |
|---|---|---|
| **Approval-rate ratio** (adverse impact ratio) | approval rate of a group ÷ approval rate of the most-approved group | flag < 0.80 (four-fifths screen) |
| **Bad rate among approved by group** | as above, per group | large gaps mean the same cut-off carries different risk by group |
| **Calibration by group** | mean PD ÷ observed bad rate per group | over- or under-prediction for a group |

Groups: sex (`sex_738L`) and age band at decision (from the applicant's birth date `birth_259D`). Both are used **only to test** the policy, never as model inputs.
