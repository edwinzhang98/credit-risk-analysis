-- =====================================================================================================
-- dq_06_value_ranges.sql · Impossible and extreme values in the fields that drive money and policy
-- Inputs : raw parquet in getvariable('data_dir'): train_base, train_static_0_*, train_person_1 (applicant row)
-- Output : table dq_value_ranges (one row per rule) and the same rows as the final result set
-- Rules  : each rule counts affected loans; "action" says what the pipeline does about it
-- Run    : python -m src.db sql/dq/dq_06_value_ranges.sql
-- =====================================================================================================
CREATE OR REPLACE TEMP VIEW src_base AS SELECT case_id, CAST(date_decision AS DATE) AS dd, target FROM read_parquet(getvariable('data_dir') || '/train_base.parquet');
CREATE OR REPLACE TEMP VIEW src_static_0 AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_static_0_*.parquet', union_by_name = true);
CREATE OR REPLACE TEMP VIEW src_person_1 AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_person_1.parquet') WHERE num_group1 = 0;

CREATE OR REPLACE TEMP TABLE v AS
SELECT
    b.case_id, b.target,
    s.credamount_770A AS credit_amount,
    s.annuity_780A AS annuity,
    s.eir_270L AS interest_rate,
    s.downpmt_116A AS down_payment,
    s.price_1097A AS goods_price,
    s.maxdpdlast24m_143P AS max_dpd_24m,
    p.mainoccupationinc_384A AS income,
    DATEDIFF('day', TRY_CAST(p.birth_259D AS DATE), b.dd) / 365.25 AS age_years,
    DATEDIFF('day', TRY_CAST(p.empl_employedfrom_271D AS DATE), b.dd) / 365.25 AS employment_years
FROM src_base b
JOIN src_static_0 s USING (case_id)
JOIN src_person_1 p USING (case_id);

CREATE OR REPLACE TABLE dq_value_ranges AS
WITH q AS (SELECT QUANTILE_CONT(credit_amount, 0.999) AS amt_p999, QUANTILE_CONT(income, 0.999) AS inc_p999 FROM v)
SELECT 'credit amount missing or <= 0' AS rule, COUNT(*) FILTER (WHERE credit_amount IS NULL OR credit_amount <= 0) AS n_loans, 'excluded from money metrics (none expected)' AS action FROM v
UNION ALL SELECT 'credit amount above 99.9th percentile', COUNT(*) FILTER (WHERE credit_amount > (SELECT amt_p999 FROM q)), 'kept; money metrics also reported as rates' FROM v
UNION ALL SELECT 'monthly annuity missing or <= 0', COUNT(*) FILTER (WHERE annuity IS NULL OR annuity <= 0), 'payment-to-income ratio left missing' FROM v
UNION ALL SELECT 'monthly annuity greater than the credit amount', COUNT(*) FILTER (WHERE annuity > credit_amount), 'kept; flagged in audit (likely revolving limits or data error)' FROM v
UNION ALL SELECT 'interest rate outside [0, 1]', COUNT(*) FILTER (WHERE interest_rate < 0 OR interest_rate > 1), 'kept as provided' FROM v
UNION ALL SELECT 'down payment greater than goods price', COUNT(*) FILTER (WHERE down_payment > goods_price AND goods_price > 0), 'down-payment share capped at 1' FROM v
UNION ALL SELECT 'max days past due (24m) negative', COUNT(*) FILTER (WHERE max_dpd_24m < 0), 'kept (negative = paid early, per data dictionary)' FROM v
UNION ALL SELECT 'income missing or <= 0', COUNT(*) FILTER (WHERE income IS NULL OR income <= 0), 'ratio features left missing' FROM v
UNION ALL SELECT 'income above 99.9th percentile', COUNT(*) FILTER (WHERE income > (SELECT inc_p999 FROM q)), 'kept; tree model and WOE bins are robust to outliers' FROM v
UNION ALL SELECT 'age at decision < 18 or > 100 (fairness attribute only)', COUNT(*) FILTER (WHERE age_years < 18 OR age_years > 100), 'age band set to unknown' FROM v
UNION ALL SELECT 'employment start date after the decision', COUNT(*) FILTER (WHERE employment_years < 0), 'employment length set to missing' FROM v
UNION ALL SELECT 'employment length > 60 years', COUNT(*) FILTER (WHERE employment_years > 60), 'employment length set to missing' FROM v;

SELECT * FROM dq_value_ranges;
