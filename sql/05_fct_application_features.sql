-- =====================================================================================================
-- 05_fct_application_features.sql · Model-ready application table: one row per loan, every feature point-in-time
-- Inputs : stg_base (01), stg_static (02), int_applprev_pit (03), int_person_applicant (04)
-- Output : table fct_application_features, 1 row per case_id (1,526,659 rows)
--   keys / labels ...... case_id, date_decision, decision_month, split, target
--   segments ........... product_type, is_new_to_lender (no earlier application with this lender)
--   features ........... all columns from stg_static and int_applprev_pit, employment_years, income_main, and the
--                        derived affordability / behaviour ratios below
--   fairness only ...... fair_sex, fair_age_years, fair_income_type (NEVER model inputs; for testing outcomes by group)
-- Derived features (all from fields known at the decision):
--   payment_to_income        monthly payment / declared monthly income
--   loan_to_income           loan amount / declared monthly income
--   down_payment_share       down payment / (loan amount + down payment)
--   disbursed_share          amount paid out at start / loan amount (revolving drawdown choice)
--   payment_vs_past_instalment / payment_vs_max_past_payment / loan_vs_max_past_debt   "payment shock" ratios
--   net_punctuality          share of instalments paid 3+ days early minus share paid late
--   dpd_worsening            1 if the worst lateness in the last 6 months exceeds the worst 6-36 months ago
--   has_repayment_history    1 if the client has an internal repayment record
-- Run    : python -m src.db sql/05_fct_application_features.sql
-- =====================================================================================================
CREATE OR REPLACE TABLE fct_application_features AS
SELECT
    b.case_id,
    b.date_decision,
    b.decision_month,
    b.split,
    b.target,
    -- segments
    s.product_type,
    CASE WHEN a.ap_n_apps = 0 THEN 1 ELSE 0 END                                         AS is_new_to_lender,
    -- current loan, history, bureau
    s.* EXCLUDE (case_id, product_type),
    -- previous applications (point in time)
    a.* EXCLUDE (case_id),
    -- applicant
    p.employment_years,
    p.income_main,
    -- derived ratios
    s.monthly_payment / NULLIF(p.income_main, 0)                                        AS payment_to_income,
    s.loan_amount / NULLIF(p.income_main, 0)                                            AS loan_to_income,
    s.down_payment / NULLIF(s.loan_amount + s.down_payment, 0)                          AS down_payment_share,
    s.disbursed_amount / NULLIF(s.loan_amount, 0)                                       AS disbursed_share,
    s.monthly_payment / NULLIF(s.avg_instalment_24m, 0)                                 AS payment_vs_past_instalment,
    s.monthly_payment / NULLIF(s.max_past_monthly_payment, 0)                           AS payment_vs_max_past_payment,
    s.loan_amount / NULLIF(s.max_past_debt, 0)                                          AS loan_vs_max_past_debt,
    s.share_instalments_early_3d - s.share_instalments_late_1d                          AS net_punctuality,
    CASE WHEN s.max_dpd_24m IS NULL THEN NULL
         WHEN s.max_dpd_6m > COALESCE(s.max_dpd_6to36m, 0) THEN 1 ELSE 0 END             AS dpd_worsening,
    CASE WHEN s.max_dpd_24m IS NULL THEN 0 ELSE 1 END                                   AS has_repayment_history,
    -- fairness-test attributes (never model inputs)
    p.fair_sex,
    p.fair_age_years,
    p.fair_income_type
FROM stg_base b
JOIN stg_static s USING (case_id)
JOIN int_applprev_pit a USING (case_id)
JOIN int_person_applicant p USING (case_id);

-- Reconciliation: one row per booked loan, split totals unchanged
SELECT split, COUNT(*) AS loans, SUM(target) AS bads, ROUND(AVG(target), 4) AS bad_rate,
       ROUND(AVG(is_new_to_lender), 3) AS share_new_to_lender
FROM fct_application_features GROUP BY split ORDER BY MIN(date_decision);
