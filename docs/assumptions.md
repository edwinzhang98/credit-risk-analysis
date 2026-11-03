# Assumptions log

One line per assumption: what we assume, why, and how sensitive the answer is to it. Business assumptions live in `config.yaml` and can be changed in the dashboard.

## Data and population

| # | Assumption | Source / reason | If wrong |
|---|---|---|---|
| D1 | `target = 1` means the loan defaulted; the definition and horizon are Home Credit's and are not disclosed. | Kaggle competition data description | Bad rates are still comparable across policies; absolute loss levels would shift. |
| D2 | All 1,526,659 cases are booked loans approved by the historical policy. | Every case has an outcome; `sql/dq/dq_02` | Holds by construction of the data. Consequence: approval rates are simulated on the approved population (reject inference not possible). |
| D3 | `date_decision` is the moment the decision was made, so information dated after it was not available to the lender. | Column name and data dictionary | If the real decision happened up to 14 days later, our point-in-time rules are stricter than necessary and the model is conservatively under-powered, not leaky. |
| D4 | The history snapshot fields were computed about 14 days after `date_decision`. | `sql/dq/dq_04`, `sql/dq/dq_05` (90.1% match at the decision date, rising to 92.5%, 96.7% and 98.4% for windows ending 7, 14 and 21 days after it; no event date is more than 14 days after the decision, the only later dates being two scheduled due dates) | Drives the point-in-time rebuild; see `03_data_quality_checks.md`. |
| D5 | Money is in the dataset's undisclosed local currency ("CU"). | Not documented by Home Credit | Relative results (%, pp) are unaffected; absolute CU figures are illustrative. |
| D6 | The loan amount at origination is `credamount_770A` (loan amount or card limit). | Data dictionary | Revolving limits overstate exposure for card products (13% of loans); covered by the EAD assumption. |

## Policy set-up

