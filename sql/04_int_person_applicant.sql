-- =====================================================================================================
-- 04_int_person_applicant.sql · The applicant's own person record: model inputs + fairness-test attributes
-- Inputs : table stg_base (sql/01_stg_base.sql); train_person_1.parquet (raw; num_group1 = 0 is the applicant)
-- Output : table int_person_applicant, 1 row per case_id
--            model inputs : employment_years, employment_length_band, employment_industry, income_main
--            fairness only: fair_sex, fair_age_years, fair_income_type  (prefix fair_ = NEVER a model input;
--                           used to test approval rates by group and for proxy checks)
-- Point-in-time: employment start dates after the decision date (316 cases) are set to NULL.
-- Run    : python -m src.db sql/04_int_person_applicant.sql
-- =====================================================================================================
CREATE OR REPLACE TEMP VIEW src_person_applicant AS
SELECT * FROM read_parquet(getvariable('data_dir') || '/train_person_1.parquet') WHERE num_group1 = 0;

CREATE OR REPLACE TABLE int_person_applicant AS
SELECT
    b.case_id,
    -- model inputs ---------------------------------------------------------------------------------------
    CASE WHEN TRY_CAST(p.empl_employedfrom_271D AS DATE) <= b.date_decision
         THEN DATEDIFF('day', TRY_CAST(p.empl_employedfrom_271D AS DATE), b.date_decision) / 365.25 END AS employment_years,
    p.empl_employedtotal_800L                                                                      AS employment_length_band,
    p.empl_industry_691L                                                                           AS employment_industry,
    p.mainoccupationinc_384A                                                                       AS income_main,
    -- fairness-test attributes only ------------------------------------------------------------------------
    p.sex_738L                                                                                     AS fair_sex,
    DATEDIFF('day', TRY_CAST(p.birth_259D AS DATE), b.date_decision) / 365.25                      AS fair_age_years,
    p.incometype_1044T                                                                             AS fair_income_type
FROM stg_base b
JOIN src_person_applicant p USING (case_id);

SELECT COUNT(*) AS rows, COUNT(DISTINCT case_id) AS cases, COUNT(employment_years) AS with_employment_years,
       ROUND(AVG(fair_age_years), 1) AS mean_age, ROUND(AVG(CASE WHEN fair_sex = 'F' THEN 1.0 ELSE 0 END), 3) AS share_female
FROM int_person_applicant;
