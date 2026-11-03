# 03 · Data-quality checks

**Audience:** Model Validation, Head of Credit Policy · **Data:** Home Credit 2024 training files (Kaggle), 1,526,659 booked loans, decisions 2019-01-01 to 2020-10-05 · **Code:** [`sql/dq/`](../sql/dq), [`sql/01` to `sql/06`](../sql), [notebook 01](../notebooks/01_data_audit.ipynb), [notebook 02](../notebooks/02_feature_eng.ipynb)

This is the data-quality record behind every number in the repository. Each result names what reproduces it: a check in `sql/dq/`, a feature-build file in `sql/`, an executed notebook, a field in `reports/metrics.json`, or one of the queries in the [appendix](#appendix-queries-used-in-this-document) (Q1 to Q11). "Point-in-time" means only information dated strictly before the decision date.

**How to rerun.** `make sql` builds the warehouse tables and runs the six checks. One check on its own: `python -m src.db sql/dq/dq_04_point_in_time.sql`. Notebook 01 caches the results to `data/processed/dashboard/dq_*.parquet` (local output, not in git). The appendix queries run read-only against `data/warehouse.duckdb` after `make sql`.

## 1. Summary

| # | Check | SQL file | Result | Status | Action taken |
|---|---|---|---|---|---|
| 1 | Row-count reconciliation | [`dq_01`](../sql/dq/dq_01_row_counts.sql) | 1,526,659 loans in `train_base` and `train_static_0`, one row each. Bureau (`static_cb_0`) covers 98.3% of loans, previous applications 80.0%, persons 100%. 0 orphan loans in any table. Every built table has 1,526,659 rows. | Pass | Missing child records are read as "no record", not as errors. |
| 2 | Primary keys | [`dq_02`](../sql/dq/dq_02_keys_and_target.sql) | 7 key checks, 0 violations. | Pass | None needed. |
| 3 | Target sanity | [`dq_02`](../sql/dq/dq_02_keys_and_target.sql) | Target is 0 or 1 on every row. 47,994 defaults (3.14%), equal to the dataset README. Every decision date parses. | Pass | None needed. |
| 4 | Time range and calendar consistency | [`dq_03`](../sql/dq/dq_03_time_range.sql) | 2019-01-01 to 2020-10-05. MONTH equals the decision month on every row; WEEK_NUM runs in date order. Monthly bad rate rises from 2.60% (Jan 2019) to 4.68% (Feb 2020). April 2020 volume is about 86% below March, back to March's level by September; the bad rate falls in one step to 2.16% and stays between 1.96% and 2.45%. | Issue found | Split by decision month. April to October 2020 back-tests the monitoring plan and is not used to fit or calibrate models; the back-test is not blind (section 9). |
| 5 | Missing values and coverage | [`dq_01`](../sql/dq/dq_01_row_counts.sql), Q1 | Bureau enquiry counts missing for 45.3% of January 2019 loans, 5.9% by June 2019. Employment industry and length band: 36.0% to 44.3% filled until February 2020, 1.8% to 4.0% from June 2020. Employment start date: 5.1% filled in May 2020. Training missing share of the 90 features: 0% to 60.4%. | Issue found | Missing kept as its own bin. Discontinued employment fields dropped. Bureau and employment-years features kept and monitored. |
| 6 | Value ranges and outliers | [`dq_06`](../sql/dq/dq_06_value_ranges.sql), Q3, Q4 | No impossible amounts, payments, rates or ages. Minor: 9 loans with income missing or 0, 2 with a monthly payment above the loan amount, 316 employment start dates after the decision, income top-coded at 200,000 CU, a "share" above 100% on 34,202 loans. 1,503 amounts above the 99.9th percentile. | Issue found | Ratios left missing; post-decision start dates set to missing; outliers kept; caps applied in `sql/02`. |
| 7 | Point-in-time: dates after the decision | [`dq_04`](../sql/dq/dq_04_point_in_time.sql) | 28 of 34 date fields hold values after the decision. Event dates are at most 14 days late, never more. Loans whose last rejection is dated after the decision default at 7.25% vs 4.03%. | Issue found | Dated fields never used raw: rebuilt from applications created before the decision, or dropped. |
| 8 | Snapshot timing test | [`dq_05`](../sql/dq/dq_05_snapshot_offset.sql) | The provided 30-day application count equals a recount ending at the decision for 90.1% of loans, and 92.5%, 96.7% and 98.4% for windows ending 7, 14 and 21 days after it. "Last application date" equals the latest application, post-decision ones included, for 100% of loans. | Issue found | Snapshot treated as decision + 14 days. Rebuild, drop and floor rules (section 7.4). Leak measured by ablation (section 7.7). |
| 9 | Feature roll-out breaks | Q2, Q3, Q11 | 26 `static_0` columns are empty before their roll-out date (2019-03-13 to 2019-08-29). Two kept fields change coding in August and September 2019; the last reject reason's code mix shifts from February 2019 as new codes replace old ones. | Issue found | 26 columns dropped. The two fields harmonised in `sql/02`; the reject reason kept and monitored (CSI). |
| 10 | Leakage across the time split | [`sql/01`](../sql/01_stg_base.sql), [`sql/03`](../sql/03_int_applprev_pit.sql), Q5, Q8 | Split by decision month. Minimum days since the last application: 1. Independent recounts match except at the 15-row cap. Highest training IV 0.306. No identifier or date among the inputs. | Pass | Checks in section 8; residual risks in section 9. |

The tables reconcile and the keys and target are clean. Two findings shape the model. The history snapshot was measured about 14 days after each decision, and several fields change coverage over time. Both are handled in the SQL feature build and measured. Used as provided, the snapshot would raise the out-of-time test (Jan to Mar 2020) Gini from 0.578 to 0.588. The strict point-in-time rules cost less than one Gini point against an estimate, still optimistic for the naive model, of what it could deliver at decision time (0.585).

## 2. Row-count reconciliation

Source: [`dq_01_row_counts.sql`](../sql/dq/dq_01_row_counts.sql), cached in `data/processed/dashboard/dq_row_counts.parquet`.

| Source table | Grain | Rows | Distinct loans | Share of base loans | Orphan loans |
|---|---|---:|---:|---:|---:|
| `train_base` | loan | 1,526,659 | 1,526,659 | 100.0% | 0 |
| `train_static_0` (2 files) | loan | 1,526,659 | 1,526,659 | 100.0% | 0 |
| `train_static_cb_0` | loan | 1,500,476 | 1,500,476 | 98.3% | 0 |
| `train_applprev_1` (2 files) | loan × previous application | 6,525,979 | 1,221,522 | 80.0% | 0 |
| `train_person_1` | loan × person | 2,973,991 | 1,526,659 | 100.0% | 0 |

- **Bureau (`static_cb_0`), 98.3%.** 26,183 loans have no bureau row. 23,745 of them were decided in January 2019, when 31.4% of that month's loans have no bureau row. From March 2019 the monthly gap is at most 0.5% (Q1). A missing row is read as "no bureau record": the enquiry features are missing and `cb_has_enquiry_record` is 0 ([`sql/02`](../sql/02_stg_static.sql)).
- **Previous applications, 80.0%.** 1,221,522 loans have at least one row in this table; the other 305,137 have none and are new to the lender. After the point-in-time filter (rule R1, section 7.4), 1,207,863 loans (79.1%) keep at least one application; for 13,659 loans no row is dated before the decision (Q5). The new-to-lender share falls over time: 23.0% of training loans, 22.5% validation, 17.6% test, 14.9% monitoring ([`sql/05`](../sql/05_fct_application_features.sql), final query).
- **Persons, 100%.** 2,973,991 rows: the applicant (`num_group1 = 0`) plus other persons on the application. Every loan has exactly one applicant row (section 3). Only the applicant row is read.
- **Built tables.** `stg_base`, `stg_static`, `int_applprev_pit`, `int_person_applicant`, `fct_application_features` and `abl_features_as_provided` each have 1,526,659 rows and 1,526,659 distinct loans. Notebook 02 asserts this before any modelling, so no join duplicated or dropped a loan ([notebook 02](../notebooks/02_feature_eng.ipynb), section 3.1).

Window totals ([`sql/01`](../sql/01_stg_base.sql) and [`sql/05`](../sql/05_fct_application_features.sql) final queries; notebook 02, section 3.1):

| Window | Decision months | Loans | Bads | Bad rate |
|---|---|---:|---:|---:|
| Train | 2019-01 to 2019-10 | 828,906 | 24,564 | 2.96% |
| Validation | 2019-11 to 2019-12 | 241,856 | 8,484 | 3.51% |
| Out-of-time test | 2020-01 to 2020-03 | 222,681 | 9,829 | 4.41% |
| Monitoring | 2020-04 to 2020-10 | 233,216 | 5,117 | 2.19% |
| **Total** | | **1,526,659** | **47,994** | **3.14%** |

## 3. Primary keys and target

Source: [`dq_02_keys_and_target.sql`](../sql/dq/dq_02_keys_and_target.sql), cached in `dq_keys.parquet`.

| Check | Violations | Expected |
|---|---:|---:|
| `train_base`: `case_id` unique | 0 | 0 |
| `train_static_0`: `case_id` unique across both files | 0 | 0 |
| `train_static_0`: no `case_id` in both files | 0 | 0 |
| `train_static_cb_0`: `case_id` unique | 0 | 0 |
| `train_applprev_1`: (`case_id`, `num_group1`) unique | 0 | 0 |
| `train_person_1`: (`case_id`, `num_group1`) unique | 0 | 0 |
| `train_person_1`: every loan has an applicant row (`num_group1 = 0`) | 0 | 0 |
| `train_base`: target outside {0, 1} or missing | 0 | 0 |
| `train_base`: number of defaults minus the README's 47,994 | 0 | 0 |
| `train_base`: `date_decision` not parseable | 0 | 0 |

- 47,994 defaults is the number published in the dataset README; over 1,526,659 loans it is a bad rate of 3.14%.
- Every case has a 0/1 outcome, so every case is a loan the historical policy approved and booked. Approval rates anywhere in this repository are shares of previously approved applicants; the bad rate of applicants the lender rejected is unknown (assumption D2 in [assumptions.md](assumptions.md)).
- The default definition and outcome horizon are Home Credit's and are not disclosed (assumption D1). The latest vintages may not be fully mature ([notebook 01](../notebooks/01_data_audit.ipynb), section 5).

## 4. Time range and calendar consistency

Source: [`dq_03_time_range.sql`](../sql/dq/dq_03_time_range.sql), cached in `dq_time_checks.parquet` and `dq_time_range.parquet`.

| Check | Result |
|---|---|
| First decision date | 2019-01-01 |
| Last decision date | 2020-10-05 (October 2020 holds 5 days, 8,592 loans) |
| Rows where MONTH differs from the YYYYMM of `date_decision` | 0 |
| WEEK_NUM range | 0 to 91 |
| Weeks whose WEEK_NUM order disagrees with the dates | 0 |
| Rank correlation of `case_id` with the decision date | 0.299 |

MONTH equals the decision month on every row and WEEK_NUM runs in date order, so the split can safely use MONTH (`sql/01` assigns windows from it). `case_id` is only loosely ordered in time. It is not a time index and is never used to order loans in time, to split or as a model input.

Monthly volume and bad rate (95% Wilson interval):

| Decision month | Loans | Bads | Bad rate | 95% interval | Window |
|---|---:|---:|---:|---:|---|
| 2019-01 | 75,529 | 1,963 | 2.60% | 2.49% to 2.71% | Train |
| 2019-02 | 63,064 | 1,727 | 2.74% | 2.61% to 2.87% | Train |
| 2019-03 | 69,147 | 1,850 | 2.68% | 2.56% to 2.80% | Train |
| 2019-04 | 72,012 | 2,121 | 2.95% | 2.82% to 3.07% | Train |
| 2019-05 | 64,594 | 2,132 | 3.30% | 3.17% to 3.44% | Train |
| 2019-06 | 94,398 | 2,431 | 2.58% | 2.48% to 2.68% | Train |
| 2019-07 | 97,566 | 2,679 | 2.75% | 2.65% to 2.85% | Train |
| 2019-08 | 98,741 | 2,639 | 2.67% | 2.57% to 2.78% | Train |
| 2019-09 | 98,706 | 3,359 | 3.40% | 3.29% to 3.52% | Train |
| 2019-10 | 95,149 | 3,663 | 3.85% | 3.73% to 3.97% | Train |
| 2019-11 | 115,845 | 4,132 | 3.57% | 3.46% to 3.68% | Validation |
| 2019-12 | 126,011 | 4,352 | 3.45% | 3.35% to 3.56% | Validation |
| 2020-01 | 86,750 | 3,537 | 4.08% | 3.95% to 4.21% | Test |
| 2020-02 | 75,183 | 3,520 | 4.68% | 4.53% to 4.84% | Test |
| 2020-03 | 60,748 | 2,772 | 4.56% | 4.40% to 4.73% | Test |
| 2020-04 | 8,289 | 179 | 2.16% | 1.87% to 2.50% | Monitoring |
| 2020-05 | 28,725 | 635 | 2.21% | 2.05% to 2.39% | Monitoring |
| 2020-06 | 45,962 | 1,128 | 2.45% | 2.32% to 2.60% | Monitoring |
| 2020-07 | 28,912 | 660 | 2.28% | 2.12% to 2.46% | Monitoring |
| 2020-08 | 50,831 | 994 | 1.96% | 1.84% to 2.08% | Monitoring |
| 2020-09 | 61,905 | 1,332 | 2.15% | 2.04% to 2.27% | Monitoring |
| 2020-10 | 8,592 | 189 | 2.20% | 1.91% to 2.53% | Monitoring |

**The 2019 rise.** The bad rate is 2.60% to 2.74% from January to March 2019 and 3.85% by October 2019. Volume grows from 63,064 to 75,529 loans a month (January to May 2019) to 94,398 to 98,741 (June to October) and 115,845 to 126,011 (November and December). The test quarter is the riskiest period: 4.08%, 4.68% and 4.56% in January, February and March 2020.

**The April 2020 break.** April 2020 has 8,289 loans, about 86% fewer than March (60,748); volume is back to March's level by September (61,905), and October 2020 covers 1 to 5 October only. The bad rate falls in one step to 2.16% and then stays flat, between 1.96% and 2.45%, through October 2020. Its cause is not known: it may reflect COVID-era measures, the lender's own tightening or loans too recent to have defaulted (the outcome horizon is not disclosed); the data cannot separate these (notebook 01, section 4.3), so the monitoring back-test on these months is illustrative.

**How the time split was chosen** ([config.yaml](../config.yaml), `split`):

1. By decision month only: no random split is used to fit, calibrate or test the credit models. The monthly bad rate moves from 2.60% (January 2019) to 4.68% (February 2020), so a random split would mix periods and overstate performance. The only random split is the fair-lending proxy check ([`src/fairness.py`](../src/fairness.py): 70/30 within a random sample of 200,000 training-window loans), which predicts sex and age 50 or over, not default.
2. No model is fitted, calibrated or chosen on April to October 2020 outcomes; those months back-test the monitoring plan (assumption P2). That back-test is not blind: two employment fields were dropped partly because their collection stopped in June 2020, and inputs already shifted between training and test were put on the CSI list with that knowledge (section 9).
3. The out-of-time test is the last full quarter before the break (January to March 2020). Every headline number comes from it.
4. Validation is the two months just before the test quarter (November and December 2019): early stopping and Platt calibration.
5. Training starts in January 2019 despite the early bureau gap (section 5.2), because starting in March or June 2019 lowered validation Gini (0.582 vs 0.579 and 0.575); the test quarter only confirms it (section 8, check 10).

## 5. Missing values and coverage

### 5.1 Coverage by table

| Table | Loans covered | Gap | Treatment |
|---|---|---|---|
| `static_0` | 100% | None | None needed |
| `person_1`, applicant row | 100% | Field-level gaps in employment data (5.2) | See 5.2 |
| `static_cb_0` | 98.3% | 26,183 loans, 23,745 of them decided in January 2019 | "No bureau record"; enquiry features missing |
| `applprev_1` | 80.0% (79.1% with an application before the decision) | 305,137 loans new to the lender; 13,659 with no row before the decision | Counts set to 0, other numeric fields missing, categories set to `no_history` (`sql/03`) |

### 5.2 Structural breaks over time

Coverage by decision month (Q1):

| Decision month | Loans | No bureau row | Bureau enquiry counts missing | Employment industry filled | Employment length band filled | Employment start date filled |
|---|---:|---:|---:|---:|---:|---:|
| 2019-01 | 75,529 | 31.4% | 45.3% | 38.4% | 38.9% | 38.7% |
| 2019-02 | 63,064 | 1.8% | 18.4% | 36.0% | 36.5% | 36.3% |
| 2019-03 | 69,147 | 0.0% | 18.0% | 36.4% | 36.8% | 36.6% |
| 2019-04 | 72,012 | 0.0% | 18.0% | 40.4% | 40.9% | 40.6% |
| 2019-05 | 64,594 | 0.3% | 17.1% | 39.3% | 39.8% | 39.5% |
| 2019-06 | 94,398 | 0.5% | 5.9% | 40.5% | 40.9% | 40.7% |
| 2019-07 | 97,566 | 0.2% | 6.4% | 40.2% | 40.6% | 40.4% |
| 2019-08 | 98,741 | 0.1% | 5.4% | 39.1% | 39.5% | 39.3% |
| 2019-09 | 98,706 | 0.0% | 5.8% | 40.4% | 40.9% | 40.6% |
| 2019-10 | 95,149 | 0.0% | 6.0% | 41.0% | 41.4% | 41.2% |
| 2019-11 | 115,845 | 0.0% | 5.1% | 43.8% | 44.3% | 44.1% |
| 2019-12 | 126,011 | 0.0% | 5.0% | 42.8% | 43.2% | 43.0% |
| 2020-01 | 86,750 | 0.0% | 5.2% | 43.2% | 43.7% | 43.4% |
| 2020-02 | 75,183 | 0.0% | 3.7% | 38.2% | 38.7% | 38.5% |
| 2020-03 | 60,748 | 0.0% | 3.0% | 27.9% | 28.2% | 28.1% |
| 2020-04 | 8,289 | 0.0% | 4.0% | 17.6% | 17.8% | 17.7% |
| 2020-05 | 28,725 | 0.0% | 3.9% | 5.1% | 5.1% | 5.1% |
| 2020-06 | 45,962 | 0.1% | 4.0% | 4.0% | 4.0% | 23.7% |
| 2020-07 | 28,912 | 0.0% | 3.5% | 3.7% | 3.7% | 26.4% |
| 2020-08 | 50,831 | 0.0% | 3.6% | 1.8% | 1.8% | 23.7% |
| 2020-09 | 61,905 | 0.4% | 3.7% | 2.0% | 2.0% | 22.4% |
| 2020-10 | 8,592 | 0.0% | 3.2% | 2.1% | 2.1% | 22.7% |

"Employment start date filled" is the share of loans with a usable `employment_years` (start dates after the decision are already set to missing).

**Bureau enquiry counts not collected in early 2019.** The counts are missing for 45.3% of January 2019 loans (31.4% have no bureau row at all), 17.1% to 18.4% from February to May 2019, 5.0% to 6.4% from June to December 2019 and 3.0% to 5.2% in 2020. The training-window missing share is 13.4%; in the test quarter it is 4.1%. Alongside that fall, the five bureau features have a training-to-test PSI of 0.119 to 0.126. Notebook 02 screens all 90 features this way (categories compared by share); 6 are above 0.10: these five and the last reject reason (0.145, below) (`feature_screening.parquet`; `nb02_summary.json`, `n_unstable_features`). After the training window the bureau CSI first reaches 0.10 in December 2019 or February 2020 and is above it in every month from February 2020 (maximum 0.37; `csi_flags.parquet`, `csi_monthly.parquet`). *Action:* kept, with missing as its own bin. In early 2019 that bin mixes "not collected" and "no record" (notebook 02, section 4). The training window was not shortened: starting in March or June 2019 lowered validation Gini (section 8, check 10). Bureau inputs carry 5.2% of the challenger's SHAP impact (`reports/metrics.json`, `models.group_shares`).

**Employment fields collapse after March 2020.** Industry (`empl_industry_691L`) and the self-declared length band (`empl_employedtotal_800L`) are 36.0% to 44.3% filled through February 2020, then 27.9% to 28.2% in March, 17.6% to 17.8% in April, 5.1% in May and 1.8% to 4.0% from June 2020. *Action:* both dropped (feature log, rule OTHER), partly because their collection stopped in June 2020: in production almost every applicant would fall in the missing bin. June 2020 is inside the monitoring window, so the monitoring back-test is not blind to this break (section 9). The employment start date (`empl_employedfrom_271D`, feature `employment_years`) follows the same path down to 5.1% in May 2020, then recovers to 22.4% to 26.4%. *Action:* kept. Its training-to-test PSI is 0.031, but in the monitoring back-test its CSI is above 0.10 in all 7 months from April 2020, with a maximum of 0.86 (`reports/metrics.json`, `monitoring.csi_flags`). The scorecard's score PSI moves with it, 0.108 to 0.146 from May 2020, while the challenger's stays below 0.10 (maximum 0.08; `monitoring_monthly.parquet`). It is the challenger's strongest single input (`models.top_driver`), so a capture break in this field needs a monitoring alert, not just a note. Its missing bin also stands in for income type (99.7% of retirees have no start date; feature log), one reason outcomes are tested by age band in notebook 04.

**Columns rolled out part-way through 2019.** 26 `static_0` columns in five suffix families are empty for every loan decided before their first value (Q2):

| Suffix family | Columns | First decision with a value |
|---|---:|---|
| `_4187` | 7 | 2019-03-13 |
| `_4325` | 1 | 2019-05-22 |
| `_4493` | 7 | 2019-08-13 |
| `_4499` | 4 | 2019-08-16 |
| `_4525` | 7 | 2019-08-29 |

A missing value in these columns says "decided before the roll-out", not anything about the applicant. *Action:* all 26 dropped (`sql/02` header; the feature log gives each column's reason, for example ROLLOUT, DUP or OTHER).

**Coding changes in three kept fields** (Q3, Q11):
- `maxdpdfrom6mto36m_3546853P` is missing on 6.0% to 7.2% of each month's loans from January to July 2019 although the client has a repayment history, 2.6% in August and 0% from September 2019: the source switched from "missing" to 0. *Action:* set to 0 whenever the client has a repayment history (37,356 loans; feature `max_dpd_6to36m`, `sql/02`).
- `numinstlswithdpd10_728L` (instalments paid 10+ days late): the monthly share of loans above 40 is 3.1% to 3.7% from January to July 2019 and 1.1% to 1.7% from September 2019. The monthly maximum is 226 to 330 before August 2019 and 111 to 187 from September 2019. The feature log records the 99th percentile moving from about 75 to about 43. *Action:* capped at 40 in every month (21,892 loans; feature `n_instalments_10d_late`).
- `rejectreason_755M` (feature `ap_last_reject_reason`, the reason on the client's last rejected application): the hashed codes change over time. `P94_109_143` is the last reason for 28.6% of January 2019 loans and 8.1% of March 2020 loans; three codes absent in January 2019 appear from February 2019 and are the last reason for 5.5% of February 2019 loans and 37.6% of March 2020 loans. This is the highest training-to-test PSI of the 90 features (0.145), and after the training window its CSI is above 0.10 in all 9 months from February 2020 (maximum 0.24; `csi_flags.parquet`). *Action:* kept (training IV 0.163) and monitored as a categorical input. The codes are hashed, so whether the meaning changed cannot be read from the data (section 9).

**Tax-authority block (`static_cb_0`).** Coverage moves between windows (for example `requesttype_4525192L`: 24% of training loans, 100% of validation and test, 3% of monitoring; feature log) and the response dates fall after the decision (section 7.1). *Action:* all dropped: 11 fields under rule L5 and 4 later fields of the block, empty or almost empty before April 2020, under SPARSE (feature log).

### 5.3 Missing values in the 90 model features

Missing share in the training window, from `feature_screening.parquet` (notebook 02, section 3.3):

| Group | Features | Missing share: min / median / max | Why values are missing |
|---|---:|---|---|
| Repayment history | 30 | 0.0% / 31.7% / 51.1% | No internal repayment record (22.1% of training loans); windowed fields are missing more often |
| Previous applications | 29 | 0.0% / 23.0% / 54.4% | No application before the decision (23.0% of training loans); fields about the last rejection also need a past rejection |
| Affordability | 11 | 0.0% / 23.0% / 60.4% | `employment_years` 60.4% (no start date captured); ratios that need a previous application |
| Loan terms | 11 | 0.0% / 0.0% / 14.1% | Not applicable: no goods price on 57.5% of cash loans and 10.0% of revolving loans; no fixed term on 26.6% of revolving loans |
| Credit bureau | 5 | 0.0% / 13.4% / 13.4% | Enquiry counts not collected or no bureau row (5.2) |
| Contact details | 4 | 0.0% / 0.0% / 0.0% | None |

31 of the 90 features have no missing values. Nothing is imputed. Counts are 0 where "none" is the true value. Other numeric fields stay missing, and categorical fields get `no_history`, `never_rejected` or `never_cancelled`. `ap_n_approved` and `ap_n_repaid_ontime` stay missing for clients without history, so "no history" is not merged with "history, none approved" (`sql/03` header). The scorecard keeps missing values in a separate bin but scores them at a WOE of 0, optbinning's default, so a missing value earns neutral points (every Missing bin in the notebook 03 points table, `scorecard_points.parquet`, has the same 37.24 points). Refitting it with each missing bin's empirical WOE moves its out-of-time test Gini from 0.462 to 0.464 (notebook 03, section 7; `nb03_summary.json`), so the neutral treatment does not handicap it. LightGBM handles missing values natively ([notebook 03](../notebooks/03_modeling.ipynb), sections 2 and 3.1).

## 6. Value ranges and outliers

Source: [`dq_06_value_ranges.sql`](../sql/dq/dq_06_value_ranges.sql), cached in `dq_value_ranges.parquet`. The rules cover the fields that drive money and policy.

| Rule | Loans | Action |
|---|---:|---|
| Credit amount missing or ≤ 0 | 0 | None needed |
| Credit amount above the 99.9th percentile (360,000 CU) | 1,503 | Kept; money metrics are also reported as rates |
| Monthly payment missing or ≤ 0 | 0 | None needed |
| Monthly payment greater than the credit amount | 2 | Kept and flagged here (likely revolving limits or a data error) |
| Interest rate outside [0, 1] | 0 | None needed; the rate is not a model input (rule S4) |
| Down payment greater than the goods price | 0 | None needed |
| Worst days past due (24 months) negative | 0 | None needed |
| Income missing or ≤ 0 | 9 | Ratio features left missing |
| Income above the 99.9th percentile | 0 | None found because income is top-coded (below) |
| Age at decision below 18 or above 100 (fairness attribute only) | 0 | None needed |
| Employment start date after the decision | 316 | Employment length set to missing ([`sql/04`](../sql/04_int_person_applicant.sql)) |
| Employment length above 60 years | 0 | None needed |

Further findings (Q3, Q4):

- **Income is top-coded at 200,000 CU.** 12,430 loans have a declared income of exactly 200,000 CU. That is the highest value in the data and also its 99.9th percentile, so the percentile rule cannot flag anything. It looks like a cap in the source or on the application form. If so, ratios that divide by income (payment-to-income, loan-to-income) are overstated for applicants above the cap. Income fields carry little signal (training IV 0.002 for `income_main`, 0.001 for `payment_to_income`).
- **A "share" above 100%.** `pctinstlsallpaidearl3d_427L` (share of instalments paid 3+ days early) is above 1 on 34,202 loans (3.2% of non-missing values; maximum 23.0). *Action:* capped at 1 (feature `share_instalments_early_3d`).
- **Loan amounts.** Median 35,199 CU, 99.9th percentile 360,000 CU, maximum 950,000 CU. Large loans are kept because they carry the money; every money result is also shown as a rate.
- **Count caps in `sql/02`.** Contact-sharing counts have long tails (up to 23 people on one mobile number, 728 applications on one phone). Both models see inputs through bins (WOE) or tree splits, so a cap only changes the top bin.

| Feature | Cap | Loans above the cap |
|---|---:|---:|
| `n_instalments_10d_late` | 40 | 21,892 |
| `share_instalments_early_3d` | 1 | 34,202 |
| `n_people_same_mobile` | 6 | 8,915 |
| `n_clients_same_mobile_12m` | 3 | 519 |
| `n_apps_same_phone` | 13 | 13,690 |
| `n_home_phones` | 5 | 708 |

## 7. Point-in-time and leakage

The question for every input: was it known on the decision date? This section shows that part of the source snapshot was not, what was done about it, what remains, and what the leak would have done to the results.

### 7.1 Evidence 1: dated fields after the decision

[`dq_04_point_in_time.sql`](../sql/dq/dq_04_point_in_time.sql) unpivots every date column (34 fields in 4 tables). It compares each value with the loan's decision date and reports the share after the decision, the largest gap, and the bad rate of loans with the date after vs on or before the decision.

- 28 of the 34 date fields hold at least one value after the decision.
- Event dates are at most 14 days after the decision, never more. The only larger gaps (47 days) are two scheduled future due dates (`firstnonzeroinstldate_307D`, `firstdatedue_489D`): plans, not events.
- Four tax-authority date fields are after the decision for 99.6% to 100% of values. The feature log finds 94.8% of `responsedate_1012D` and 98.6% of `responsedate_4527233D` exactly 14 days after it. A fixed lag of exactly 14 days points to a systematic extraction date, not to client behaviour (notebook 01, section 4.5).
- For the fields below, loans with an event dated after the decision default more often:

| Table | Field | Values | After the decision | Max days after | Bad rate if after | Bad rate if on or before |
|---|---|---:|---:|---:|---:|---:|
| `static_0` | `lastapplicationdate_877D` | 1,221,522 | 9.4% | 14 | 4.99% | 3.21% |
| `static_0` | `firstclxcampaign_1125D` | 667,445 | 5.5% | 14 | 4.96% | 2.32% |
| `static_0` | `lastdelinqdate_224D` | 548,684 | 5.3% | 13 | 7.28% | 4.30% |
| `static_0` | `lastrejectdate_50D` | 757,613 | 5.1% | 14 | 7.25% | 4.03% |
| `static_0` | `datelastunpaid_3546854D` | 639,000 | 4.4% | 13 | 7.33% | 4.12% |
| `static_0` | `lastapprdate_640D` | 1,084,618 | 3.2% | 14 | 4.88% | 3.19% |
| `static_0` | `maxdpdinstldate_3546855D` | 700,659 | 1.8% | 13 | 6.52% | 3.94% |
| `static_0` | `lastactivateddate_801D` | 1,073,072 | 1.4% | 14 | 4.86% | 3.22% |
| `applprev_1` | `creationdate_885D` (rows) | 6,525,913 | 2.1% | 14 | 5.33% | 3.70% |
| `applprev_1` | `approvaldate_319D` (rows) | 3,515,685 | 1.1% | 14 | 5.02% | 2.70% |
| `applprev_1` | `firstnonzeroinstldate_307D` (rows, scheduled) | 5,873,497 | 3.6% | 47 | 6.17% | 3.66% |

For `applprev_1` the counts are rows, not loans, and each row carries its loan's outcome. These are associations in approved loans: clients who apply again and are rejected, or fall behind on another contract, in the two weeks after the decision default more often. The lender could not have seen any of that at the decision.

### 7.2 Evidence 2: when the snapshot was taken

`applications30d_658L` is "applications in the last 30 days". [`dq_05_snapshot_offset.sql`](../sql/dq/dq_05_snapshot_offset.sql) recounts each client's applications from the previous-applications table over 30-day windows that end at the decision date and 7, 14 and 21 days later, and measures how often the recount equals the provided value. It also compares `lastapplicationdate_877D` with the latest application in the table, with and without the point-in-time filter.

| Test | Match rate |
|---|---:|
| 30-day count = recount over 30 days ending at the decision date (point-in-time) | 90.1% |
| 30-day count = recount ending at decision + 7 days | 92.5% |
| 30-day count = recount ending at decision + 14 days | 96.7% |
| 30-day count = recount ending at decision + 21 days | 98.4% |
| Last application date = latest application, all rows including those after the decision | 100.0% |
| Last application date = latest application created before the decision | 90.4% |

Other snapshot fields tell the same story ([feature log](feature_inclusion_log.csv), recounts against the previous-applications table):
- `numrejects9m_859L` equals the count of rejected applications in the 9 months up to decision + 14 days for 99.3% of loans, vs 95.2% for the 9 months up to the decision.
- `numcontrs3months_479L` equals a count ending at decision + 14 days for 94.7% of loans, vs 88.1% for the point-in-time window.
- `lastst_736L` equals the status of the latest application over all rows, including those after the decision, for 99.0% of loans.

### 7.3 Interpretation

The history snapshot was taken about 14 days after the decision date. Four facts support this:
1. No event date is ever more than 14 days after the decision (7.1).
2. In the two main tax-authority response-date fields, 94.8% and 98.6% of values sit exactly 14 days after the decision.
3. The 30-day count matches better as the window end moves past the decision, and "last application date" equals the latest application, post-decision ones included, for 100% of loans.
4. The previous-applications table holds no application dated more than 14 days after the decision (Q5).

The match keeps improving to 98.4% at +21 days. With no application later than +14 days in the table, a window ending at +21 days cannot pick up later applications. It differs from the +14 window only in where it starts and in including day 14 itself. The test therefore shows that the field was measured at least 14 days after the decision; it does not pin the exact day. Working assumption: snapshot = decision + 14 days (assumption D4).

What the data cannot tell is why: a pipeline lag or a mislabelled decision date. If the decision was in fact taken 14 days later than recorded, the rules below are stricter than needed and the model is somewhat weaker than it could be, but it does not leak. The reverse mistake would be leakage, so the conservative side was taken (assumption D3; notebook 01, section 5).

### 7.4 Rules applied

**Previous applications** ([`sql/03_int_applprev_pit.sql`](../sql/03_int_applprev_pit.sql)):

| Rule | What it does | Effect and evidence |
|---|---|---|
| R1 | Uses only applications created strictly before the decision date | Removes 144,679 of 6,525,979 rows (2.2%) dated on or after the decision and the 66 rows with no creation date; 13,659 loans keep no row (Q5). |
| R2 | Uses only the 15 most recent pre-decision applications | The source keeps at most 20 rows per loan, post-decision rows included (34,061 loans are at that cap). A client who applied again after the decision would show fewer pre-decision rows. With 15 rows the window is unaffected for all but 171 loans (Q5). |
| R3a | "Approved" = approval date before the decision; "rejected" = status D; "cancelled" = status T | The status field is captured at the snapshot; D and T are fixed at application time. Approval falls on the creation day (feature log: 95th percentile of the lag is 0 days). |
| R3b | Worst days past due (DPD) of a previous contract: as provided if the contract closed before the decision (status K, H or Q and last payment or scheduled end before the decision); otherwise reduced by 14 days and floored at 0 | DPD grows by at most one day per day, so the result is a guaranteed lower bound of what was known at the decision. Evidence that the raw value leaks: on contracts created before the decision whose first instalment falls after it, 3.7% of rows with a DPD value (858 of 22,965) show 1 to 14 days, and those loans default at 13.99% vs 4.16% for rows with 0 days (Q6). Training IV of the worst-DPD feature: 0.219 computed naively (all rows, raw DPD) vs 0.175 point-in-time (Q9). |
| R3c | Does not use snapshot balances (current debt, outstanding debt, actual DPD, card balances) | Exposure at the decision is rebuilt from the instalments of contracts approved before and not closed before the decision (`ap_sum_open_annuity`). |
| R4 | Never reads education, family state, district, number of children or profession | Fair-lending rule, not a timing rule. |

**Snapshot fields** ([`sql/02_stg_static.sql`](../sql/02_stg_static.sql), [`sql/04`](../sql/04_int_person_applicant.sql), [feature log](feature_inclusion_log.csv)). Of the 294 raw columns reviewed, 41 are kept as provided, 27 rebuilt point-in-time, 223 dropped and 3 kept only for fair-lending tests, never as model inputs.

| Rule | What it does | Effect and evidence |
|---|---|---|
| S1 | Dated "last event" fields and their companions are never used; they are rebuilt from previous applications | 9 `static_0` fields rebuilt: last application, rejection and approval dates (as days since), last status, last reject and cancel reasons, last rejected and approved amounts, and `numrejects9m_859L` (as rejections in the last 90 and 365 days). Fields with no point-in-time source are dropped, not blanked (7.5). |
| S2 | Snapshot aggregates with a look-back under 6 months and "current status" fields are not used | 49 fields dropped under rule L4, for example `applications30d_658L`, `maxdpdlast3m_392P`, `currdebt_22A`, `actualdpdtolerance_344P`. 14 days is up to 47% of a 30-day window. 9 fields with windows of 6 months or more are kept (7.6). |
| S3 | Tax-authority fields are not used | 11 fields dropped (rule L5): they arrive after the decision (7.1) and their coverage moves between windows (5.2). |
| S4 | Interest-rate and marketing-campaign fields are not used | 5 fields dropped (rule PROCESS). They are outputs of the lender's own pricing and targeting and would teach the new model the old model's decisions. Two campaign dates also fall after the decision on 5.5% and 36.0% of values. |
| S5 | Columns rolled out during 2019 are not used | 26 columns (5.2). |
| S6 | DPD floor on the seven `static_0` days-past-due maxima | If the client's last delinquency started after the decision and the maximum is no larger than the days between that start and decision + 14, the maximum could have been reached entirely after the decision. It is then set to 0, a lower bound. This changes the 24-month maximum for 17,753 loans (1.2%) and at least one of the seven fields for 21,534 loans (1.4%). The 17,753 loans default at 5.57% vs 3.12% for the rest (Q6). Training IV falls by 0.003 to 0.016 per field (7.6). |
| S7 | Stability rules | `max_dpd_6to36m` set to 0 instead of missing when the client has history (37,356 loans); `n_instalments_10d_late` capped at 40 (5.2). |
| S8 | Bureau enquiries are used only as window differences | Measured at the snapshot, the provided "30-day" count covers [decision − 16 days, decision + 14 days), not the 30 days before the decision. The windows nest (30 ≤ 90 ≤ 120 ≤ 180 ≤ 360 days) on all 1,385,691 bureau rows with counts (Q4), so subtracting the 30-day count removes the contaminated part exactly: the 180-day minus the 30-day count covers [decision − 166 days, decision − 16 days). The four enquiry counts used (1 to 4, 1 to 6, 1 to 12 and 6 to 12 months) are such differences; each ends 16 days or more before the decision and none is negative. The raw 30- and 90-day counts are not features. Feature log: loans with a Home Credit application in the 14 days after the decision and none just before it show 1.02 vs 0.47 enquiries in the "30-day" count; cleaning moves the 6-month window's IV from about 0.10 to 0.073. |
| S9 | Employment start dates after the decision are set to missing | 316 loans (`sql/04`, `dq_06`). |

### 7.5 Why "null if after the decision" was rejected

The simple fix for a dated field is to blank it when the date is after the decision. It leaks through the missing bin. The blanked loans join the loans that never had the event, and they are not a random group. Example, `lastapplicationdate_877D` in the training window (Q7):

| Group | Loans | Bad rate |
|---|---:|---:|
| No last-application date in the source (no earlier application) | 182,363 | 2.21% |
| Last application dated after the decision (would be blanked) | 58,331 | 4.52% |
| Missing bin after "null if after the decision" (both groups) | 240,694 | 2.77% |
| Point-in-time rebuild: no application before the decision | 190,451 | 2.27% |

Blanking raises the missing bin's bad rate from 2.21% to 2.77%. "Missing" would then partly mean "applied again within 14 days after the decision", which the lender could not know. The rebuild from previous applications avoids this and keeps more signal. Feature log, training IV of the rebuild vs the blanked version: 0.056 vs 0.029 for days since the last application, 0.153 vs 0.116 for days since the last rejection, 0.157 vs 0.123 for the last rejection reason (log values; `feature_screening.parquet` gives the rebuilt reason 0.163, as in 5.2).

Fields with no point-in-time source were therefore dropped rather than blanked: for example `datelastunpaid_3546854D`, `maxdpdinstldate_3546855D`, `firstdatedue_489D` and the goods category of the last approved or rejected application. `lastdelinqdate_224D` is not a feature; it is used only to apply the DPD floor (S6).

### 7.6 Residual risks

- **Long windows are still measured at the snapshot.** All 30 repayment-history features come from the `static_0` snapshot. Apart from `max_dpd_6to36m` and `max_past_debt`, whose windows end 6 and 4 months before the snapshot (feature log), each can include up to 14 days after the decision. They are kept because their windows are 6 months or longer, or lifetime: 14 days is 8% of a 6-month window and 2% of a 24-month window. Two contact-sharing counts carry the same residual (`n_apps_same_phone`, `n_clients_same_mobile_12m`). The feature log names nine of these fields as kept under rule L4 with this residual: `avg_dpd_24m`, `avg_days_late_24m`, `avg_worst_dpd_9m`, `avg_instalment_24m`, `n_months_with_payment_24m`, `n_incoming_payments_9m`, `max_days_overdue_hist`, `n_apps_same_phone`, `n_clients_same_mobile_12m`.
- **Size of the inflation.** Notebook 02 (section 4) puts the residual at most about 0.01 IV per field. The seven DPD maxima are the kept fields where the post-decision part can be bounded from the data, because DPD grows by at most one day per day. They were checked for this document (Q9). Worst case: every delinquency that started on or before the decision kept running to decision + 14 days, and every maximum that could include those days is replaced by its lower bound. Training IV then falls by 0.002 to 0.008 per field. The averages, shares and counts cannot be split into a pre- and a post-decision part with this data.

| Feature | Training loans changed by the floor (S6) | IV as provided | IV after the floor (used) | Removed by the floor | Training loans in the worst case | IV in the worst case | Possible residual |
|---|---:|---:|---:|---:|---:|---:|---:|
| `max_dpd_6m` | 1.3% | 0.131 | 0.123 | 0.008 | 0.7% | 0.121 | 0.002 |
| `max_dpd_9m` | 1.3% | 0.149 | 0.139 | 0.010 | 0.7% | 0.136 | 0.003 |
| `max_dpd_12m` | 1.2% | 0.164 | 0.157 | 0.007 | 0.8% | 0.155 | 0.002 |
| `max_dpd_24m` | 1.1% | 0.191 | 0.184 | 0.007 | 0.8% | 0.180 | 0.004 |
| `max_dpd_ever` | 0.9% | 0.179 | 0.176 | 0.003 | 0.9% | 0.173 | 0.003 |
| `max_days_overdue_hist` | 0.8% | 0.220 | 0.215 | 0.005 | 1.0% | 0.209 | 0.006 |
| `max_days_late_12m` | 1.2% | 0.248 | 0.232 | 0.016 | 0.7% | 0.224 | 0.008 |

Training window (Jan to Oct 2019), IV with 10 quantile bins plus a missing bin (`src/metrics.py`, `iv_numeric`, the same method as `feature_screening.parquet`). The two difference columns subtract the rounded IVs shown.

- **Lower bounds lose some signal.** R3b and S6 replace uncertain values with lower bounds. That removes the leak, but it can understate the DPD of a contract that was already late at the decision. This is a loss of information, not a leak.

### 7.7 What the leak would have done: ablation

Notebook 02, section 3.4; tables `leakage_ablation.parquet`, `leakage_ablation_groups.parquet`, `leakage_business.parquet`. Same LightGBM set-up and same time split; only the inputs differ.

- **A · point-in-time (ours):** the 90 features.
- **B · as provided (naive):** previous-application aggregates over all rows including post-decision applications, raw DPD, raw bureau windows, plus the dropped snapshot fields ([`sql/06`](../sql/06_abl_snapshot_as_provided.sql)). Fairness attributes, interest rate, campaign and roll-out fields stay excluded, so the comparison isolates timing. Tax-authority fields are not in B either.
- **B scored on decision-time inputs:** every field that can be rebuilt point-in-time is swapped for its point-in-time value. Fields with no rebuild stay as provided (five dated ones are blanked when the date is after the decision), so this estimate is still optimistic for B.

| Model | Validation Gini (Nov to Dec 2019) | Out-of-time test Gini (Jan to Mar 2020) |
|---|---:|---:|
| A · point-in-time (ours) | 0.582 | 0.578 |
| B · as provided, offline test | 0.594 | 0.588 |
| B · as provided, decision-time inputs | 0.591 | 0.585 |

Where B's edge sits (out-of-time test). "Activity after the decision" means a new application, rejection, approval, activation or delinquency dated after the decision.

| Group | Share of test loans | Bad rate | A | B, offline | B, decision-time inputs | B offline minus A |
|---|---:|---:|---:|---:|---:|---:|
| Client activity dated after the decision | 10.6% | 7.71% | 0.532 | 0.545 | 0.541 | +0.013 |
| No post-decision activity | 89.4% | 4.02% | 0.576 | 0.583 | 0.583 | +0.007 |

What it means in money (out-of-time test, same cost-based rule, each model calibrated on its own validation predictions):

| Model | Approval rate | Expected bad rate of approved | Observed bad rate of approved | Net profit |
|---|---:|---:|---:|---:|
| A · point-in-time (ours) | 90.7% | 2.79% | 3.17% | 991.8M CU |
| B · what the offline test promises | 90.6% | 2.76% | 3.11% | 995.6M CU |
| B · what it delivers at decision time | 91.0% | 2.74% | 3.14% | 995.0M CU |

Approval rates are shares of previously approved applicants; the bad rate of past rejects is unknown. Net profit uses assumed margins, exposure at default and loss given default ([assumptions.md](assumptions.md)).

Reading the results:
1. **The leak exists and the naive model benefits from it.** Offline, B scores 0.588 against 0.578. Its edge is about twice as large among the 10.6% of loans whose client did something after the decision (+0.013 vs +0.007 Gini).
2. **The effect is small in this data.** The client's track record with the lender carries 52% of the challenger's SHAP impact (`reports/metrics.json`, `models.track_record_share`). Its repayment part uses long windows, which a 14-day lag barely changes (7.6), and its previous-application part is rebuilt point-in-time. 48% of B's total split gain (LightGBM feature importance) comes from inputs that are computed differently by us or dropped (notebook 02, section 3.4).
3. **The strict rules have a small, measured price.** With decision-time values swapped in, B still scores 0.585, 0.007 above ours. The remainder comes from snapshot fields such as current debt, current days past due and short-window counts. They mix pre-decision information with up to 14 days of post-decision information and cannot be separated, so they were dropped. Cost: less than one Gini point and 0.3% of net profit (3.2M CU) on the test quarter (`reports/metrics.json`, `leakage.naive_decision_time_profit_gap`), measured against an estimate that is still optimistic for B.
4. **Fix at source.** Re-extract the dropped snapshot fields as of the decision date, then test them again.

## 8. How the absence of leakage across the time split was verified

| # | Check | Result | Reproduce |
|---|---|---|---|
| 1 | Time-based split by decision month | Each loan gets exactly one window from MONTH: train 2019-01 to 2019-10, validation 2019-11 to 2019-12, test 2020-01 to 2020-03, monitoring 2020-04 to 2020-10. Window totals add up to 1,526,659 loans and 47,994 bads. No random split is used to fit, calibrate or test the credit models; the only one is the fair-lending proxy check (section 4). | [config.yaml](../config.yaml) `split`; `sql/01` final query; notebook 02, section 3.1; [`src/fairness.py`](../src/fairness.py) |
| 2 | Features computed relative to each loan's own decision date | Every window, day count and filter uses the loan's own `date_decision`. There is no global "as of" date. | [`sql/02`](../sql/02_stg_static.sql), [`sql/03`](../sql/03_int_applprev_pit.sql), [`sql/04`](../sql/04_int_person_applicant.sql) |
| 3 | Previous-application filter: creation date before the decision date | R1 removes 144,679 rows dated on or after the decision and 66 rows with no creation date. Minimum days since the last application, last rejection, last approval and first application: 1 day each. Minimum `employment_years`: 0. | `sql/03` final query; Q5 |
| 4 | 15-row window | Unaffected by post-decision rows for all but 171 of 1,526,659 loans. | Q5 |
| 5 | Recount checks | The rebuilt 30-, 90- and 365-day application counts equal an independent recount over [decision − N days, decision) for 99.999%, 99.99% and 99.85% of loans. All 10, 172 and 2,328 differences are clients at the 15-row cap whose rebuilt count is below the recount; none comes from a post-decision row. Days since the last application equals the recount for 100% of loans. | Q8 |
| 6 | No single feature with IV above 0.5 | Highest training IV 0.306 (`avg_dpd_24m`). The feature log flags anything above 0.5 for review (rule L6); scorecard selection refuses IV above 0.8. | `feature_screening.parquet`; [feature log](feature_inclusion_log.csv); `src/modeling.py` |
| 7 | No target encoding | The SQL build reads `target` only to carry the label (`sql/01`, `sql/05`). WOE bins and scorecard weights are fitted on the training window only. LightGBM category levels are frozen from the training window. | `sql/0*.sql`; notebook 03, model-fitting cells before the TL;DR; `src/modeling.py` |
| 8 | No MONTH, WEEK_NUM, `case_id` or decision date as features | The 90 inputs exclude `case_id`, `date_decision`, `decision_month`, `week_num`, `split`, `target` and the `fair_` attributes. `check_against_table` fails the build if the SQL table and the feature catalogue disagree. | `src/features.py`; notebook 02, table-build cell before the TL;DR |
| 9 | Fitting and calibration only on earlier windows | WOE bins, the scorecard and the LightGBM trees: training window (Jan to Oct 2019). Early stopping and Platt calibration: validation window (Nov to Dec 2019). Apart from notebook 02's training-to-test PSI screen and notebook 03's SHAP ranking on a test-quarter sample, which put inputs on the CSI list, the test quarter is used only to evaluate. PSI and CSI reference: training window. The recommended cut-offs are break-even PDs from cost assumptions, not fitted to any window. Two diagnostics in notebook 04 (section 9), a hindsight intercept refit and the calibration slope, and the "best single cut-off" on the loss curve are read off test-quarter outcomes. These are reported as diagnostics or benchmarks; no decision rule uses them. | [notebook 03](../notebooks/03_modeling.ipynb), model-fitting cells before the TL;DR; [notebook 04](../notebooks/04_threshold_and_strategy.ipynb), sections 3, 9 and 10 |
| 10 | Training-window test | Same challenger refitted from later start months. The choice rests on validation Gini: 0.582 from January 2019 (used), 0.579 from March 2019, 0.575 from June 2019. The test quarter only confirms it: 0.578, 0.577, 0.572. | Notebook 03, appendix (section 6); `training_window_check.parquet` |
| 11 | Snapshot dates at the window boundaries | Kept long-window fields of loans decided in the last 14 days of a window are measured in the next window: 41,638 training loans (decided 18 to 31 October 2019), 62,270 validation loans (18 to 31 December 2019) and 23,256 test loans (18 to 31 March 2020). This is the residual of 7.6, not an additional leak. No outcome from a later window enters an earlier one. | Q10 |

The hindsight benchmark in check 9 favours single cut-offs, not the recommended rule. Read off the test quarter, the challenger's best single cut-off (PD 14.8%) costs 326.3M CU in wrong decisions; the cost-based rule costs 301.0M CU (assumed margins and losses, [assumptions.md](assumptions.md); `reports/metrics.json`, `loss_curve`).

## 9. Open issues and residual risks

- **Snapshot lag in kept fields.** The repayment-history features and two contact-sharing counts still include up to 14 days after the decision. For the DPD maxima the worst case is 0.002 to 0.008 training IV per field; averages, shares and counts cannot be split. *Fix at source:* re-extract them as of the decision date.
- **Dropped snapshot fields.** Current debt, current DPD and short-window counts were dropped. With the other point-in-time rules, that cost less than one Gini point and 0.3% of net profit on the test quarter (7.7). Re-extracting these fields as of the decision date may recover part of it; they must then pass the same tests. Tax-authority data were not part of that test; if the tax check can run before the decision in production, it can be re-evaluated.
- **Cause of the 14-day lag unknown.** A pipeline lag and a mislabelled decision date look the same in this data. The data owner should confirm. The rules assume the stricter case.
- **Early-2019 bureau gap.** In training, the bureau missing bin mixes "not collected" and "no record". The five bureau features are, with the last reject reason, the 6 of the 90 inputs with a training-to-test PSI above 0.10 (5.2). They carry 5.2% of the challenger's impact and are on the CSI list, which covers the 12 most influential inputs, every categorical input and every input that already shifted between training and test.
- **Reject-reason codes.** New codes replace old ones from February 2019 (5.2), and the challenger's splits on this field were learned on the 2019 mix (the scorecard does not use it). The codes are hashed, so the data owner should confirm whether the meaning changed. If it did, the challenger needs refitting; if only the coding did, a mapping from old to new codes would remove the drift.
- **Employment start date.** This is the challenger's strongest single input, and its capture fell from about 40% to 5.1% (May 2020). Production needs a check that the field is still collected (CSI reached 0.86 in the back-test, and the scorecard's score PSI rose to 0.108 to 0.146 with it while the challenger's stayed below 0.10). Its missing bin stands in for income type (retirees), so fairness results by age band depend on it (notebook 04).
- **Monitoring back-test not blind.** Two employment fields (`empl_industry_691L`, `empl_employedtotal_800L`) were dropped partly because their collection stopped in June 2020, inside the monitoring window (5.2). The six inputs that had already shifted between training and test were put on the CSI list with that knowledge, and all six are among the 12 inputs the back-test flags after the training window (`csi_flags.parquet`). The back-test shows how the plan handles breaks already known, not that it would have found them unaided.
- **Label maturity.** The split separates decision dates, not outcome dates. Unless the undisclosed outcome horizon is shorter than about two months, the labels of loans booked in late 2019 were observed after the test quarter began, so a lender deploying in January 2020 could not yet have trained on them. The size of this effect is unknown. The latest vintages may also be immature, which could account for part of the monitoring window's lower bad rate (notebook 01, section 4.3).
- **Approved loans only.** Every check here covers booked loans. Data quality for applicants the lender rejected, and their bad rate, are unknown.
- **Source quirks to raise with the data owner.** Income top-coded at 200,000 CU (12,430 loans); a share of instalments paid early above 100% (34,202 loans, capped at 1); the August 2019 change in the tail of `numinstlswithdpd10_728L`; 2 loans with a monthly payment above the loan amount.
- **Reconciliation of figures quoted in code comments (resolved).** The `sql/03` header now quotes the recounts in this document: 171 affected loans (99.99%) for rule R2, and for the R3b evidence 858 rows (3.7% of those with a DPD value) already at 1 to 14 days, defaulting at 14.0% vs 4.2% (Q5, Q6).

## Appendix: queries used in this document

Run after `make sql`, read-only, for example:

```python
from src.db import query          # opens data/warehouse.duckdb read-only and sets data_dir
print(query("""<paste a query here>"""))
```

`stg_base`, `int_applprev_pit`, `fct_application_features` and `abl_features_as_provided` are built by `sql/01` to `sql/06`. Raw files are read through `getvariable('data_dir')`, as in the pipeline.

**Q1. Coverage by decision month** (sections 2 and 5)

```sql
WITH cb AS (SELECT case_id, days360_512L FROM read_parquet(getvariable('data_dir') || '/train_static_cb_0.parquet')),
     p  AS (SELECT case_id, empl_industry_691L, empl_employedtotal_800L
            FROM read_parquet(getvariable('data_dir') || '/train_person_1.parquet') WHERE num_group1 = 0)
SELECT b.decision_month,
       COUNT(*)                                          AS loans,
       COUNT(*) FILTER (WHERE cb.case_id IS NULL)        AS loans_no_bureau_row,
       AVG((cb.case_id IS NULL)::INT)                    AS no_bureau_row,
       AVG((cb.days360_512L IS NULL)::INT)               AS enquiry_counts_missing,
       AVG((p.empl_industry_691L IS NOT NULL)::INT)      AS industry_filled,
       AVG((p.empl_employedtotal_800L IS NOT NULL)::INT) AS length_band_filled,
       AVG((f.employment_years IS NOT NULL)::INT)        AS employment_start_date_filled
FROM stg_base b
LEFT JOIN cb USING (case_id)
LEFT JOIN p USING (case_id)
JOIN fct_application_features f USING (case_id)
GROUP BY 1 ORDER BY 1;
```

**Q2. Columns rolled out during 2019** (section 5.2)

```sql
SELECT col, MIN(date_decision) AS first_decision_with_value, COUNT(*) AS loans_with_value
FROM (UNPIVOT (SELECT b.date_decision, CAST(COLUMNS('_(4187|4325|4493|4499|4525)[0-9]+[A-Z]$') AS VARCHAR)
               FROM stg_base b
               JOIN read_parquet(getvariable('data_dir') || '/train_static_0_*.parquet', union_by_name = true) USING (case_id))
      ON COLUMNS(* EXCLUDE (date_decision)) INTO NAME col VALUE v)
GROUP BY col ORDER BY first_decision_with_value, col;
```

**Q3. Caps and coding changes in `static_0`** (sections 5.2 and 6)

```sql
SELECT COUNT(*) FILTER (WHERE numinstlswithdpd10_728L > 40)     AS instalments_10d_late_above_40,
       COUNT(*) FILTER (WHERE pctinstlsallpaidearl3d_427L > 1)   AS share_early_3d_above_1,
       COUNT(pctinstlsallpaidearl3d_427L)                        AS share_early_3d_non_missing,
       MAX(pctinstlsallpaidearl3d_427L)                          AS share_early_3d_max,
       COUNT(*) FILTER (WHERE mobilephncnt_593L > 6)             AS same_mobile_above_6,
       COUNT(*) FILTER (WHERE clientscnt12m_3712952L > 3)        AS clients_same_mobile_12m_above_3,
       COUNT(*) FILTER (WHERE applicationscnt_1086L > 13)        AS apps_same_phone_above_13,
       COUNT(*) FILTER (WHERE homephncnt_628L > 5)               AS home_phones_above_5,
       MAX(mobilephncnt_593L) AS same_mobile_max, MAX(applicationscnt_1086L) AS apps_same_phone_max,
       COUNT(*) FILTER (WHERE maxdpdlast24m_143P IS NOT NULL AND maxdpdfrom6mto36m_3546853P IS NULL) AS dpd_6to36m_missing_with_history
FROM read_parquet(getvariable('data_dir') || '/train_static_0_*.parquet', union_by_name = true);

SELECT b.decision_month,
       AVG((s.maxdpdlast24m_143P IS NOT NULL AND s.maxdpdfrom6mto36m_3546853P IS NULL)::INT) AS dpd_6to36m_missing_with_history,
       AVG((s.numinstlswithdpd10_728L > 40)::INT) AS instalments_10d_late_above_40,
       MAX(s.numinstlswithdpd10_728L)             AS instalments_10d_late_max
FROM stg_base b
JOIN read_parquet(getvariable('data_dir') || '/train_static_0_*.parquet', union_by_name = true) s USING (case_id)
GROUP BY 1 ORDER BY 1;
```

**Q4. Amounts, income and bureau window nesting** (sections 6 and 7.4)

```sql
SELECT QUANTILE_CONT(loan_amount, 0.5)   AS amount_median,
       QUANTILE_CONT(loan_amount, 0.999) AS amount_p999,
       MAX(loan_amount)                  AS amount_max,
       QUANTILE_CONT(income_main, 0.999) AS income_p999,
       MAX(income_main)                  AS income_max,
       COUNT(*) FILTER (WHERE income_main = 200000) AS loans_at_income_200000
FROM fct_application_features;

SELECT COUNT(days360_512L) AS bureau_rows_with_counts,
       AVG((days30_165L <= days90_310L AND days90_310L <= days120_123L
            AND days120_123L <= days180_256L AND days180_256L <= days360_512L)::INT)
           FILTER (WHERE days360_512L IS NOT NULL) AS share_nested
FROM read_parquet(getvariable('data_dir') || '/train_static_cb_0.parquet');
```

**Q5. Previous-application filter and window** (sections 2, 7.4 and 8)

```sql
WITH a AS (
    SELECT a.case_id, CAST(a.creationdate_885D AS DATE) AS c_dt, b.date_decision AS dd
    FROM read_parquet(getvariable('data_dir') || '/train_applprev_1_*.parquet', union_by_name = true) a
    JOIN stg_base b USING (case_id)
),
per_loan AS (
    SELECT case_id, COUNT(*) AS n_rows, COUNT(*) FILTER (WHERE c_dt < dd) AS n_pre FROM a GROUP BY case_id
)
SELECT (SELECT COUNT(*) FROM a)                                         AS rows_total,
       (SELECT COUNT(*) FROM a WHERE c_dt >= dd)                        AS rows_on_or_after_decision,
       (SELECT COUNT(*) FROM a WHERE c_dt IS NULL)                      AS rows_with_no_creation_date,
       (SELECT MAX(c_dt - dd) FROM a)                                   AS max_days_after_decision,
       (SELECT COUNT(*) FROM per_loan WHERE n_pre > 0)                  AS loans_with_pre_decision_row,
       (SELECT COUNT(*) FROM per_loan WHERE n_pre = 0)                  AS loans_with_no_pre_decision_row,
       (SELECT COUNT(*) FROM per_loan WHERE n_rows = 20)                AS loans_at_20_row_cap,
       (SELECT COUNT(*) FROM per_loan WHERE n_rows = 20 AND n_pre < 15) AS loans_window_affected,
       (SELECT MIN(ap_days_since_last_app) FROM int_applprev_pit)       AS min_days_since_last_app,
       (SELECT MIN(ap_days_since_last_reject) FROM int_applprev_pit)    AS min_days_since_last_reject,
       (SELECT MIN(ap_days_since_last_approval) FROM int_applprev_pit)  AS min_days_since_last_approval,
       (SELECT MIN(ap_days_since_first_app) FROM int_applprev_pit)      AS min_days_since_first_app,
       (SELECT MIN(employment_years) FROM fct_application_features)     AS min_employment_years;
```

**Q6. Days-past-due evidence and the DPD floor** (section 7.4)

```sql
-- (a) previous contracts created before the decision whose first instalment falls after it
WITH a AS (
    SELECT b.target, a.maxdpdtolerance_577P AS dpd
    FROM read_parquet(getvariable('data_dir') || '/train_applprev_1_*.parquet', union_by_name = true) a
    JOIN stg_base b USING (case_id)
    WHERE CAST(a.creationdate_885D AS DATE) < b.date_decision
      AND CAST(a.firstnonzeroinstldate_307D AS DATE) > b.date_decision
      AND a.maxdpdtolerance_577P IS NOT NULL
)
SELECT COUNT(*) AS rows_with_dpd,
       AVG((dpd BETWEEN 1 AND 14)::INT)                 AS share_dpd_1_to_14,
       AVG(target) FILTER (WHERE dpd BETWEEN 1 AND 14)  AS bad_rate_dpd_1_to_14,
       AVG(target) FILTER (WHERE dpd = 0)               AS bad_rate_dpd_0
FROM a;

-- (b) static_0 maxima set to 0 by the floor in sql/02
WITH s AS (
    SELECT b.target,
           DATEDIFF('day', b.date_decision, TRY_CAST(x.lastdelinqdate_224D AS DATE)) AS da,
           x.maxdpdlast6m_474P AS m6, x.maxdpdlast9m_1059P AS m9, x.maxdpdlast12m_727P AS m12,
           x.maxdpdlast24m_143P AS m24, x.maxdpdtolerance_374P AS mever,
           x.daysoverduetolerancedd_3976961L AS od, x.maxdbddpdtollast12m_3658940P AS late12
    FROM stg_base b
    JOIN read_parquet(getvariable('data_dir') || '/train_static_0_*.parquet', union_by_name = true) x USING (case_id)
)
SELECT COUNT(*) FILTER (WHERE da > 0 AND m24 > 0 AND m24 <= 14 - da) AS loans_24m_max_set_to_0,
       COUNT(*) FILTER (WHERE da > 0 AND ((m6 > 0 AND m6 <= 14 - da) OR (m9 > 0 AND m9 <= 14 - da)
                         OR (m12 > 0 AND m12 <= 14 - da) OR (m24 > 0 AND m24 <= 14 - da)
                         OR (mever > 0 AND mever <= 14 - da) OR (od > 0 AND od <= 14 - da)
                         OR (late12 > 0 AND late12 <= 14 - da))) AS loans_any_max_changed,
       AVG(target) FILTER (WHERE da > 0 AND m24 > 0 AND m24 <= 14 - da) AS bad_rate_24m_set_to_0,
       AVG(target) FILTER (WHERE NOT COALESCE(da > 0 AND m24 > 0 AND m24 <= 14 - da, FALSE)) AS bad_rate_rest
FROM s;
```

**Q7. "Null if after the decision" and the missing bin** (section 7.5)

```sql
WITH x AS (
    SELECT b.target, b.date_decision AS dd, TRY_CAST(s.lastapplicationdate_877D AS DATE) AS lad, a.ap_n_apps
    FROM stg_base b
    JOIN read_parquet(getvariable('data_dir') || '/train_static_0_*.parquet', union_by_name = true) s USING (case_id)
    JOIN int_applprev_pit a USING (case_id)
    WHERE b.split = 'train'
)
SELECT COUNT(*) FILTER (WHERE lad IS NULL)                 AS loans_no_date,
       AVG(target) FILTER (WHERE lad IS NULL)              AS bad_rate_no_date,
       COUNT(*) FILTER (WHERE lad > dd)                    AS loans_date_after_decision,
       AVG(target) FILTER (WHERE lad > dd)                 AS bad_rate_date_after_decision,
       COUNT(*) FILTER (WHERE lad IS NULL OR lad > dd)     AS loans_missing_if_blanked,
       AVG(target) FILTER (WHERE lad IS NULL OR lad > dd)  AS bad_rate_missing_if_blanked,
       COUNT(*) FILTER (WHERE ap_n_apps = 0)               AS loans_no_pit_history,
       AVG(target) FILTER (WHERE ap_n_apps = 0)            AS bad_rate_no_pit_history
FROM x;
```

**Q8. Independent recount of the rebuilt application counts** (section 8)

```sql
WITH a AS (SELECT case_id, CAST(creationdate_885D AS DATE) AS c_dt
           FROM read_parquet(getvariable('data_dir') || '/train_applprev_1_*.parquet', union_by_name = true)),
r AS (
    SELECT b.case_id, b.date_decision AS dd,
           COUNT(a.c_dt) FILTER (WHERE a.c_dt >= b.date_decision - 30  AND a.c_dt < b.date_decision) AS n30,
           COUNT(a.c_dt) FILTER (WHERE a.c_dt >= b.date_decision - 90  AND a.c_dt < b.date_decision) AS n90,
           COUNT(a.c_dt) FILTER (WHERE a.c_dt >= b.date_decision - 365 AND a.c_dt < b.date_decision) AS n365,
           MAX(a.c_dt) FILTER (WHERE a.c_dt < b.date_decision) AS last_app
    FROM stg_base b LEFT JOIN a USING (case_id)
    GROUP BY b.case_id, b.date_decision
)
SELECT AVG((p.ap_n_apps_30d = r.n30)::INT)   AS match_30d,
       AVG((p.ap_n_apps_90d = r.n90)::INT)   AS match_90d,
       AVG((p.ap_n_apps_365d = r.n365)::INT) AS match_365d,
       COUNT(*) FILTER (WHERE p.ap_n_apps_30d <> r.n30)   AS diff_30d,
       COUNT(*) FILTER (WHERE p.ap_n_apps_90d <> r.n90)   AS diff_90d,
       COUNT(*) FILTER (WHERE p.ap_n_apps_365d <> r.n365) AS diff_365d,
       COUNT(*) FILTER (WHERE (p.ap_n_apps_30d <> r.n30 OR p.ap_n_apps_90d <> r.n90 OR p.ap_n_apps_365d <> r.n365)
                          AND NOT (p.ap_n_apps = 15 AND p.ap_n_apps_30d <= r.n30 AND p.ap_n_apps_90d <= r.n90
                                   AND p.ap_n_apps_365d <= r.n365)) AS diff_not_explained_by_cap,
       AVG((p.ap_days_since_last_app IS NOT DISTINCT FROM r.dd - r.last_app)::INT) AS match_days_since_last_app
FROM int_applprev_pit p JOIN r USING (case_id);
```

**Q9. IV of the DPD fields: as provided, after the floor, worst case** (sections 7.4 and 7.6)

```python
import numpy as np
from src.db import connect
from src.metrics import iv_numeric

cols = ["max_dpd_6m", "max_dpd_9m", "max_dpd_12m", "max_dpd_24m", "max_dpd_ever", "max_days_overdue_hist", "max_days_late_12m"]
con = connect(read_only=True)
d = con.execute(f"""
    SELECT f.target, f.ap_max_dpd_safe AS pit_ap, a.ap_max_dpd_safe AS raw_ap,
           {", ".join(f"f.{c} AS pit_{c}, a.{c} AS raw_{c}" for c in cols)},
           DATEDIFF('day', f.date_decision, TRY_CAST(s.lastdelinqdate_224D AS DATE)) AS da
    FROM fct_application_features f
    JOIN abl_features_as_provided a USING (case_id)
    JOIN read_parquet(getvariable('data_dir') || '/train_static_0_*.parquet', union_by_name = true) s USING (case_id)
    WHERE f.split = 'train'""").df()
y = d.target.to_numpy(float)
k = -d.da.astype(float).to_numpy()            # days from the last delinquency start to the decision
iv = lambda x: iv_numeric(np.asarray(x, float), y, 10)
print("previous-application worst DPD: naive", round(iv(d.raw_ap), 3), "point-in-time", round(iv(d.pit_ap), 3))
for c in cols:
    raw, pit = d[f"raw_{c}"].astype(float).to_numpy(), d[f"pit_{c}"].astype(float).to_numpy()
    floored = ~np.isnan(raw) & (raw != pit)
    worst = (k >= 0) & (pit > k) & (pit <= k + 14)   # maximum could include up to 14 post-decision days
    lower = np.where(worst, np.minimum(pit, k), pit)
    print(c, f"{floored.mean():.1%}", round(iv(raw), 3), round(iv(pit), 3), f"{worst.mean():.1%}", round(iv(lower), 3))
```

**Q10. Loans whose snapshot falls in the next window** (section 8)

```sql
SELECT split, COUNT(*) AS loans,
       COUNT(*) FILTER (WHERE date_decision + 14 > CASE split WHEN 'train' THEN DATE '2019-10-31'
                                                              WHEN 'valid' THEN DATE '2019-12-31'
                                                              WHEN 'test'  THEN DATE '2020-03-31' END) AS snapshot_in_next_window
FROM stg_base GROUP BY split ORDER BY MIN(date_decision);
```

**Q11. Reject-reason code mix by decision month** (section 5.2)

```sql
SELECT decision_month,
       AVG((ap_last_reject_reason = 'P94_109_143')::INT)                               AS share_P94_109_143,
       AVG((ap_last_reject_reason IN ('P99_56_166', 'P198_131_9', 'P45_84_106'))::INT) AS share_codes_first_seen_2019_02
FROM fct_application_features
GROUP BY 1 ORDER BY 1;
```