| # | Assumption | Source / reason | If wrong |
|---|---|---|---|
| P1 | The incumbent production model is a logistic-regression scorecard. We rebuild one on the same data and call it the champion. | Industry standard for consumer-lending application scores; the real incumbent is not in the data (the only external score covers 3.7% of loans). | If the real incumbent is stronger, the challenger's uplift is overstated. A scorecard with the 18-variable cap lifted (23 variables, same rules) reaches a test Gini of 0.490 against 0.462, closing 24% of the gap to the challenger's 0.578 (`notebooks/03_modeling.ipynb`, appendix). |
| P2 | Time windows: train 2019-01..10, validation 2019-11..12, out-of-time test 2020-01..03, monitoring 2020-04..10 (October 2020 covers 1 to 5 October only). | Strict time order: no random split is used to fit, calibrate or test the credit models (the only one, 70/30 on a 200,000-loan sample of the training window, is in the fair-lending proxy check, which predicts sex and age 50 or over, not default). Nothing is fitted, calibrated or selected on loans after the April 2020 break, though the input review did look at later months (P7). From March to April 2020 volume fell about 86% (it was back to March's level by September) and the bad rate halved in one step. | Headline numbers describe the quarter before the break. After it, ranking held but predicted PDs ran 34% to 66% above actual (P3, P7). |
| P3 | Both models' PDs are recalibrated on the validation window (Platt scaling on November to December 2019: two months, bad rate 3.51%). | Cut-offs are set on PD, so PDs must be comparable and roughly calibrated. | The level drifted, the ranking did not: PDs ran 6% to 18% below actual by month in January to March 2020 (bad rate 4.41%) and 34% to 66% above it from April 2020 (both models); the challenger's calibration slope on the test quarter is 0.99. Recalibrate on the latest mature loans before go-live; the calibration ratio is monitored monthly. |
| P4 | Interest rate and marketing-campaign fields are outputs of the lender's own pricing and targeting, not applicant information, and are excluded from both models. | They encode the incumbent model's view (risk-based price tiers, pre-approved offers); using them would make the new model copy the old one and become circular once prices follow the new score. | Loses some predictive power; the loan amount, term and payment are still used, so price information is not fully removed (documented in the model card). |
| P5 | The development window starts in January 2019 although some bureau enquiry data was not collected for about 45% of January applications. | Chosen on the validation window (`notebooks/03_modeling.ipynb`, appendix): challenger Gini 0.582 starting in January 2019 vs 0.579 (March) and 0.575 (June). The out-of-time test only confirms it (0.578, 0.577, 0.572). Bureau inputs carry about 5% of the model's impact. | Monitored through feature stability (CSI). |
| P6 | Review outcomes are modelled as expected values (a reviewer declines a fixed share of bad and of good applicants), not simulated case by case. | No review data exists; expected values keep results reproducible. | The value of the review tier moves with the reviewer catch rate: +1.8M to +31.7M CU a quarter for catch rates of 20% to 60%, with 10% of good applicants declined (sensitivity grid in notebook 04). |
| P7 | The monitoring back-test (April to October 2020) is not blind. | Two employment fields (`empl_industry_691L`, `empl_employedtotal_800L`) were dropped partly because their collection stopped in June 2020, inside the monitoring window (`docs/feature_inclusion_log.csv` also cites later-month coverage or PSI for other dropped fields), and the inputs already shifting between training and test (notebook 02, PSI > 0.10: five bureau-enquiry inputs, plus the last-reject-reason category, which is on the list anyway as a categorical input) were added to the CSI list with that knowledge. Acceptable for the production design: a model should not depend on fields the lender has stopped collecting, and a shift seen before go-live belongs on the monitoring list. | The back-test is illustrative. It cannot show what the two fields would have done to the score, and five of its 12 CSI alerts (`csi_flags.parquet`) are the bureau-enquiry inputs added this way (highest 0.37, from December 2019). |

## Unit economics (per currency unit of loan amount)

| # | Assumption | Value (range tested) | Source / reason |
|---|---|---|---|
| E1a | Net lifetime margin of a repaid **cash loan** (CAL; = cost of declining a good cash-loan applicant) | **20%** (12% to 28%) | Loan terms in the data (training window): median contractual rate 42% a year and median term 24 months, so interest over the full schedule is a median 49% of principal (amount-weighted 64%). Less ~25% of that for early repayment, ~7% funding cost (6% a year on an average balance of ~60% for ~2 years) and ~5% operating and acquisition cost leaves about 25%; the base case takes 20% to stay on the conservative side. |
| E1b | Net lifetime margin of a repaid **point-of-sale loan** (COL) | **5%** (2% to 9%) | Median contractual lifetime interest 12.5% of principal (same basis as E1a) and 42% of these loans are 0%-interest promotions (income then comes from merchant subsidies, not in the data). Less early repayment, ~3% funding and ~4% operating cost, plus an assumed ~2% merchant and insurance income. |
| E1c | Net lifetime margin of a repaid **revolving** account (REL) | **10%** (5% to 15%) | No interest rate in the data (99.8% missing) and the amount is the credit limit; mid-point assumption. |
| E2 | Exposure at default as a share of the loan amount | **80%** (70% to 100%) | Instalment loans usually default after some repayments; revolving limits are usually close to fully drawn at default. Assumption. |
| E3 | Loss given default on that exposure, after collections and recoveries | **75%** (60% to 90%) | Typical range for unsecured consumer credit; no recovery data in the dataset. |
| E4 | Cost of approving a bad (E2 × E3) | **60%** of the loan amount | Derived |
| E5 | Break-even PD per product = margin ÷ (margin + 60%) | **cash 25.0% · revolving 14.3% · point-of-sale 7.7%** | Derived; declining is worth it only above the product's break-even (see `02_metric_definitions.md`). One rule, "approve when expected profit is positive", therefore prints as three PD cut-offs. |
| E6 | Interest or fees collected before default are ignored. | Conservative | Slightly overstates the cost of a bad loan. |
| E7 | The margin assumptions are the largest source of uncertainty in the money figures. | Low and high ends of the ranges above | They move the break-even PDs more than the LGD and EAD ranges do (notebook 04, section 2). The cost-based rule's gain over today's policy is 56.6M to 147.7M CU a quarter across the margin range (`economics_sensitivity.parquet`), against a 95% sampling interval of 86.0M to 98.7M CU around the base case's 92.3M. The threshold simulator recomputes the money figures for any margin, EAD and LGD. |

## Manual review (three-tier policy)

| # | Assumption | Value | Source / reason |
|---|---|---|---|
| R1 | Cost per manual review | **300 CU** (~1% of the median loan; ~20 to 30 minutes of an underwriter's time) | Assumption; to be replaced with the operations team's cost per case. |
| R2 | Share of bad applicants a reviewer declines | **40%** | Assumption; no review outcomes in the data. Must be measured from review logs before relying on the review tier. |
| R3 | Share of good applicants a reviewer declines anyway | **10%** | Assumption (document checks, unreachable applicants). |
| R4 | Review capacity | **5% of monthly applications** (3,711 a month on booked-loan volume) | Assumption; to be confirmed with underwriting operations. It binds: about 5,988 applications a month would be worth reviewing, so the 3,711 where review adds the most are kept. |

## Fair lending

| # | Assumption | Source / reason |
|---|---|---|
| F1 | Never used as model inputs: sex, age, marital or family status, number of children and dependents, education, language, profession, income type (it contains pension and disability categories), addresses, zip codes and districts, relationship and role fields. | Fair-lending practice (e.g. US ECOA / Regulation B protected characteristics; EU guidance treating credit scoring as high-risk AI). The data's jurisdiction is not disclosed, so we apply the stricter common standard. |
| F2 | Three of the 294 raw columns are kept only for fair-lending tests, never as model inputs: sex and birth date (age band at decision), to test the policy (approval-rate ratio, bad rate and calibration by group; proxy check), and income type, to test whether adding employment status closes the calibration gaps (it does not). | Standard disparate-impact testing; decision `fairness_only` in `docs/feature_inclusion_log.csv` |
| F3 | Four-fifths screen: a group's approval rate below 80% of the most-approved group's rate is flagged for review. | Common screening heuristic, not a legal test. |
