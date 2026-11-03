# Model card: application PD model for consumer loans

**Version** 1.0 · **Owner** Credit Risk Analytics · **Date** 2026-11-03 · **Status** submitted to Model Risk / Validation; not approved for production

This card documents two models built on the same data. The **champion** is a 16-variable WOE logistic-regression scorecard that stands in for the lender's incumbent model. The **challenger** is LightGBM on 90 point-in-time features. **The challenger is the model proposed for approval.** The card is written for Model Risk / Validation, Compliance and the Head of Credit Policy.

Unless stated otherwise, numbers are for the out-of-time test (Jan to Mar 2020): 222,681 booked loans with a bad rate of 4.41%. Every loan in the data was approved by the historical policy, so each approval rate in this card is a share of previously approved applicants; the bad rate of past rejects is unknown. Money is in the dataset's undisclosed currency units (CU). Margins, LGD, EAD and review effectiveness are assumptions ([assumptions.md](assumptions.md)). Metric definitions are in [02_metric_definitions.md](02_metric_definitions.md).

## Summary for the approver

| | Champion (scorecard) | Challenger (LightGBM), proposed |
|---|---|---|
| Inputs | 16 binned variables | 90 features |
| Gini, out-of-time test | 0.462 | 0.578 |
| KS | 0.342 | 0.432 |
| Mean PD ÷ observed bad rate | 0.86 | 0.90 |
| Cost-based rule: approval rate | 92.5% | 90.7% |
| Cost-based rule: bad rate of approved loans | 3.57% | 3.17% |
| Cost-based rule: net profit over the quarter | 945.5M CU | 991.8M CU |
| Decline reasons | Points below each variable's maximum; a defect was found (section 7.4) | SHAP; contributions add up exactly to the model's raw log-odds |

**Developer's recommendation.** Approve the challenger for a controlled champion/challenger test on 20% of applications, stratified by product, not for a full switch. The conditions are in section 11.2. The most important three: recalibrate the PD on the latest mature vintage (it ran 10% low on the test quarter); get Compliance decisions on the calibration gaps by sex and age (section 8.5); and monitor calibration and early delinquency, not only score stability, because score stability alone missed the 2020 shift (section 10.2).

**Main risks.** No outcomes exist for applicants the old policy rejected. The PD level drifts when the base rate moves. The model under-predicts the risk of men and of 18-24-year-olds (calibration ratio 0.73 for both). Its largest input, years with current employer, is the field whose data capture broke in April 2020.

## 1. Model details

| Field | Value |
|---|---|
| Name | Application PD model, consumer loans: champion (scorecard) and challenger (LightGBM) |
| Version | 1.0 (both models) |
| Owner | Credit Risk Analytics |
| Date | 2026-11-03 |
| Status | Challenger proposed for approval; both models submitted for independent validation |
| Materiality | Would decide every new consumer-loan application: about 74,200 booked loans a month in the test quarter, plus the applications the old policy rejected (not in the data) |
| Purpose | Probability of default (PD) of a new consumer-loan application, at the decision date |
| Challenger type | Gradient-boosted decision trees (LightGBM 4.7.0, binary objective): 963 trees on 90 inputs, Platt-scaled to a PD |
| Champion type | Logistic regression on weight-of-evidence (WOE) bins (optbinning 1.0.0 with scikit-learn 1.9.1): 16 variables, scaled to points, Platt-scaled to a PD |
| Output | A calibrated PD from both models. The champion also gives points: 600 points at good:bad odds of 50:1, and +20 points doubles the odds |
| Decision use | Cost-based rule: approve when the PD is below the product's break-even PD (cash loan 25.0%, revolving 14.3%, point-of-sale 7.7%). The challenger's PD also assigns the three tiers: Auto-approve, Manual review, Decline |
| Data | Home Credit "Credit Risk Model Stability" (Kaggle 2024), training files: 1,526,659 booked loans decided from 2019-01-01 to 2020-10-05 |
| Artefacts | `artifacts/challenger_lightgbm.txt` (LightGBM text model, 963 trees) · `artifacts/champion_scorecard.pkl` (pickled optbinning `Scorecard`, including its binning process) · `artifacts/calibration.json` (Platt parameters a and b for each model). Git-ignored; written by notebook 03 |
| Code | Feature build: [sql/01](../sql/01_stg_base.sql) to [sql/05](../sql/05_fct_application_features.sql) · catalog, labels and groups: [src/features.py](../src/features.py) · training, calibration and scorecard reasons: [src/modeling.py](../src/modeling.py) · SHAP and principal reasons: [src/explain.py](../src/explain.py) · metrics: [src/metrics.py](../src/metrics.py) · fairness: [src/fairness.py](../src/fairness.py) · monitoring: [src/monitoring.py](../src/monitoring.py) · cost rule and tiers: [src/economics.py](../src/economics.py), [src/strategy.py](../src/strategy.py) |
| Notebooks | Fit and evaluation: [notebooks/03_modeling.ipynb](../notebooks/03_modeling.ipynb) · policy, fairness and monitoring: [notebooks/04_threshold_and_strategy.ipynb](../notebooks/04_threshold_and_strategy.ipynb) |
| Configuration | [config.yaml](../config.yaml): time split, seed 42, cost and review assumptions |
| Reproduction | `make all` rebuilds the features, executes the notebooks, writes the artefacts and [reports/metrics.json](../reports/metrics.json). Python 3.12; versions pinned in [requirements.txt](../requirements.txt) |

## 2. Intended use and out-of-scope uses

**Intended use**

- Score a new application for a cash loan, a point-of-sale loan or a revolving card in this lender's consumer portfolio, at the moment of the decision. Only information dated strictly before the decision date is used (point-in-time).
- Feed the cost-based rule. With the challenger, the rule approves 90.7% of test-quarter applications. The three-tier version sends 86.6% to Auto-approve, 5.0% to Manual review (3,711 a month, the assumed review capacity) and 8.4% to Decline. Cut-off analysis: [cutoff_and_swap_set.md](cutoff_and_swap_set.md).
- Give up to four principal reasons for each decline or referral (section 7).
- Users: Credit Policy owns the cut-offs, Underwriting Operations works the review queue, Risk Analytics runs the monitoring.
- Route to production: a randomised champion/challenger test with 20% of applications on the challenger, stratified by product. About 32,438 approved loans per arm are needed to detect the gap between the two approved-book bad rates (3.57% vs 3.17%; two-sided 5% test, 80% power). That is roughly 2.4 months of applications, then the outcome window.

**Out of scope**

| Use | Why not |
|---|---|
| Pricing or risk-based interest rates | Not designed or tested for it. Interest-rate and campaign fields were excluded so that the model does not learn the old pricing engine's decisions |
| Credit limits, loan amounts, line increases | The PD is conditional on the amount and term requested; it was not tested for setting them |
| Collections or early warning on existing accounts | Application-time model; it uses no information from after the decision |
| Fraud detection | The target is default, not fraud; there are no fraud labels |
| Applicants outside the booked population, such as those the historical policy rejected | Trained and tested on booked loans only, without reject inference. Approving below today's line needs the below-cut-off test first (section 3.2) |
| Provisioning (IFRS 9, CECL) or regulatory capital | The target's definition and horizon are not disclosed, and the PD is calibrated to one recent window, not through the cycle |
| Other lenders, countries or products | Not tested |
| Any decision that uses sex, age or income type | These are kept only to test outcomes by group (section 4.4) |

## 3. Data

### 3.1 Sources

