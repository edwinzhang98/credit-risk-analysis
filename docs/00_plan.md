# 00 · Project plan (one page)

**Owner:** Credit Risk Analyst (consumer lending) · **Stakeholder:** Head of Credit Policy · **Written:** 2026-11-03

## Direction and why

Direction **A: credit default / cut-off strategy** on **Home Credit – Credit Risk Model Stability (Kaggle 2024)**.
Reasons: the stakeholder's question is a credit-policy one (cut-off, swap set, approvals vs bad rate); this is the most recent public, real, application-level lending dataset (decisions from 2019-01 to 2020-10); and its multi-table layout (application, bureau, previous applications, persons) mirrors a real lending warehouse. The 2018 Home Credit dataset stays as a fallback only.

## Data (read in place with DuckDB, never committed)

`~/projects/data-projects/datasets/p2-comp-home-credit-2024/parquet_files/train/` (path set in `config.yaml`).
Tables used, added one at a time (stop adding when the signal is enough):

| Table | Grain | Rows | Use |
|---|---|---|---|
| `train_base` | 1 row / loan (case) | 1,526,659 | target, decision date, time split |
| `train_static_0_*` | 1 row / loan | 1,526,659 | current loan terms, internal payment-history summaries |
| `train_static_cb_0` | 1 row / loan | 1,500,476 | credit-bureau summaries (enquiries, rejections) |
| `train_applprev_1_*` | many rows / loan | 6,525,979 | the client's previous applications with this lender |
| `train_person_1` (applicant row) | 1 row / loan | 1,526,659 | employment, income; age and sex **for fairness testing only** |

## Early findings that shape the plan

1. **Only booked loans have outcomes** (all 1.53M rows have a default flag), so every approval rate in this project is a *simulated* rate on the historically approved population. Applicants rejected by the old policy are invisible; that is the reject-inference problem, and it is stated as limitation #1 together with the test that would close it.
2. **Look-ahead leak in the snapshot fields.** Date fields run up to 14 days *after* the decision date, and the pre-computed history counts match a window shifted +14 days (96.7% exact match) better than the point-in-time window (90.1%). Cases whose "last application" happened after the decision default 55% more often (5.0% vs 3.2%). Plan: rebuild history features point-in-time from the previous-applications table, drop short-window and "current status" snapshot fields, and measure how much the leak would have inflated results.
3. **Time drift.** Bad rate climbs from about 2.8% (H1 2019) to 4.7% (Feb 2020), then volume falls about 86% and bad rate drops to about 2.2% after April 2020 (COVID period). This drives the split design and gives the monitoring section a real drift episode.

## Analysis outline

| Step | Output |
|---|---|
| 1. Scope and metric definitions before touching data | `docs/01_request_and_scope.md`, `docs/02_metric_definitions.md`, `docs/assumptions.md` |
| 2. Data audit: row reconciliation, keys, nulls, outliers, time range, leakage | `notebooks/01_data_audit`, `sql/dq/`, `docs/03_data_quality_checks.md` |
| 3. Point-in-time features in DuckDB SQL; fair-lending exclusions; feature inclusion log | `sql/0*.sql`, `notebooks/02_feature_eng` |
| 4. Time split: train 2019-01..10 · validation 2019-11..12 · out-of-time test 2020-01..03 · monitoring 2020-04..10 | `config.yaml` |
| 5. Champion = WOE logistic-regression scorecard (the long-established approach in application scoring); challenger = LightGBM. Imbalance test (none / class weight / SMOTE); calibration; compared on money, not AUC | `notebooks/03_modeling` |
| 6. Cost matrix → break-even PD cut-off; loss curve; cut-off table; swap set (champion vs challenger); 3-tier policy (approve / review / decline) with volumes and cost; fairness by sex and age band; PSI and drift monitoring on the 2020 window | `notebooks/04_threshold_and_strategy`, `docs/cutoff_and_swap_set.md`, `docs/model_card.md` |
| 7. Deliverables | Streamlit app (7 pages), `reports/report.html`, `docs/readout.md`, `reports/executive_summary.md`, README |

## What we borrow and what we add

**Borrowed:** table-depth conventions and date-to-"days before decision" handling (jetakow starter); depth-1 aggregation patterns (batprem utility scripts); ratio features such as payment-to-income (jsaguiar 2018 kernel); SQL-first feature engineering (mratsim); swap-set framing from Experian's scorecard guidance and reject-inference caveats from Gregory & Etimova's survey.

**Added (what the competition notebooks skip):** point-in-time leakage audit with quantified impact; a cost matrix that sets the cut-off (instead of 0.5 or leaderboard AUC); a champion-vs-challenger swap set; a 3-tier decision policy with review cost and capacity; plain-English decline reasons; fair-lending checks; a monitoring plan tested on a real drift period; business-facing docs.

## Design decisions

Five decisions shape the analysis:
1. **"Is there room?" is answered in two parts.** Tightening is measured directly on the booked book; loosening is shown as an exchange rate (new approvals per declined loan at an unchanged bad rate) that depends on the unknown bad rate of past rejects, plus a sized below-cut-off test.
2. **Margins differ by product** (cash 20%, revolving 10%, point-of-sale 5%), so one rule ("approve when expected profit is positive") gives three PD cut-offs.
3. **Manual review is amount-aware and capacity-bound:** small point-of-sale loans never go to review; when demand exceeds capacity the most valuable reviews are kept.
4. **Fairness is tested with and without employment status**, and results are split by new-to-lender vs existing clients.
5. **A score/odds table, calibration-drift checks and test sizing** were added to the policy pack.

A column-by-column leakage check covers mid-2019 roll-out columns, "null if after the decision" leaking through the missing bin, days-past-due counted to decision + 14 days and bureau windows; all are handled in `sql/02` and `sql/03` and logged in `docs/feature_inclusion_log.csv`.

## Guardrails

Fixed seeds, one-command pipeline (`make all`), data path in `config.yaml`, no raw or row-level data in git. Every assumption goes into `docs/assumptions.md` with its source. Correlation is not written up as causation; small segments get intervals.
