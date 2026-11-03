-- =====================================================================================================
-- dq_05_snapshot_offset.sql · When were the pre-computed "history" fields actually measured?
-- Inputs : raw parquet in getvariable('data_dir'): train_base, train_static_0_*, train_applprev_1_*
-- Output : table dq_snapshot_offset (one row per candidate reference date) and final result set
-- Logic  : static_0.applications30d_658L = "applications made by the client in the last 30 days".
--          We recount the client's applications from the previous-applications table for windows that
--          end on different reference dates (decision date + 0, +7, +14, +21 days) and measure how often
--          the recount equals the provided field. The reference date with the best match is when the
--          snapshot was taken. A best match at +14 days means the field contains up to 14 days of
--          information from AFTER the credit decision (look-ahead leakage).
--          Second test: lastapplicationdate_877D vs the latest previous-application creation date with
--          and without a point-in-time filter.
-- Run    : python -m src.db sql/dq/dq_05_snapshot_offset.sql
-- =====================================================================================================
CREATE OR REPLACE TEMP VIEW src_base AS SELECT case_id, CAST(date_decision AS DATE) AS dd FROM read_parquet(getvariable('data_dir') || '/train_base.parquet');
CREATE OR REPLACE TEMP VIEW src_static_0 AS SELECT case_id, applications30d_658L, CAST(lastapplicationdate_877D AS DATE) AS lastapplicationdate FROM read_parquet(getvariable('data_dir') || '/train_static_0_*.parquet', union_by_name = true);
CREATE OR REPLACE TEMP VIEW src_applprev_1 AS SELECT case_id, CAST(creationdate_885D AS DATE) AS created FROM read_parquet(getvariable('data_dir') || '/train_applprev_1_*.parquet', union_by_name = true);

CREATE OR REPLACE TEMP TABLE recount AS
SELECT
    b.case_id,
    s.applications30d_658L AS provided_30d,
    s.lastapplicationdate,
    COUNT(a.created) FILTER (WHERE a.created >= b.dd - 30 AND a.created < b.dd)           AS cnt_ref_plus0,
    COUNT(a.created) FILTER (WHERE a.created >= b.dd - 23 AND a.created < b.dd + 7)       AS cnt_ref_plus7,
    COUNT(a.created) FILTER (WHERE a.created >= b.dd - 16 AND a.created < b.dd + 14)      AS cnt_ref_plus14,
    COUNT(a.created) FILTER (WHERE a.created >= b.dd - 9 AND a.created < b.dd + 21)       AS cnt_ref_plus21,
    MAX(a.created)                                                                         AS last_created_all,
    MAX(a.created) FILTER (WHERE a.created < b.dd)                                         AS last_created_pit
FROM src_base b
JOIN src_static_0 s USING (case_id)
LEFT JOIN src_applprev_1 a USING (case_id)
GROUP BY ALL;

CREATE OR REPLACE TABLE dq_snapshot_offset AS
SELECT 'applications30d_658L = recount over 30 days ending at decision date + 0d (point in time)' AS test,
       AVG(CASE WHEN provided_30d = cnt_ref_plus0 THEN 1.0 ELSE 0 END) AS match_rate FROM recount WHERE provided_30d IS NOT NULL
UNION ALL SELECT 'applications30d_658L = recount over 30 days ending at decision date + 7d',
       AVG(CASE WHEN provided_30d = cnt_ref_plus7 THEN 1.0 ELSE 0 END) FROM recount WHERE provided_30d IS NOT NULL
UNION ALL SELECT 'applications30d_658L = recount over 30 days ending at decision date + 14d',
       AVG(CASE WHEN provided_30d = cnt_ref_plus14 THEN 1.0 ELSE 0 END) FROM recount WHERE provided_30d IS NOT NULL
UNION ALL SELECT 'applications30d_658L = recount over 30 days ending at decision date + 21d',
       AVG(CASE WHEN provided_30d = cnt_ref_plus21 THEN 1.0 ELSE 0 END) FROM recount WHERE provided_30d IS NOT NULL
UNION ALL SELECT 'lastapplicationdate_877D = latest previous application (all rows, incl. after decision)',
       AVG(CASE WHEN lastapplicationdate = last_created_all THEN 1.0 ELSE 0 END) FROM recount WHERE lastapplicationdate IS NOT NULL
UNION ALL SELECT 'lastapplicationdate_877D = latest previous application created before the decision',
       AVG(CASE WHEN lastapplicationdate = last_created_pit THEN 1.0 ELSE 0 END) FROM recount WHERE lastapplicationdate IS NOT NULL;

SELECT * FROM dq_snapshot_offset;
