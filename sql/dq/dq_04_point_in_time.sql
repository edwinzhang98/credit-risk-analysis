-- =====================================================================================================
-- dq_04_point_in_time.sql · Do any dated fields fall AFTER the credit decision?
-- Inputs : raw parquet in getvariable('data_dir'): train_base, train_static_0_*, train_static_cb_0,
--          train_applprev_1_*, train_person_1 (applicant row)
-- Output : table dq_point_in_time (one row per date field) and the same rows as the final result set
-- Logic  : every column whose name ends in "D" is a date (competition naming convention). We unpivot them,
--          compare each value with the case's date_decision and report: share after the decision, the
--          largest gap in days, and the bad rate of cases with the date after vs on/before the decision.
--          A field that can be dated after the decision carries information the lender did not have.
-- Run    : python -m src.db sql/dq/dq_04_point_in_time.sql
-- =====================================================================================================
CREATE OR REPLACE TEMP VIEW src_base AS SELECT case_id, CAST(date_decision AS DATE) AS dd, target FROM read_parquet(getvariable('data_dir') || '/train_base.parquet');
CREATE OR REPLACE TEMP VIEW src_static_0 AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_static_0_*.parquet', union_by_name = true);
CREATE OR REPLACE TEMP VIEW src_static_cb_0 AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_static_cb_0.parquet');
CREATE OR REPLACE TEMP VIEW src_applprev_1 AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_applprev_1_*.parquet', union_by_name = true);
CREATE OR REPLACE TEMP VIEW src_person_1 AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_person_1.parquet') WHERE num_group1 = 0;

CREATE OR REPLACE TEMP TABLE date_fields AS
SELECT 'static_0' AS source_table, case_id, field, TRY_CAST(value AS DATE) AS event_date
FROM (UNPIVOT (SELECT case_id, COLUMNS('.*D$') FROM src_static_0) ON COLUMNS(* EXCLUDE (case_id)) INTO NAME field VALUE value)
UNION ALL
SELECT 'static_cb_0', case_id, field, TRY_CAST(value AS DATE)
FROM (UNPIVOT (SELECT case_id, COLUMNS('.*D$') FROM src_static_cb_0) ON COLUMNS(* EXCLUDE (case_id)) INTO NAME field VALUE value)
UNION ALL
SELECT 'applprev_1', case_id, field, TRY_CAST(value AS DATE)
FROM (UNPIVOT (SELECT case_id, COLUMNS('.*D$') FROM src_applprev_1) ON COLUMNS(* EXCLUDE (case_id)) INTO NAME field VALUE value)
UNION ALL
SELECT 'person_1 (applicant)', case_id, field, TRY_CAST(value AS DATE)
FROM (UNPIVOT (SELECT case_id, COLUMNS('.*D$') FROM src_person_1) ON COLUMNS(* EXCLUDE (case_id)) INTO NAME field VALUE value);

CREATE OR REPLACE TABLE dq_point_in_time AS
SELECT
    d.source_table,
    d.field,
    COUNT(*)                                                                   AS n_non_null,
    AVG(CASE WHEN d.event_date > b.dd THEN 1.0 ELSE 0 END)                     AS share_after_decision,
    MAX(DATEDIFF('day', b.dd, d.event_date))                                   AS max_days_after_decision,
    AVG(b.target) FILTER (WHERE d.event_date > b.dd)                           AS bad_rate_if_after,
    AVG(b.target) FILTER (WHERE d.event_date <= b.dd)                          AS bad_rate_if_on_or_before
FROM date_fields d
JOIN src_base b USING (case_id)
WHERE d.event_date IS NOT NULL
GROUP BY ALL
ORDER BY share_after_decision DESC, n_non_null DESC;

SELECT * FROM dq_point_in_time;
