-- =====================================================================================================
-- dq_03_time_range.sql · Time coverage, calendar consistency and monthly volume / bad rate
-- Inputs : raw parquet in getvariable('data_dir'): train_base
-- Output : table dq_time_range (one row per decision month) and table dq_time_checks (consistency checks)
-- Checks : date_decision range; MONTH equals the YYYYMM of date_decision; WEEK_NUM increases with time;
--          monthly volumes and bad rates (with 95% Wilson interval) to spot breaks
-- Run    : python -m src.db sql/dq/dq_03_time_range.sql
-- =====================================================================================================
CREATE OR REPLACE TEMP VIEW src_base AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_base.parquet');

CREATE OR REPLACE TABLE dq_time_checks AS
SELECT 'min date_decision' AS check_name, CAST(MIN(CAST(date_decision AS DATE)) AS VARCHAR) AS value FROM src_base
UNION ALL SELECT 'max date_decision', CAST(MAX(CAST(date_decision AS DATE)) AS VARCHAR) FROM src_base
UNION ALL SELECT 'rows where MONTH <> YYYYMM(date_decision)',
    CAST(COUNT(*) FILTER (WHERE MONTH <> YEAR(CAST(date_decision AS DATE)) * 100 + MONTH(CAST(date_decision AS DATE))) AS VARCHAR) FROM src_base
UNION ALL SELECT 'WEEK_NUM range', CAST(MIN(WEEK_NUM) AS VARCHAR) || ' to ' || CAST(MAX(WEEK_NUM) AS VARCHAR) FROM src_base
UNION ALL SELECT 'weeks whose WEEK_NUM order disagrees with dates',
    CAST((SELECT COUNT(*) FROM (
        SELECT WEEK_NUM, MIN(CAST(date_decision AS DATE)) AS d0, LAG(MAX(CAST(date_decision AS DATE))) OVER (ORDER BY WEEK_NUM) AS prev_max
        FROM src_base GROUP BY WEEK_NUM) WHERE d0 < prev_max) AS VARCHAR)
UNION ALL SELECT 'case_id increases with date (Spearman-like check: corr of ranks)',
    CAST(ROUND(CORR(r_case, r_date), 4) AS VARCHAR)
    FROM (SELECT RANK() OVER (ORDER BY case_id) AS r_case, RANK() OVER (ORDER BY CAST(date_decision AS DATE)) AS r_date FROM src_base);

CREATE OR REPLACE TABLE dq_time_range AS
WITH m AS (
    SELECT MONTH AS decision_month, COUNT(*) AS n, SUM(target) AS bads, MIN(CAST(date_decision AS DATE)) AS first_day, MAX(CAST(date_decision AS DATE)) AS last_day
    FROM src_base GROUP BY MONTH
)
SELECT
    decision_month, first_day, last_day, n, bads,
    bads / n AS bad_rate,
    -- 95% Wilson interval
    (bads / n + 1.96 ^ 2 / (2 * n) - 1.96 * SQRT(bads / n * (1 - bads / n) / n + 1.96 ^ 2 / (4 * n ^ 2))) / (1 + 1.96 ^ 2 / n) AS bad_rate_ci_low,
    (bads / n + 1.96 ^ 2 / (2 * n) + 1.96 * SQRT(bads / n * (1 - bads / n) / n + 1.96 ^ 2 / (4 * n ^ 2))) / (1 + 1.96 ^ 2 / n) AS bad_rate_ci_high
FROM m ORDER BY decision_month;

SELECT * FROM dq_time_checks;