| Table | Grain | Rows | Loans covered | Used for |
|---|---|---|---|---|
| `train_base` | one row per loan | 1,526,659 | 100% | decision date, target, time split |
| `train_static_0` (2 files) | one row per loan | 1,526,659 | 100% | loan terms, internal repayment-history summaries, contact sharing |
| `train_static_cb_0` | one row per loan | 1,500,476 | 98.3% | credit-bureau enquiry counts |
| `train_applprev_1` (2 files) | one row per previous application | 6,525,979 | 80.0% (1,221,522) | previous applications with this lender, rebuilt point-in-time |
| `train_person_1` | one row per person per loan | 2,973,991 | 100% (applicant row) | employment years and income; sex, birth date and income type for fairness tests only |

The raw files are read in place with DuckDB and never stored in the repository. The tables reconcile: keys are unique, no child table has orphan records, and every feature table has exactly one row per booked loan ([notebooks/01_data_audit.ipynb](../notebooks/01_data_audit.ipynb), [sql/dq/](../sql/dq)).

### 3.2 Population: booked loans only

All 1,526,659 loans were booked, so outcomes exist only for applicants the historical policy approved. Applications it rejected are not in the data. Consequences:

1. The PD is estimated on approved applicants. How well it ranks or calibrates applicants the old policy would have declined is unknown.
2. Every approval rate in this card is a share of previously approved applicants, not a through-the-door approval rate.
3. Tightening can be measured. Under the challenger's cost-based rule, the 9.3% of booked loans it would decline defaulted at 16.61% (95% interval 16.11% to 17.12%). Loosening cannot be measured: the bad rate of past rejects was never observed.
4. No reject inference was attempted. A below-cut-off test (about 589 approved loans just below today's line, with an expected net loss of about 2.6M CU) would measure the bad rate the model cannot see.

### 3.3 Target

`target = 1` as supplied by Home Credit. We call it default ("bad"), and `target = 0` "good". The delinquency definition and the outcome horizon are not disclosed. Over all loans there are 47,994 defaults, a bad rate of 3.14%. Vintages up to March 2020 are treated as mature; outcomes for the April to October 2020 vintages may not be complete.

### 3.4 Time windows

The split is strictly by decision month; there is no random split anywhere ([config.yaml](../config.yaml)).

| Window | Decision dates | Loans | Defaults | Bad rate | Used for |
|---|---|---|---|---|---|
| Train | Jan to Oct 2019 | 828,906 | 24,564 | 2.96% | fitting both models; scorecard binning and variable selection |
| Validation | Nov to Dec 2019 | 241,856 | 8,484 | 3.51% | challenger early stopping; Platt calibration of both models |
| Out-of-time test | Jan to Mar 2020 | 222,681 | 9,829 | 4.41% | every headline number |
| Monitoring | Apr 2020 to 5 Oct 2020 | 233,216 | 5,117 | 2.19% | monitoring back-test only |
| All | 1 Jan 2019 to 5 Oct 2020 | 1,526,659 | 47,994 | 3.14% | |

The population moves between windows. The bad rate rises from 2.96% (train) to 4.41% (test), then roughly halves to 2.19% in the COVID-period monitoring window, when monthly volume fell from 60,748 loans in March 2020 to 8,289 in April. New-to-lender clients fall from 23.0% of loans (train) to 17.6% (test) and 14.9% (monitoring). Point-of-sale loans are 66.1% of the training window and 60.5% of the test window.

### 3.5 Data quality: the 14-day look-ahead leak

The source's history snapshot was taken about 14 days after the decision. The provided "applications in the last 30 days" matches a point-in-time recount for 90.1% of loans, against 96.7% to 98.4% for windows that reach past the decision. The provided "last application date" equals the latest application in the table, counting applications made after the decision, for 100% of loans, and the latest application before the decision for only 90.4%. History features were therefore rebuilt as of the decision date, and fields that could not be rebuilt were dropped (section 4.3).

The ablation in [notebooks/02_feature_eng.ipynb](../notebooks/02_feature_eng.ipynb) sizes the effect. The same LightGBM set-up on the snapshot as provided reaches an out-of-time Gini of 0.588, against 0.578 point-in-time. Scored on decision-time inputs where they can be rebuilt, it drops to 0.585, and its profit under the cost-based rule is within 0.3% of ours. The naive model's edge is about twice as large among the 10.6% of test loans with client activity after the decision (+0.013 Gini) as among the rest (+0.007). The leak exists but is small in this data; the strict fix cost less than one Gini point. Full audit: [03_data_quality_checks.md](03_data_quality_checks.md).

## 4. Features

### 4.1 The 90 features

The features are defined in `CATALOG` in [src/features.py](../src/features.py). Each has a plain-English label (which doubles as decline-reason text), a business group and an expected risk direction. The build fails if the SQL feature table and the catalog disagree. 85 features are numeric and 5 categorical (product, how the loan is paid out, outcome of the last application, reason for the last rejection, reason for the last cancellation).

| Group | Features | Examples |
|---|---|---|
| Repayment history | 30 | Average days late, last 24 months · Worst days past due, last 12 months · Share of instalments paid late |
| Previous applications | 29 | Share of past applications rejected · Days since last rejection · Loans repaid with no late payment |
| Loan terms | 11 | Loan amount requested · Loan term (months) · Monthly payment on this loan |
| Affordability | 11 | Years with current employer · Monthly payment as share of income · Declared monthly income |
| Credit bureau | 5 | Credit checks 1-6 months before applying · Credit checks 6-12 months before applying |
| Contact details | 4 | People sharing the applicant's mobile · Home phone numbers given |
| **Total** | **90** | |

### 4.2 How the 90 were chosen

All 294 raw columns were reviewed one by one against written rules: 41 kept as provided, 27 rebuilt point-in-time, 223 dropped and 3 kept for fairness testing only. The decision and the reason for every column are in [feature_inclusion_log.csv](feature_inclusion_log.csv). The 223 drops: short-window or current-status snapshot fields (49), almost empty or constant (38), fair-lending exclusions (33), duplicates of a kept field (30), no measurable signal (26), unstable coverage or meaning (15), tax-authority fields that arrive after the decision (11), fields dated after the decision or describing a post-decision event (13), outputs of the lender's own pricing or targeting (5), fields collected only from mid-2019 (2), and one identifier.

### 4.3 Point-in-time rules (summary)

- Only information dated strictly before the decision date is used.
- Previous applications ([sql/03](../sql/03_int_applprev_pit.sql)): only applications created before the decision are used (144,679 later rows, 2.2%, are removed), at most the 15 most recent. "Approved" means an approval date before the decision, not the snapshot status.
- Days past due on previous contracts are used as recorded only if the contract closed before the decision. Otherwise they are reduced by 14 days and floored at 0, a guaranteed lower bound of what was known. Snapshot balances (current debt, current days past due) are not used.
- Internal snapshot ([sql/02](../sql/02_stg_static.sql)): dated "last event" fields are never used raw; they are rebuilt from previous applications. Snapshot aggregates with a look-back under 6 months, current-status fields, tax-authority fields and columns rolled out part-way through 2019 are not used. Maximum days-past-due fields are set to 0 when the delinquency could have happened entirely after the decision.
- Credit bureau: the provided "30-day" window covers 16 days before to 14 days after the decision. Only window differences are used (for example 180 days minus 30 days), which end 16 days before the decision.
- Employment start dates after the decision (316 loans) are set to missing.

### 4.4 Fair-lending exclusions

Never used as model inputs: sex and gender; birth date and age; marital and family status; number of children and dependents; education; language; profession; income type (it contains pension and disability categories); addresses, districts and zip codes; relationship and role fields, including the persons accompanying the applicant; and a flag for sudden changes in socio-demographic data. Sex, age (from the applicant's birth date) and income type are kept, prefixed `fair_`, only to test outcomes by group (section 8). Interest-rate and marketing-campaign fields are also excluded, as outputs of the lender's own pricing and targeting ([assumptions.md](assumptions.md), P4).

## 5. Development

### 5.1 Champion: WOE logistic-regression scorecard

1. **Binning.** Monotonic optimal binning (optbinning) of all 90 candidates on the training window. The trend (ascending or descending) is chosen automatically, with at most 6 bins of at least 2% of loans each. Missing values get their own bin.
2. **Selection,** in descending order of Information Value (IV): IV of at least 0.02 (29 candidates failed); IV of at most 0.8 (none failed); absolute WOE correlation of at most 0.6 with every variable already selected (22 failed); at most 18 variables (21 candidates with enough IV came after the cap was reached).
3. **Fit.** Logistic regression on the WOE values (scikit-learn, L2 penalty, C = 1.0).
4. **Sign check.** Every coefficient must be negative (a higher WOE means safer). Two variables flipped sign through collinearity and were removed before refitting: share of repaid loans ever paid late, and instalments paid late. Result: **16 variables**.
5. **Scaling.** PDO 20, 600 points at odds of 50:1, no rounding. Points are on the raw (pre-calibration) scale: 600 points is a raw PD of 1.96% and a calibrated PD of 2.40%. The possible range is 470 to 668 points. The break-even PDs translate into cut-offs of 524 points (cash loan), 544 (revolving) and 564 (point-of-sale).

The selection log is `data/processed/dashboard/scorecard_selection.parquet`; the points per bin are in `scorecard_points.parquet` (both written by notebook 03).

| # | Variable | Label | IV (train) | Coefficient | Points range |
|---|---|---|---|---|---|
| 1 | `avg_dpd_24m` | Average days late, last 24 months | 0.311 | −0.414 | 22.2 to 43.3 |
| 2 | `net_punctuality` | Early minus late payment share | 0.284 | −0.226 | 30.1 to 42.9 |
| 3 | `ap_n_repaid_ontime` | Loans repaid with no late payment | 0.200 | −0.564 | 29.1 to 54.6 |
| 4 | `ap_share_rejected` | Share of past applications rejected | 0.189 | −0.231 | 32.9 to 40.1 |
| 5 | `ap_max_dpd_safe` | Worst days past due on past loans with us | 0.178 | −0.185 | 31.6 to 38.8 |
| 6 | `max_dpd_12m` | Worst days past due, last 12 months | 0.176 | −0.258 | 28.1 to 38.2 |
| 7 | `ap_days_since_last_reject` | Days since last rejection | 0.153 | −0.386 | 29.0 to 41.0 |
| 8 | `avg_worst_dpd_9m` | Average worst lateness, last 9 months | 0.148 | −0.048 | 36.1 to 37.8 |
| 9 | `n_instalments_10d_late` | Instalments paid 10+ days late | 0.104 | −0.039 | 36.9 to 37.7 |
| 10 | `n_people_same_mobile` | People sharing the applicant's mobile | 0.098 | −0.780 | 23.0 to 43.7 |
| 11 | `min_days_late_24m` | Least-late payment, last 24 months | 0.090 | −0.212 | 32.3 to 39.4 |
| 12 | `dpd_worsening` | Lateness got worse in last 6 months | 0.088 | −0.428 | 26.9 to 37.7 |
| 13 | `employment_years` | Years with current employer | 0.069 | −1.154 | 19.8 to 54.4 |
| 14 | `cb_enquiries_1_to_6m` | Credit checks 1-6 months before applying | 0.067 | −0.520 | 27.7 to 40.1 |
| 15 | `max_past_debt` | Largest past debt (4+ months ago) | 0.059 | −0.397 | 33.8 to 39.7 |
| 16 | `ap_days_since_last_app` | Days since last application | 0.056 | −0.420 | 30.4 to 38.4 |

Reading the table:
- 8 of the 16 variables describe repayment history and 5 describe previous applications with this lender.
- No loan-terms variable made it. Under monotonic binning their IV was below 0.02, except loan term (0.036), which came after the cap was reached. The challenger, which has no monotonic constraint, ranks loan term and monthly payment second and fourth among its inputs (section 7.1).
- Two variables add almost nothing: average worst lateness, last 9 months (1.7 points of range) and instalments paid 10+ days late (0.8 points).
- A missing value scores 37.24 points on every variable: the points of a WOE of 0, not of the missing bin's own WOE (section 9, row 11).

### 5.2 Challenger: LightGBM

| Setting | Value |
|---|---|
| Inputs | All 90 features. Missing values and the 5 categorical features are handled natively; category levels are frozen from the training window, so an unseen level becomes missing |
| Objective | Binary (log-loss) |
| Learning rate | 0.03 |
| Tree size | At most 63 leaves (`num_leaves`), at least 400 loans per leaf (`min_data_in_leaf`) |
| Sampling | 80% of rows per tree, redrawn every iteration (`bagging_fraction`, `bagging_freq` 1); 60% of features per tree (`feature_fraction`) |
| Regularisation | L2 penalty of 10 (`lambda_l2`) |
| Categorical settings | One-hot up to 8 levels (`max_cat_to_onehot`), smoothing 50 (`cat_smooth`), at least 200 loans per category group (`min_data_per_group`) |
| Histogram bins | 255 (`max_bin`) |
| Reproducibility | `deterministic`; seed 42 for every random draw |
| Boosting rounds | Up to 5,000, stopping after 200 rounds without improvement in validation AUC. Best iteration: **963**; the saved model has 963 trees |
| Not used | Monotone constraints, class weights, hyper-parameter search |

The parameters are `LGBM_PARAMS` in [src/modeling.py](../src/modeling.py). They were set once, with conservative leaf sizes and early stopping, rather than tuned, to avoid overfitting the validation window.

### 5.3 Calibration

Both models are recalibrated with Platt scaling on the validation window (Nov to Dec 2019: 241,856 loans, bad rate 3.51%):

PD = 1 ÷ (1 + exp(−(a × logit(p) + b))), where p is the raw model output.

The two parameters are fitted as an effectively unpenalised logistic regression (scikit-learn, C = 10⁶). The transformation is monotonic, so the ranking does not change.

| Model | a | b |
|---|---|---|
| Challenger | 0.948 | 0.093 |
| Champion | 0.984 | 0.144 |

On the validation window the mean PD equals the bad rate for both models (calibration ratio 1.00). On the test quarter, which defaulted more (4.41%), both under-predict (section 6.4).

### 5.4 Class imbalance

Defaults are 2.96% of the training window (24,564 loans). Neither model uses resampling or class weights; the cut-off comes from costs instead. Evidence from notebook 03 (`imbalance_experiment.parquet`, test window, observed bad rate 4.41%):

| Approach | Test AUC | Mean raw PD | Approval rate if the break-even rule is applied to the raw output | Approval rate after recalibration | Net profit after recalibration |
|---|---|---|---|---|---|
| LightGBM, no re-weighting (used) | 0.789 | 3.2% | 93.0% | 90.7% | 991.8M CU |
| LightGBM, class weight (balanced) | 0.785 | 35.4% | 22.3% | 90.2% | 990.1M CU |
| Logistic on WOE, no re-weighting (used) | 0.731 | 3.2% | 94.6% | 92.5% | 945.5M CU |
| Logistic on WOE, class weight (balanced) | 0.733 | 42.8% | 6.5% | 92.6% | 946.3M CU |
| Logistic on WOE, SMOTE (300,000-loan sample) | 0.731 | 42.8% | 6.4% | 92.3% | 944.5M CU |

Re-weighting and SMOTE leave the ranking about the same but inflate raw PDs to 35% to 43%. Applying the break-even rule to those outputs would approve only 6% to 22% of applicants. After recalibration they land where the unweighted models already are, so resampling adds a step and no value. SMOTE would also mean training on synthetic applicants, which is hard to defend in a model review.

### 5.5 Training window

Bureau enquiry data was not collected for about 45% of January 2019 applications, so later start dates were tested (notebook 03 appendix, `training_window_check.parquet`):

| Training from | Loans | Defaults | Validation Gini | Test Gini |
|---|---|---|---|---|
| Jan 2019 (used) | 828,906 | 24,564 | 0.582 | 0.578 |
| Mar 2019 | 690,313 | 20,874 | 0.579 | 0.577 |
| Jun 2019 | 484,560 | 14,771 | 0.575 | 0.572 |

Starting later lowered Gini on both windows, and bureau inputs carry about 5% of the challenger's impact, so the full January to October 2019 window was kept. The early-2019 bureau gap stays on the monitoring list.

## 6. Performance

### 6.1 Rank-ordering and calibration by window

From `model_metrics.parquet`. Calibration ratio = mean PD ÷ observed bad rate (1.00 = calibrated in the large).

| Window | Loans | Bad rate | Model | AUC | Gini | KS | Brier | Calibration ratio |
|---|---|---|---|---|---|---|---|---|
| Train (Jan to Oct 2019) | 828,906 | 2.96% | Champion | 0.737 | 0.474 | 0.350 | 0.0281 | 1.20 |
| | | | Challenger | 0.875 | 0.751 | 0.574 | 0.0247 | 1.25 |
| Validation (Nov to Dec 2019) | 241,856 | 3.51% | Champion | 0.734 | 0.468 | 0.341 | 0.0328 | 1.00 |
| | | | Challenger | 0.791 | 0.582 | 0.434 | 0.0320 | 1.00 |
| **Out-of-time test (Jan to Mar 2020)** | 222,681 | 4.41% | Champion | 0.731 | 0.462 | 0.342 | 0.0407 | 0.86 |
| | | | Challenger | 0.789 | 0.578 | 0.432 | 0.0393 | 0.90 |
| Monitoring (Apr to Oct 2020) | 233,216 | 2.19% | Champion | 0.761 | 0.522 | 0.389 | 0.0210 | 1.50 |
| | | | Challenger | 0.803 | 0.606 | 0.457 | 0.0207 | 1.50 |

- The challenger ranks better on every window: +0.114 Gini on validation and +0.116 on the test quarter.
- From validation to test, the challenger loses 0.004 Gini and the champion 0.006, both well inside the 5-point alert (section 10.1).
- Calibration ratios above 1 on the training window are expected: both models were calibrated on validation, which defaulted more (3.51% vs 2.96%).
- The higher Gini in the monitoring window should not be read as an improvement. The population changed (fewer new-to-lender clients, COVID-period conditions) and those outcomes may not be mature.

### 6.2 The challenger's train-versus-validation gap

The challenger's Gini is 0.751 on the training window and 0.582 on validation, a gap of 0.169. The champion's gap is 0.005 (0.474 vs 0.468). By month, the challenger's Gini is 0.732 to 0.764 in the training months and 0.560 to 0.586 in the validation and test months.

- The gap is in-sample fit: 963 trees with up to 63 leaves each fit the training loans closely. It is not instability, because validation, test and monitoring Gini sit close together (0.582, 0.578, 0.606).
- Training-window metrics are not evidence of performance, and training-window predictions should not be used to calibrate the model. That is why Platt scaling is fitted on validation.
- Whether a more regularised set-up (fewer leaves, a larger minimum leaf) would keep the out-of-sample Gini with a smaller gap was not tested. Model Risk may want that sensitivity run (section 11.1).

### 6.3 Business performance (test quarter)

From `model_business_comparison.parquet`. Same applications and same costs; only the model and the policy differ. Approval rates are shares of previously approved applicants.

| Model | Policy | Approval rate | Bad rate of approved | Bads declined | Goods declined | Credit losses | Margin forgone | Net profit |
|---|---|---|---|---|---|---|---|---|
| Champion | Cost-based rule | 92.5% | 3.57% | 25.3% | 6.7% | 318.7M CU | 28.6M CU | 945.5M CU |
| Challenger | Cost-based rule | 90.7% | 3.17% | 34.9% | 8.1% | 254.1M CU | 46.9M CU | 991.8M CU |
| Champion | Approve the safest 90% | 90.0% | 3.33% | 32.1% | 9.0% | 286.2M CU | 94.8M CU | 911.8M CU |
| Challenger | Approve the safest 90% | 90.0% | 2.98% | 39.3% | 8.6% | 222.4M CU | 113.4M CU | 957.0M CU |
| Champion | Approve the safest 95% | 95.0% | 3.77% | 18.8% | 4.4% | 332.4M CU | 44.3M CU | 916.1M CU |
| Challenger | Approve the safest 95% | 95.0% | 3.49% | 25.0% | 4.1% | 279.0M CU | 48.2M CU | 965.7M CU |

Head to head ([reports/metrics.json](../reports/metrics.json)):
- **At the champion's bad rate (3.57%)** the challenger approves 95.8% of applications instead of 92.5%: +3.3 pp, about 2,458 more loans a month, and 20.8M CU more net profit over the quarter.
- **At the champion's approval rate (92.5%)** the challenger's approved book defaults at 3.22% instead of 3.57%, and credit losses are 68.9M CU (22%) lower.
- **Each at its own cost-based rule,** the challenger approves 1.8 pp fewer applications, cuts credit losses by 64.6M CU and adds 46.3M CU of net profit. Swap-outs (approved by the champion, declined by the challenger: 8,708 loans, 3.9%) defaulted at 14.70% (95% interval 13.97% to 15.46%). Swap-ins (4,776 loans, 2.1%) defaulted at 7.08% (6.38% to 7.84%).
- **Against a 0.5 cut-off,** which approves almost everyone, the cost-based rule cuts the total cost of wrong decisions by 23% with the challenger (12% with the champion) and credit losses by 35% (19%).

The full cut-off and swap-set analysis is in [cutoff_and_swap_set.md](cutoff_and_swap_set.md).

### 6.4 Calibration by decile (test quarter)

From `calibration_test.parquet`: challenger PDs sorted into ten equal groups (22,268 or 22,269 loans each), with 95% Wilson intervals on the observed bad rate.

| Decile (low to high risk) | Mean PD | Observed bad rate (95% interval) | Mean PD ÷ observed |
|---|---|---|---|
| 1 | 0.30% | 0.25% (0.19% to 0.32%) | 1.23 |
| 2 | 0.62% | 0.53% (0.44% to 0.63%) | 1.17 |
| 3 | 0.97% | 1.11% (0.98% to 1.26%) | 0.87 |
| 4 | 1.39% | 1.76% (1.59% to 1.94%) | 0.79 |
| 5 | 1.94% | 2.26% (2.07% to 2.46%) | 0.86 |
| 6 | 2.64% | 2.82% (2.62% to 3.05%) | 0.94 |
| 7 | 3.56% | 4.08% (3.83% to 4.35%) | 0.87 |
| 8 | 4.89% | 5.64% (5.34% to 5.95%) | 0.87 |
| 9 | 7.27% | 8.33% (7.98% to 8.71%) | 0.87 |
| 10 | 16.11% | 17.36% (16.86% to 17.86%) | 0.93 |

- In 7 of 10 deciles the whole interval lies above the mean PD: the challenger under-predicts. In no decile does the whole interval lie below it. The top decile holds 39.3% of test defaults.
- The champion under-predicts in 8 of 10 deciles. Its top decile has a mean PD of 13.03% against 14.15% observed and holds 32.1% of test defaults.
- Calibration slope on the test quarter (a logistic regression of the outcome on the model's log-odds): 0.99 for the challenger and 0.95 for the champion. Both spread risk about right; what moved is the level. Matching the test bad rate needs an intercept shift of +0.12 log-odds for the challenger and +0.17 for the champion. The challenger's two figures are in reports/metrics.json; the champion's were recomputed for this card from `predictions_test.parquet` with the same method as notebook 04.

Does the miscalibration change decisions? Notebook 04 (section 9) re-runs the challenger's cost-based rule under two alternative PD levels:

| View | Mean PD | Calibration ratio | Approval rate | Bad rate of approved | Net profit |
|---|---|---|---|---|---|
| As calibrated on Nov to Dec 2019 | 3.97% | 0.90 | 90.7% | 3.17% | 991.8M CU |
| Hindsight: intercept refitted on the test quarter | 4.41% | 1.00 | 89.3% | 3.08% | 993.2M CU |
| Stress: every applicant's odds of default +25% | 4.84% | 1.10 | 87.9% | 2.99% | 994.0M CU |

Net profit moves by less than 0.3% across the three views, while the approval rate moves by up to 2.9 pp. The cost-based rule holds up under a calibration error of this size; the approval rate does not. The hindsight refit is not available in production, because outcomes take months to mature. Hence the plan: recalibrate on the latest mature vintage and track the calibration ratio monthly.

### 6.5 Segments (test quarter)

From `segment_metrics.parquet`.

| Segment | Loans | Share of test | Bad rate | Gini, champion | Gini, challenger | Calibration ratio, champion | Calibration ratio, challenger |
|---|---|---|---|---|---|---|---|
| New to lender | 39,085 | 17.6% | 2.66% | 0.270 | 0.421 | 0.97 | 1.05 |
| Existing client | 183,596 | 82.4% | 4.79% | 0.474 | 0.588 | 0.84 | 0.88 |
| Cash loan | 55,330 | 24.8% | 5.17% | 0.332 | 0.436 | 0.72 | 0.77 |
| Point-of-sale loan | 134,695 | 60.5% | 4.30% | 0.531 | 0.631 | 0.90 | 0.95 |
| Revolving | 32,656 | 14.7% | 3.58% | 0.462 | 0.591 | 0.95 | 0.97 |

- The challenger ranks better in every segment.
- Both models rank new-to-lender clients least well: these clients have no internal repayment history, so the models lean on application and bureau data. A segment-specific scorecard or cut-off is the standard next step.
- Cash loans are the most under-predicted segment (calibration ratio 0.77). At the 25.0% break-even PD this has little effect on decisions, since the challenger's rule approves 99.6% of cash loans (notebook 04, section 3). It would matter for any tighter cash-loan cut-off.

## 7. Explainability

### 7.1 Global drivers of the challenger (SHAP)

Mean absolute SHAP value (the average impact on the log-odds of default) over 20,000 randomly drawn test-quarter applications (`shap_global.parquet`):

| Group | Share of total impact |
|---|---|
| Repayment history | 26.0% |
| Previous applications | 25.6% |
| Loan terms | 19.9% |
| Affordability | 15.1% |
| Contact details | 8.2% |
| Credit bureau | 5.2% |

The client's track record with the lender (repayment history plus previous applications) carries 52% of the impact. No single input dominates: the largest carries 6.5% and the top ten together 37.8%.

| Rank | Input | Group | Share |
|---|---|---|---|
| 1 | Years with current employer | Affordability | 6.5% |
| 2 | Loan term (months) | Loan terms | 5.8% |
| 3 | People sharing the applicant's mobile | Contact details | 4.8% |
| 4 | Monthly payment on this loan | Loan terms | 3.8% |
| 5 | Average days late, last 24 months | Repayment history | 3.5% |
| 6 | Share of past applications rejected | Previous applications | 3.3% |
| 7 | Length of application history (days) | Previous applications | 2.9% |
| 8 | Home phone numbers given | Contact details | 2.6% |
| 9 | Monthly payment as share of income | Affordability | 2.3% |
| 10 | Days since last rejection | Previous applications | 2.3% |

One input, "Has a repayment record with us", has zero impact (the model never uses it), and "Has a credit-bureau enquiry record" has almost none. The two largest inputs, years with current employer and loan term, are also the two that moved most in the monitoring back-test (section 10.2).

### 7.2 Principal reasons for a decline

Both models give up to four principal reasons per application, written with the plain-English labels in [src/features.py](../src/features.py). Reasons explain the model's estimate, not the cause of default: they describe how inputs and predicted risk move together in approved loans.

- **Challenger** ([src/explain.py](../src/explain.py)): the four inputs with the largest positive SHAP contributions for that applicant, that is, the inputs that pushed the PD up the most (fewer if fewer than four push it up). SHAP values come from shap's TreeExplainer on the booster, in raw log-odds. They add up exactly: the SHAP base value (−4.143 log-odds, a raw PD of 1.6%) plus the 90 contributions equals the model's raw log-odds. On the 2,000-case explanation sample the largest difference is 3 × 10⁻¹⁴. Platt scaling then maps the log-odds to the PD; because it is monotonic, the ranking of reasons is the same on the PD scale.
- **Champion** ([src/modeling.py](../src/modeling.py), `scorecard_reason_codes`): the four variables where the applicant scored furthest below that variable's maximum points ("points below maximum", the usual convention for scorecard adverse-action reasons). Section 7.4 describes a defect in the implementation.
- No reason can be a protected attribute, because none is an input. Two categorical inputs (reason for the last rejection, reason for the last cancellation) are hashed codes in the source and cannot be shown to a customer as text without the lender's code list.

The explanation sample (`explain_sample.parquet`) holds 2,000 test-quarter applications: 1,500 drawn at random from those the challenger's rule declines and 500 from those it approves.

### 7.3 Worked example: application 949636

A point-of-sale loan decided in February 2020: 19,955 CU, a monthly payment of 2,524 CU, declared monthly income of 50,000 CU. The break-even PD for point-of-sale loans is 7.69% (564 points on the champion's scale).

| | Challenger | Champion |
|---|---|---|
| Model output | Raw log-odds −2.322 | 564.5 points |
| Calibrated PD | 10.8% | 7.62% |
| Cost-based rule | Decline (10.8% is above 7.69%) | Approve (7.62% is below 7.69%) |

This is a swap-out: the champion approves the application by 0.3 points, the challenger declines it.

**How the challenger's PD is built.** Base value −4.143, plus the sum of the 90 SHAP contributions, +1.821 (+3.223 from inputs that raise risk, −1.402 from inputs that lower it), gives raw log-odds of −2.322 (a raw PD of 8.9%). Platt scaling: 0.948 × (−2.322) + 0.093 = −2.108, so PD = 1 ÷ (1 + e^2.108) = 10.8%.

**Challenger reasons.** The applicant's value is compared with the median among test applications the challenger approves.

| Reason | Applicant | Typical approved | SHAP (log-odds) |
|---|---|---|---|
| People sharing the applicant's mobile | 4 | 1 | +0.608 |
| Share of past applications rejected | 60% | 25% | +0.376 |
| Days since last rejection | 56 | 464 | +0.325 |
| Years with current employer | 3.4 | 4.0 | +0.239 |

The largest offsets are a short loan term (9 months against a typical 12; −0.213) and a short term on the last approved loan (3 months against 12; −0.192).

**Champion reasons (points below maximum).** Years with current employer: 25.1 (3.4 years earns 29.3 of a possible 54.4 points). People sharing the applicant's mobile: 20.7 (23.0 of 43.7). Loans repaid with no late payment: 18.0 (one such loan earns 36.6 of 54.6). Days since last rejection: 12.0 (29.0 of 41.0). This applicant has no missing values among the 16 variables, so these reasons are not affected by the defect in section 7.4.

Three of the four reasons are shared by the two models. What differs is the overall level: 10.8% against 7.62%, which puts the application on opposite sides of the line. The loan did not default. One case proves nothing either way: as a group, swap-outs under the recommended policy defaulted at 14.70% and swap-ins at 7.08%.

### 7.4 Defect found: the champion's reason codes overstate missing values

While preparing this card we found that `scorecard_reason_codes` in [src/modeling.py](../src/modeling.py), in the version that produced the current outputs, ranks reasons incorrectly whenever a variable is missing.

- **What happens.** The score gives a missing value 37.24 points on every variable, the points of a WOE of 0. The reason-code function looks up each applicant's points by matching WOE values against the points table. For a missing value the WOE (0) does not match the WOE listed for the missing bin, so a fallback formula is used, and it returns 0 points. The "points lost" on a missing variable is therefore overstated by 37.24 points, and missing variables crowd the top of the list.
- **Size.** For the 2,000-case explanation sample we recomputed each applicant's points by bin from the scorecard's own table. The recomputed points add up to the stored scores exactly (largest difference 0.0 points). The stored first reason matches the recomputed one for 17.0% of the sample, and the set of four reasons is identical for 47.1%. 1,850 of the 2,000 applications have at least one of the 16 variables missing. "Years with current employer", which is missing for 60.4% of training loans, is the stored first reason for 70.2% of the sample and the recomputed first reason for 27.7%.
- **Not affected:** scores, PDs, decisions and every performance number in this card. The challenger's SHAP reasons are not affected.
- **Where it shows:** notebook 03 (section 3.6), the dashboard's Model & Explainability page, and the example in [reports/report.html](../reports/report.html). There, for application 1819832, "Years with current employer" is listed first (54.4 points lost in `explain_sample.parquet`); recomputed, it is third, with 17.2.
- **Fix:** compute each variable's points from the WOE the score uses (WOE 0 for a missing value), re-run notebook 03 and regenerate the outputs; this is required before the scorecard's reasons are shown to anyone. The code change is now in src/modeling.py, but notebook 03 has not been re-run, so the outputs listed above still carry the defect.

## 8. Fairness checks

Sex and age band (from the applicant's birth date) are used only here, to test outcomes; they are never model inputs. Results are for the test quarter (`fairness.parquet`, notebook 04 section 8). Approval rates are shares of previously approved applicants.

### 8.1 Recommended policy: challenger with the cost-based rule

| Group | Applications | Approval rate | Ratio to most-approved group | Observed bad rate | Bad rate of approved loans (95% interval) | Mean PD | Calibration ratio |
|---|---|---|---|---|---|---|---|
| Women | 135,182 | 90.8% | 1.00 | 3.72% | 2.59% (2.50% to 2.68%) | 3.97% | 1.07 |
| Men | 87,499 | 90.6% | 1.00 | 5.48% | 4.07% (3.94% to 4.21%) | 3.97% | 0.73 |
| 18-24 | 12,580 | 85.7% | 0.89 | 7.57% | 5.64% (5.22% to 6.09%) | 5.49% | 0.73 |
| 25-34 | 55,416 | 87.9% | 0.92 | 5.31% | 3.72% (3.56% to 3.90%) | 4.72% | 0.89 |
| 35-44 | 56,095 | 89.4% | 0.93 | 4.60% | 3.18% (3.03% to 3.33%) | 4.19% | 0.91 |
| 45-54 | 41,587 | 91.9% | 0.96 | 3.92% | 2.85% (2.69% to 3.03%) | 3.64% | 0.93 |
| 55-64 | 35,759 | 94.5% | 0.98 | 2.94% | 2.29% (2.13% to 2.45%) | 3.13% | 1.07 |
| 65+ | 21,244 | 96.0% | 1.00 | 3.19% | 2.57% (2.36% to 2.80%) | 2.57% | 0.81 |

### 8.2 Three policies compared

| Policy | Lowest ratio, sex | Lowest ratio, age band | Calibration ratio, men | Calibration ratio, 18-24 | Calibration ratio, 65+ | Approval rate, 65+ |
|---|---|---|---|---|---|---|
| Champion, cost-based rule | 0.996 | 0.940 (25-34) | 0.68 | 0.62 | 0.91 | 96.0% |
| Challenger, cost-based rule (recommended) | 0.998 | 0.893 (18-24) | 0.73 | 0.73 | 0.81 | 96.0% |
| Challenger plus employment status | 0.995 | 0.879 (18-24) | 0.73 | 0.74 | 0.68 | 97.2% |

### 8.3 Proxy check

Excluding an attribute does not stop other inputs from carrying it. A quick LightGBM (200 trees), fitted on 70% of a 200,000-loan sample of the training window and scored on the other 30%, predicts sex from the 90 inputs with an AUC of 0.63 and age 50 or over with an AUC of 0.84, where 0.5 means no information (`proxy_check.parquet`). The age signal is strong. Notebook 02 attributes it mostly to product choice, loan size, income and repayment history, which differ by life stage. This is why outcomes are tested by group.

### 8.4 Interpretation

- Every group passes the four-fifths screen under all three policies. The lowest approval-rate ratio under the recommended policy is 0.89 (18-24).
- By age, approval rates rise with age and follow observed default rates: 18-24-year-olds defaulted at 7.57%, 55-64-year-olds at 2.94%. Compared with the champion, the challenger widens the approval gap for the youngest band (ratio 0.945 to 0.893) and narrows its calibration gap (0.62 to 0.73).
- By sex, approval rates are virtually equal (90.8% women, 90.6% men) although men default more often (5.48% vs 3.72%). The model gives both groups the same mean PD, 3.97%: it under-predicts the risk of men (ratio 0.73) and over-predicts that of women (1.07). Among approved loans, men defaulted at 4.07% and women at 2.59%.
- When groups default at different rates, equal approval rates and equal calibration usually cannot both hold. Which matters more is a policy question, not a modelling one.
- Adding employment status, which contains a "retired" category (a proxy for age), raises approval for 65+ from 96.0% to 97.2%. It also worsens their under-prediction (calibration ratio 0.81 to 0.68), lowers the youngest band's ratio to 0.879 and leaves men's calibration at 0.73. It stays excluded.
- The four-fifths screen is a heuristic that triggers a review, not a legal test, and the data's jurisdiction is not disclosed. Only sex and age can be tested; other protected characteristics are not in the data. The smallest group has 12,580 test applications, so the intervals above are narrow.

### 8.5 What Compliance must decide

1. Approve the excluded-attribute list (section 4.4) and the "testing only" use of sex, age and income type.
2. Decide which standard applies to the calibration gaps for men and 18-24-year-olds (ratio 0.73): accept and monitor, or require a remedy, and which remedies are lawful in the lender's jurisdiction. Most remedies that use sex or age directly would not be.
3. Decide whether inputs that carry age information (proxy AUC 0.84) need an input-by-input business justification or a search for less discriminatory alternatives.
4. Confirm that employment status stays excluded (recommended).
5. Approve the decline-reason wording (the labels in src/features.py) for adverse-action notices. Hashed rejection and cancellation codes cannot be shown as text, and the champion's reason codes need the fix in section 7.4.
6. Set the cadence and thresholds for fairness monitoring. Proposed: quarterly, with the four-fifths screen for approval rates; the threshold for calibration gaps follows from decision 2.

## 9. Limitations and known risks

| # | Limitation or risk | Evidence | What it means | Mitigation (owner) |
|---|---|---|---|---|
| 1 | Booked loans only; no reject inference | All 1,526,659 loans were approved by the old policy | PD unproven for past rejects; loosening the cut-off cannot be evaluated | Below-cut-off test of about 589 loans, expected net loss about 2.6M CU (Credit Policy, Finance) |
| 2 | The champion is a rebuilt stand-in for the incumbent | The incumbent model is not in the data ([assumptions.md](assumptions.md), P1) | If the incumbent is stronger, the challenger's uplift is overstated | Compare against the production scorecard in the champion/challenger test (Model Risk) |
| 3 | PD level drifts with the base rate | Calibration ratio 0.90 on the test quarter, 1.34 to 1.66 by month in the monitoring window | PD levels are wrong when the base rate moves; the approval rate under the rule moves with them | Recalibrate on the latest mature vintage before go-live; monthly calibration monitoring (Model Validation) |
| 4 | Undisclosed target definition and horizon | Home Credit does not publish them | Cannot be aligned to a 12-month default definition; recent vintages may be immature | Confirm the definition with the data owner; out of scope for provisioning and capital (Risk Analytics) |
| 5 | Residual look-ahead in long-window repayment summaries | Measured at decision + 14 days; at most about 0.01 IV per field (notebook 02) | Slight optimism in those inputs | Re-extract them as of the decision date and re-test (Data engineering) |
| 6 | Challenger complexity | Train Gini 0.751 vs validation 0.582; no monotone constraints; one fit, one seed, no tuning | Harder to challenge than a scorecard; an input's effect can change direction across its range | Sensitivity runs and direction checks in validation (section 11.1); consider monotone constraints on inputs with an expected direction (Risk Analytics) |
| 7 | Reliance on inputs that moved | Employment years (largest input, 6.5% of impact): CSI 0.86 in May 2020 when capture collapsed. Loan term (second largest): CSI up to 0.23. Bureau inputs: PSI 0.12 to 0.13 from train to test (early-2019 collection gap) | A data-capture break shifts PDs without any change in applicant risk | Feature CSI monitoring; data-capture controls on employment start date (Risk Analytics, Data engineering) |
| 8 | Weak segment: new to lender | Gini 0.421 vs 0.588 for existing clients; 17.6% of test loans | Less separation of good and bad among new clients | Segment-specific cut-off or scorecard (Risk Analytics) |
| 9 | Cash loans under-predicted | Calibration ratio 0.77 | Little effect at the 25.0% break-even (99.6% approved); matters for any tighter cut-off | Recalibration by product (Risk Analytics) |
| 10 | Calibration gaps by sex and age; proxies | Ratio 0.73 for men and for 18-24; proxy AUC 0.84 for age 50+ | Fair-lending exposure | Compliance decisions (section 8.5) |
| 11 | Champion scores missing values as average risk | 14 of 16 variables have missing values; their missing bins' own WOE ranges from −0.106 to +0.347, but each scores 37.24 points (WOE 0). Example: "Days since last rejection" is missing (no rejection on record) for 53.6% of training loans, with a 2.11% bad rate, yet scores below the best bin | Some signal lost; applicants with no rejection on record score below some who were rejected | Refit with the missing bins' own WOE if the scorecard stays in use (Risk Analytics) |
| 12 | Champion reason-code defect | Stored first reason correct for 17.0% of sampled applications (section 7.4) | Wrong adverse-action reasons if used | Fix and regenerate before any use (Risk Analytics) |
| 13 | Economics are assumptions | Margins, LGD and EAD set the break-even PDs. Margins at the low end of their range give a 75.7% approval rate under the rule; at the high end, 95.7% | Money figures move with them; the ranking of the two models does not | Finance sign-off; sensitivity in notebook 04 (Finance) |
| 14 | Price information still present | Interest-rate and campaign fields excluded, but amount, term and payment reflect pricing choices ([assumptions.md](assumptions.md), P4) | The model partly learns from the old pricing | Re-check if pricing starts to follow this model's PD (Credit Policy) |
| 15 | Explanations are associations | SHAP and points describe the model, not the world | Reasons must not be presented as causes | Reason wording reviewed by Compliance |

## 10. Monitoring plan

### 10.1 What is monitored

| Metric | Definition | Frequency | Investigate | Act | Owner |
|---|---|---|---|---|---|
| Score PSI | PD distribution vs training-window deciles | Monthly | 0.10 or more | 0.25 or more | Risk Analytics |
| Feature CSI | The 12 largest challenger inputs by SHAP, vs the training window; missing values get their own bin | Monthly | 0.10 or more | 0.25 or more | Risk Analytics |
| Approval rate under the rule | Share approved, by product | Weekly | ±3 pp vs plan | ±5 pp | Credit Policy |
| Early delinquency | Share of a vintage 30+ days past due at month 3 on book, vs the share expected for its PDs. Not in this dataset | Monthly | +20% vs expected | +40% | Risk Analytics |
| Calibration ratio | Mean PD ÷ observed bad rate, mature vintages | Monthly | Outside 0.8 to 1.25 | Outside for two months in a row | Model Validation |
| Gini | Mature vintages | Quarterly | 5 points below validation (0.582) | 10 points below | Model Validation |
| Overrides | Override rate, and bad rate of overridden loans | Monthly | Over 5% of decisions | Override bad rate above that of model-approved loans | Credit Policy |
| Review-tier hit rate | Bads found ÷ cases reviewed | Monthly | 25% below the assumption | Re-run the review grid with the measured rate (notebook 04, section 7) | Underwriting Operations |
| Fairness | Approval-rate ratio, bad rate and calibration by sex and age band | Quarterly | Ratio below 0.80 | Compliance decides | Compliance |

Sources: [notebooks/04_threshold_and_strategy.ipynb](../notebooks/04_threshold_and_strategy.ipynb) section 10 and [02_metric_definitions.md](02_metric_definitions.md).

### 10.2 Back-test on the April to October 2020 (COVID) period

The plan was run over the monitoring window as if the challenger had gone live in April 2020 (`monitoring_monthly.parquet`, `csi_flags.parquet`). The test months are shown for comparison.

| Month | Loans | Bad rate | Mean PD | Calibration ratio | Gini | Score PSI | Approval rate under the rule |
|---|---|---|---|---|---|---|---|
| Jan 2020 (test) | 86,750 | 4.08% | 3.82% | 0.94 | 0.586 | 0.001 | 91.0% |
| Feb 2020 (test) | 75,183 | 4.68% | 4.06% | 0.87 | 0.584 | 0.006 | 90.9% |
| Mar 2020 (test) | 60,748 | 4.56% | 4.07% | 0.89 | 0.560 | 0.008 | 90.2% |
| Apr 2020 | 8,289 | 2.16% | 3.37% | 1.56 | 0.533 | 0.029 | 91.3% |
| May 2020 | 28,725 | 2.21% | 3.16% | 1.43 | 0.604 | 0.083 | 91.9% |
| Jun 2020 | 45,962 | 2.45% | 3.28% | 1.34 | 0.591 | 0.059 | 92.5% |
| Jul 2020 | 28,912 | 2.28% | 3.36% | 1.47 | 0.605 | 0.044 | 92.7% |
| Aug 2020 | 50,831 | 1.96% | 3.24% | 1.66 | 0.626 | 0.071 | 92.3% |
| Sep 2020 | 61,905 | 2.15% | 3.36% | 1.56 | 0.610 | 0.051 | 92.4% |
| Oct 2020 (to 5 Oct) | 8,592 | 2.20% | 3.42% | 1.55 | 0.649 | 0.054 | 92.2% |

Findings:
1. **Score PSI did not flag the shift.** The challenger's PSI stayed below 0.10 in every month (highest 0.083, May 2020). The champion's PSI crossed 0.10 in six of the seven months (highest 0.146, August 2020).
2. **The outcome moved a lot.** The bad rate halved, and predicted PDs ran 34% to 66% above actual (calibration ratio 1.34 to 1.66). That is outside the 0.8 to 1.25 band in all seven months, but the alert can only be computed once those vintages' outcomes mature, months later.
3. **Ranking held.** Monthly Gini stayed between 0.533 and 0.649 and never fell more than 5 points below validation. The lowest month (April 2020, 0.533 on 8,289 loans) is just above the alert line of 0.532.
4. **The approval rate under the rule barely moved:** 91.3% to 92.7%, against 90.2% to 91.0% in the test months. With PDs running high, the rule declines more applicants than the economics justify; the size of that effect was not measured.
5. **Feature CSI caught a data-capture break at once.** Years with current employer reached a CSI of 0.27 in April and 0.86 in May 2020, when the field's fill rate collapsed, and stayed above 0.10 in all seven months. Smaller flags: length of application history (July to October, highest 0.12), monthly payment (July and August, 0.12) and payment-to-income (August, 0.13). Loan term crossed 0.10 in nine months, including two training months (March and October 2019): it moves with the product mix, so it needs a seasonal or product-level reference to avoid false alarms.
6. **Lesson.** Input stability alone would have missed this change. The plan pairs PSI and CSI with calibration on mature vintages and an early-delinquency measure (30+ days past due at month 3) to shorten the lag. The lower bad rate after April mixes COVID-period measures, the lender's own tightening and possibly immature outcomes. It is not evidence that the model is too conservative, and any cut-off change should wait for mature vintages.

## 11. Validation and approval checklist

### 11.1 What Model Risk should re-perform

| # | Check | How | Developer's result to reproduce |
|---|---|---|---|
| 1 | End-to-end rebuild | `make all` from the raw files; compare [reports/metrics.json](../reports/metrics.json) | Same numbers (fixed seed 42) |
| 2 | Reconciliation | `sql/dq/dq_01`, `dq_02`; notebook 02 section 3.1 | 1,526,659 loans; 47,994 defaults; 0 key violations; window counts as in section 3.4 |
| 3 | Point-in-time build | `sql/dq/dq_04`, `dq_05`; review the rules in sql/02 and sql/03; trace a sample of loans back to the raw tables | Match rates of 90.1% at the decision date vs 96.7% at +14 days and 98.4% at +21 days; 144,679 post-decision previous-application rows removed |
| 4 | Leakage ablation | Notebook 02 section 3.4 | Test Gini 0.588 (as provided), 0.585 (decision-time inputs), 0.578 (point-in-time); profit gap 0.3% |
| 5 | Feature decisions | [feature_inclusion_log.csv](feature_inclusion_log.csv) against the SQL | 294 columns: 41 kept, 27 rebuilt, 223 dropped, 3 fairness-only; catalog check passes |
| 6 | Scorecard build | Refit from `fit_scorecard`; compare the selection log | 16 variables; all coefficients negative |
| 7 | Challenger build and sensitivity | Refit with seed 42; then other seeds and a more regularised set-up (section 6.2) | 963 rounds; validation Gini 0.582. The sensitivity runs have not been done |
| 8 | Rank-ordering and calibration | Recompute from `data/processed/predictions.parquet` | Section 6.1; test calibration slope 0.99 (challenger) and 0.95 (champion) |
| 9 | Reason codes | Challenger: base value plus SHAP equals raw log-odds. Champion: points by bin add up to the score | Largest difference 3 × 10⁻¹⁴ (SHAP) and 0.0 points (champion); then confirm the fix in section 7.4 |
| 10 | Direction of effects | Compare each input's SHAP pattern with the expected direction in src/features.py | Not yet done by the developer |
| 11 | Fairness and proxies | Notebook 04 section 8; `proxy_strength` in src/fairness.py | Sections 8.1 to 8.3 |
| 12 | Economics | config.yaml, [assumptions.md](assumptions.md), notebook 04 section 12 | Break-even PDs 25.0%, 14.3%, 7.7% |
| 13 | Implementation parity | Score a sample through the production feature build and the saved artefacts; check how unseen categorical levels are handled (they become missing) | Identical PDs and reasons |
| 14 | Monitoring | Recompute `monitoring_monthly` and `csi_monthly` | Section 10.2 |

### 11.2 Conditions before production use

1. Recalibrate the challenger's PD on the most recent mature vintage and record the new Platt parameters.
2. Finance signs off margins, LGD and EAD, because the break-even PDs depend on them.
3. Compliance takes the decisions in section 8.5.
4. Production parity: the decision-time feature build reproduces sql/01 to sql/05, and PDs and reasons match the artefacts on a test sample.
5. Monitoring runs from the first decision: PSI and CSI, approval rate, calibration on mature vintages, early delinquency (30+ days past due at month 3), overrides, review hit rate and fairness.
6. The decision rule for the champion/challenger test (bad rate, approval rate, profit) is written down before the test starts.
7. A data-capture control on employment start date, the source of the largest input.
8. If the scorecard's reasons are to be shown to anyone, the fix in section 7.4 first.

### 11.3 Sign-offs

| Function | Signs off | Status |
|---|---|---|
| Model Risk / Validation | The models, this card and the conditions in 11.2 | Not yet signed |
| Compliance | Excluded attributes, fairness results, decline-reason wording | Not yet signed |
| Finance | Margins, LGD and EAD (the cost matrix) | Not yet signed |
| Underwriting Operations | Review capacity (5% of applications, 3,711 a month) and logging of review outcomes | Not yet signed |
| Head of Credit Policy | Cut-offs, the three tiers and the champion/challenger test design | Not yet signed |

### 11.4 Inconsistencies found in other documents while preparing this card

1. [notebooks/03_modeling.ipynb](../notebooks/03_modeling.ipynb), TL;DR, calls the champion an "18-variable scorecard". 18 is the selection cap; the fitted scorecard has 16 variables.
2. The same notebook's class-imbalance appendix mentions 33,000 defaults in the training window. The training window has 24,564; 33,048 is training plus validation.
3. [notebooks/01_data_audit.ipynb](../notebooks/01_data_audit.ipynb), decision table, says bureau window differences end 30 days before the decision. The implementation ([sql/02](../sql/02_stg_static.sql)) says they end 16 days before.
4. A monitoring chart title in notebook 04 says score PSI stayed below the investigate line through the COVID months. That holds for the challenger, not for the champion (0.108 to 0.146 from May to October 2020).

## 12. Change log

| Version | Date | Change | By |
|---|---|---|---|
| 1.0 | 2026-11-03 | First version. Champion (16 variables) and challenger (963 trees) fitted on Jan to Oct 2019, calibrated on Nov to Dec 2019, evaluated on the out-of-time test (Jan to Mar 2020) and back-tested on Apr to Oct 2020. Submitted for validation, with the champion reason-code defect (section 7.4) open | Credit Risk Analytics |

Development decisions taken before version 1.0 (evidence in the notebooks, the SQL headers and the feature log):
- History features rebuilt point-in-time after the 14-day snapshot offset was found (notebooks 01 and 02).
- Interest-rate and marketing-campaign fields excluded as outputs of the lender's own pricing and targeting.
- Columns collected only from mid-2019 dropped, because their missing values encode the calendar period.
- No resampling or class weights (section 5.4).
- The full January to October 2019 training window kept (section 5.5).
- Employment status tested as an input and kept out (section 8).
