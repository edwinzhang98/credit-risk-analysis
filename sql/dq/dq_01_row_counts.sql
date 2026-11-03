-- =====================================================================================================
-- dq_01_row_counts.sql · Row-count reconciliation across the source tables used in this project
-- Inputs : raw parquet in getvariable('data_dir'): train_base, train_static_0_*, train_static_cb_0,
--          train_applprev_1_*, train_person_1
-- Output : table dq_row_counts (one row per source) and the same rows as the final result set
-- Checks : rows, distinct case_id, how many base cases each table covers, orphans (case_id not in base)
-- Expect : base = 1,526,659 rows = static_0 rows; static_cb_0 covers ~98%; no orphans anywhere
-- Run    : python -m src.db sql/dq/dq_01_row_counts.sql
--          (DuckDB CLI: SET VARIABLE data_dir = '<path to parquet_files/train>'; then .read this file)
-- =====================================================================================================
CREATE OR REPLACE TEMP VIEW src_base AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_base.parquet');
CREATE OR REPLACE TEMP VIEW src_static_0 AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_static_0_*.parquet', union_by_name = true);
CREATE OR REPLACE TEMP VIEW src_static_cb_0 AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_static_cb_0.parquet');
CREATE OR REPLACE TEMP VIEW src_applprev_1 AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_applprev_1_*.parquet', union_by_name = true);
CREATE OR REPLACE TEMP VIEW src_person_1 AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_person_1.parquet');

CREATE OR REPLACE TABLE dq_row_counts AS
WITH base_ids AS (SELECT DISTINCT case_id FROM src_base),
counts AS (
    SELECT 'train_base' AS source_table, 'case' AS grain, COUNT(*) AS n_rows, COUNT(DISTINCT case_id) AS n_cases FROM src_base
    UNION ALL SELECT 'train_static_0 (2 files)', 'case', COUNT(*), COUNT(DISTINCT case_id) FROM src_static_0
    UNION ALL SELECT 'train_static_cb_0', 'case', COUNT(*), COUNT(DISTINCT case_id) FROM src_static_cb_0
    UNION ALL SELECT 'train_applprev_1 (2 files)', 'case x previous application', COUNT(*), COUNT(DISTINCT case_id) FROM src_applprev_1
    UNION ALL SELECT 'train_person_1', 'case x person', COUNT(*), COUNT(DISTINCT case_id) FROM src_person_1
),
orphans AS (
    SELECT 'train_static_0 (2 files)' AS source_table, COUNT(*) AS n_orphan_cases FROM (SELECT DISTINCT case_id FROM src_static_0) t ANTI JOIN base_ids USING (case_id)
    UNION ALL SELECT 'train_static_cb_0', COUNT(*) FROM (SELECT DISTINCT case_id FROM src_static_cb_0) t ANTI JOIN base_ids USING (case_id)
    UNION ALL SELECT 'train_applprev_1 (2 files)', COUNT(*) FROM (SELECT DISTINCT case_id FROM src_applprev_1) t ANTI JOIN base_ids USING (case_id)
    UNION ALL SELECT 'train_person_1', COUNT(*) FROM (SELECT DISTINCT case_id FROM src_person_1) t ANTI JOIN base_ids USING (case_id)
    UNION ALL SELECT 'train_base', 0
)
SELECT
    c.source_table,
    c.grain,
    c.n_rows,
    c.n_cases,
    ROUND(c.n_cases / (SELECT COUNT(*) FROM base_ids), 4) AS share_of_base_cases,
    o.n_orphan_cases
FROM counts c JOIN orphans o USING (source_table)
ORDER BY c.n_rows;

SELECT * FROM dq_row_counts;
