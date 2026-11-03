# Assumptions log

One line per assumption: what we assume, why, and how sensitive the answer is to it. Business assumptions live in `config.yaml` and can be changed in the dashboard.

## Data and population

| # | Assumption | Source / reason | If wrong |
|---|---|---|---|
| D1 | `target = 1` means the loan defaulted; the definition and horizon are Home Credit's and are not disclosed. | Kaggle competition data description | Bad rates are still comparable across policies; absolute loss levels would shift. |
| D2 | All 1,526,659 cases are booked loans approved by the historical policy. | Every case has an outcome; `sql/dq/dq_02` | Holds by construction of the data. Consequence: approval rates are simulated on the approved population (reject inference not possible). |
| D3 | `date_decision` is the moment the decision was made, so information dated after it was not available to the lender. | Column name and data dictionary | If the real decision happened up to 14 days later, our point-in-time rules are stricter than necessary and the model is conservatively under-powered, not leaky. |
| D4 | The history snapshot fields were computed about 14 days after `date_decision`. | `sql/dq/dq_04`, `sql/dq/dq_05` (90.0% match at the decision date vs 96.7 to 98.4% for windows reaching past it; no date is ever more than 14 days late) | Drives the point-in-time rebuild; see `03_data_quality_checks.md`. |
| D5 | Money is in the dataset's undisclosed local currency ("CU"). | Not documented by Home Credit | Relative results (%, pp) are unaffected; absolute CU figures are illustrative. |
| D6 | The loan amount at origination is `credamount_770A` (loan amount or card limit). | Data dictionary | Revolving limits overstate exposure for card products (13% of loans); covered by the EAD assumption. |

## Policy set-up

| # | Assumption | Source / reason | If wrong |
|---|---|---|---|
| P1 | The incumbent production model is a logistic-regression scorecard. We rebuild one on the same data and call it the champion. | Industry standard for consumer-lending application scores; the real incumbent is not in the data (the only external score covers 3.7% of loans). | If the real incumbent is stronger, the challenger's uplift is overstated. |
| P2 | Time windows: train 2019-01..10, validation 2019-11..12, out-of-time test 2020-01..03, monitoring 2020-04..10. | Strict time order; the 2020-04 break (COVID) is kept out of model selection on purpose. | Headline numbers are for a pre-COVID quarter; the monitoring window shows how they degrade. |
| P3 | Both models' PDs are recalibrated on the validation window (Platt scaling). | Cut-offs are set on PD, so PDs must be comparable and roughly calibrated. | The test quarter's bad rate (4.4%) is higher than validation (3.5%), so PDs under-predict on test; reported as calibration drift. |
| P4 | Interest rate and marketing-campaign fields are outputs of the lender's own pricing and targeting, not applicant information, and are excluded from both models. | They encode the incumbent model's view (risk-based price tiers, pre-approved offers); using them would make the new model copy the old one and become circular once prices follow the new score. | Loses some predictive power; the loan amount, term and payment are still used, so price information is not fully removed (documented in the model card). |
| P5 | The development window starts in January 2019 although some bureau enquiry data was not collected for about 45% of January applications. | Tested in `notebooks/03_modeling.ipynb` (appendix): starting in March or June 2019 lowered out-of-time Gini by 0.1 to 0.6 points; bureau inputs carry about 5% of the model's impact. | Monitored through feature stability (CSI). |
| P6 | Review outcomes are modelled as expected values (a reviewer declines a fixed share of bad and of good applicants), not simulated case by case. | No review data exists; expected values keep results reproducible. | The value of the review tier scales with the assumed hit rate (sensitivity grid in notebook 04). |

## Unit economics (per currency unit of loan amount)

| # | Assumption | Value (range tested) | Source / reason |
|---|---|---|---|
| E1a | Net lifetime margin of a repaid **cash loan** (CAL; = cost of declining a good cash-loan applicant) | **20%** (12% to 28%) | Loan terms in the data (training window): median contractual lifetime interest 36% of principal (amount-weighted 50%), median term 17 months. Less ~25% for early repayment, ~5% funding cost (6% a year on an average balance of ~55% for ~1.5 years) and ~5% operating and acquisition cost. |
| E1b | Net lifetime margin of a repaid **point-of-sale loan** (COL) | **5%** (2% to 9%) | Median contractual lifetime interest 12% of principal and 42% of these loans are 0%-interest promotions (income then comes from merchant subsidies, not in the data). Less early repayment, ~3% funding and ~4% operating cost, plus an assumed ~2% merchant and insurance income. |
| E1c | Net lifetime margin of a repaid **revolving** account (REL) | **10%** (5% to 15%) | No interest rate in the data (99.8% missing) and the amount is the credit limit; mid-point assumption. |
| E2 | Exposure at default as a share of the loan amount | **80%** (70% to 100%) | Instalment loans usually default after some repayments; revolving limits are usually close to fully drawn at default. Assumption. |
| E3 | Loss given default on that exposure, after collections and recoveries | **75%** (60% to 90%) | Typical range for unsecured consumer credit; no recovery data in the dataset. |
| E4 | Cost of approving a bad (E2 × E3) | **60%** of the loan amount | Derived |
| E5 | Break-even PD per product = margin ÷ (margin + 60%) | **cash 25.0% · revolving 14.3% · point-of-sale 7.7%** | Derived; declining is worth it only above the product's break-even (see `02_metric_definitions.md`). One rule, "approve when expected profit is positive", therefore prints as three PD cut-offs. |
| E6 | Interest or fees collected before default are ignored. | Conservative | Slightly overstates the cost of a bad loan. |
| E7 | The margin assumptions are the largest source of uncertainty in the money figures; every money result is also shown for the low and high ends of the ranges above. | Sensitivity analysis in `notebooks/04` and the threshold simulator | |

## Manual review (three-tier policy)

| # | Assumption | Value | Source / reason |
|---|---|---|---|
| R1 | Cost per manual review | **300 CU** (~1% of the median loan; ~20 to 30 minutes of an underwriter's time) | Assumption; to be replaced with the operations team's cost per case. |
| R2 | Share of bad applicants a reviewer declines | **40%** | Assumption; no review outcomes in the data. Must be measured from review logs before relying on the review tier. |
| R3 | Share of good applicants a reviewer declines anyway | **10%** | Assumption (document checks, unreachable applicants). |
| R4 | Review capacity | **5% of monthly applications** | Assumption; to be confirmed with underwriting operations. |

## Fair lending

| # | Assumption | Source / reason |
|---|---|---|
| F1 | Never used as model inputs: sex, age, marital or family status, number of children, education, language, income type (it contains pension and disability categories), zip codes and districts. | Fair-lending practice (e.g. US ECOA / Regulation B protected characteristics; EU guidance treating credit scoring as high-risk AI). The data's jurisdiction is not disclosed, so we apply the stricter common standard. |
| F2 | Sex and age band are kept only to test the policy (approval-rate ratio, bad rate and calibration by group). | Standard disparate-impact testing |
| F3 | Four-fifths screen: a group's approval rate below 80% of the most-approved group's rate is flagged for review. | Common screening heuristic, not a legal test. |
