-- =====================================================================================================
-- dq_02_keys_and_target.sql · Primary-key uniqueness and target sanity
-- Inputs : raw parquet in getvariable('data_dir'): train_base, train_static_0_*, train_static_cb_0,
--          train_applprev_1_*, train_person_1
-- Output : table dq_keys (one row per check) and the same rows as the final result set
-- Checks : declared key is unique in every table; static_0 files do not overlap; target is 0/1 only;
--          defaults reconcile with the dataset README (47,994 defaults, 3.14%)
-- Run    : python -m src.db sql/dq/dq_02_keys_and_target.sql
-- =====================================================================================================
CREATE OR REPLACE TEMP VIEW src_base AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_base.parquet');
CREATE OR REPLACE TEMP VIEW src_static_0 AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_static_0_*.parquet', union_by_name = true, filename = true);
CREATE OR REPLACE TEMP VIEW src_static_cb_0 AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_static_cb_0.parquet');
CREATE OR REPLACE TEMP VIEW src_applprev_1 AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_applprev_1_*.parquet', union_by_name = true);
CREATE OR REPLACE TEMP VIEW src_person_1 AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_person_1.parquet');

CREATE OR REPLACE TABLE dq_keys AS
SELECT 'train_base: case_id unique' AS check_name, COUNT(*) - COUNT(DISTINCT case_id) AS violations, 0 AS expected FROM src_base
UNION ALL SELECT 'train_static_0: case_id unique across both files', COUNT(*) - COUNT(DISTINCT case_id), 0 FROM src_static_0
UNION ALL SELECT 'train_static_0: no case_id in both files',
    (SELECT COUNT(*) FROM (SELECT case_id FROM src_static_0 GROUP BY case_id HAVING COUNT(DISTINCT filename) > 1)), 0
UNION ALL SELECT 'train_static_cb_0: case_id unique', COUNT(*) - COUNT(DISTINCT case_id), 0 FROM src_static_cb_0
UNION ALL SELECT 'train_applprev_1: (case_id, num_group1) unique', COUNT(*) - COUNT(DISTINCT (case_id, num_group1)), 0 FROM src_applprev_1
UNION ALL SELECT 'train_person_1: (case_id, num_group1) unique', COUNT(*) - COUNT(DISTINCT (case_id, num_group1)), 0 FROM src_person_1
UNION ALL SELECT 'train_person_1: every case has an applicant row (num_group1 = 0)',
    (SELECT COUNT(*) FROM src_base b ANTI JOIN (SELECT case_id FROM src_person_1 WHERE num_group1 = 0) p USING (case_id)), 0
UNION ALL SELECT 'train_base: target outside {0,1}', COUNT(*) FILTER (WHERE target NOT IN (0, 1) OR target IS NULL), 0 FROM src_base
UNION ALL SELECT 'train_base: number of defaults (README says 47,994)', SUM(target) - 47994, 0 FROM src_base
UNION ALL SELECT 'train_base: date_decision not parseable', COUNT(*) FILTER (WHERE TRY_CAST(date_decision AS DATE) IS NULL), 0 FROM src_base;

SELECT * FROM dq_keys;
