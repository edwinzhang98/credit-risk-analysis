-- =====================================================================================================
-- 01_stg_base.sql · Staging: one row per booked loan with decision date, vintage month and time split
-- Inputs : train_base.parquet (raw, in getvariable('data_dir'))
-- Output : table stg_base
--            case_id        BIGINT  primary key
--            date_decision  DATE    date the credit decision was made (the point-in-time reference)
--            decision_month INTEGER YYYYMM, the vintage
--            week_num       INTEGER week index provided with the data
--            target         INTEGER 1 = default ("bad"), 0 = repaid ("good")
--            split          VARCHAR train / valid / test / monitor (time-based, see config.yaml)
-- Grain  : 1 row per case_id, 1,526,659 rows
-- Run    : python -m src.db sql/01_stg_base.sql
--          (DuckDB CLI: SET VARIABLE data_dir = '<path to parquet_files/train>'; .read sql/01_stg_base.sql
--           split months fall back to the defaults below when the variables are not set)
-- =====================================================================================================
CREATE OR REPLACE TABLE stg_base AS
SELECT
    case_id,
    CAST(date_decision AS DATE)        AS date_decision,
    CAST(MONTH AS INTEGER)             AS decision_month,
    CAST(WEEK_NUM AS INTEGER)          AS week_num,
    CAST(target AS INTEGER)            AS target,
    CASE
        WHEN MONTH BETWEEN COALESCE(getvariable('train_start'), 201901)   AND COALESCE(getvariable('train_end'), 201910)   THEN 'train'
        WHEN MONTH BETWEEN COALESCE(getvariable('valid_start'), 201911)   AND COALESCE(getvariable('valid_end'), 201912)   THEN 'valid'
        WHEN MONTH BETWEEN COALESCE(getvariable('test_start'), 202001)    AND COALESCE(getvariable('test_end'), 202003)    THEN 'test'
        WHEN MONTH BETWEEN COALESCE(getvariable('monitor_start'), 202004) AND COALESCE(getvariable('monitor_end'), 202010) THEN 'monitor'
    END                                AS split
FROM read_parquet(getvariable('data_dir') || '/train_base.parquet');

-- Sanity: every loan gets exactly one split
SELECT split, COUNT(*) AS loans, SUM(target) AS bads, ROUND(AVG(target), 4) AS bad_rate,
       MIN(date_decision) AS first_decision, MAX(date_decision) AS last_decision
FROM stg_base GROUP BY split ORDER BY first_decision;
