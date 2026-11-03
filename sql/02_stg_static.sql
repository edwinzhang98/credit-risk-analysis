-- =====================================================================================================
-- 02_stg_static.sql · Application-level fields from the internal snapshot (static_0) and credit bureau (static_cb_0),
--                     kept only where they are point-in-time safe (see docs/03_data_quality_checks.md, docs/feature_inclusion_log.csv)
-- Inputs : table stg_base (sql/01_stg_base.sql); train_static_0_*.parquet, train_static_cb_0.parquet (raw)
-- Output : table stg_static, 1 row per case_id
--   Current loan terms ......... loan_amount, monthly_payment, loan_term_months, product_type, initial_transaction_type,
--                                is_cross_sell, down_payment, goods_price, disbursed_amount
--   Internal repayment history . 24-month / 9-month / 12-month / lifetime summaries (windows >= 6 months only)
--   Contact sharing ............ people / clients sharing the applicant's phone numbers (capped)
--   Credit bureau enquiries .... window DIFFERENCES that end 16 days before the decision (fully point-in-time)
--
-- Point-in-time and stability rules applied here
--   * Never used: dated "last event" fields and their companions (rebuilt from previous applications in sql/03),
--     snapshot aggregates with look-back < 6 months, "current status" fields (current debt, current DPD, active credits),
--     tax-authority fields (arrive at decision + 14 days), interest rate and marketing-campaign fields (outputs of the
--     lender's own pricing and targeting: they would teach the new model the old model's decisions).
--   * Columns rolled out part-way through 2019 (suffix families _4187, _4325, _4493, _4499, _4525) are not used: their
--     missing values encode the calendar period, not risk.
--   * Max days-past-due fields are measured up to decision + 14 days. If the client's last delinquency started after the
--     decision and the maximum could have been reached entirely after it, the value is set to 0 (lower bound).
--   * maxdpdfrom6mto36m: NULL was replaced by 0 from Sep-2019 onward; harmonised to 0 whenever the client has history.
--   * numinstlswithdpd10: its upper tail was truncated in Aug-2019; capped at 40 everywhere.
--   * Bureau: the provided "30 days" enquiry window is really [decision - 16d, decision + 14d), and windows nest
--     (30 <= 90 <= 120 <= 180 <= 360 on 100% of rows), so e.g. days180 - days30 counts enquiries in
--     [decision - 166d, decision - 16d): entirely before the decision.
-- Run    : python -m src.db sql/02_stg_static.sql
-- =====================================================================================================
CREATE OR REPLACE TEMP VIEW src_static_0 AS
SELECT * FROM read_parquet(getvariable('data_dir') || '/train_static_0_*.parquet', union_by_name = true);
CREATE OR REPLACE TEMP VIEW src_static_cb_0 AS
SELECT * FROM read_parquet(getvariable('data_dir') || '/train_static_cb_0.parquet');

CREATE OR REPLACE TABLE stg_static AS
WITH s AS (
    SELECT
        b.case_id,
        b.date_decision AS dd,
        x.*,
        -- days from decision to the client's last delinquency start (> 0 = started after the decision)
        DATEDIFF('day', b.date_decision, TRY_CAST(x.lastdelinqdate_224D AS DATE)) AS delinq_after_days
    FROM stg_base b
    JOIN src_static_0 x USING (case_id)
)
SELECT
    s.case_id,
    -- ---------------------------------------------------------------- current loan terms (known at application)
    s.credamount_770A                                         AS loan_amount,
    s.annuity_780A                                            AS monthly_payment,
    s.pmtnum_254L                                             AS loan_term_months,
    s.credtype_322L                                           AS product_type,
    s.inittransactioncode_186L                                AS initial_transaction_type,
    CAST(s.isbidproduct_1095L AS INTEGER)                     AS is_cross_sell,
    s.downpmt_116A                                            AS down_payment,
    s.price_1097A                                             AS goods_price,
    s.disbursedcredamount_1113A                               AS disbursed_amount,
    -- ---------------------------------------------------------------- internal repayment history (>= 6-month windows)
    s.avgdpdtolclosure24_3658938P                             AS avg_dpd_24m,
    s.avgdbddpdlast24m_3658932P                               AS avg_days_late_24m,
    s.avgmaxdpdlast9m_3716943P                                AS avg_worst_dpd_9m,
    CASE WHEN s.delinq_after_days > 0 AND s.maxdbddpdtollast12m_3658940P <= 14 - s.delinq_after_days THEN LEAST(s.maxdbddpdtollast12m_3658940P, 0)
         ELSE s.maxdbddpdtollast12m_3658940P END              AS max_days_late_12m,
    CASE WHEN s.delinq_after_days > 0 AND s.maxdpdlast6m_474P  <= 14 - s.delinq_after_days THEN 0 ELSE s.maxdpdlast6m_474P  END AS max_dpd_6m,
    CASE WHEN s.delinq_after_days > 0 AND s.maxdpdlast9m_1059P <= 14 - s.delinq_after_days THEN 0 ELSE s.maxdpdlast9m_1059P END AS max_dpd_9m,
    CASE WHEN s.delinq_after_days > 0 AND s.maxdpdlast12m_727P <= 14 - s.delinq_after_days THEN 0 ELSE s.maxdpdlast12m_727P END AS max_dpd_12m,
    CASE WHEN s.delinq_after_days > 0 AND s.maxdpdlast24m_143P <= 14 - s.delinq_after_days THEN 0 ELSE s.maxdpdlast24m_143P END AS max_dpd_24m,
    CASE WHEN s.delinq_after_days > 0 AND s.maxdpdtolerance_374P <= 14 - s.delinq_after_days THEN 0 ELSE s.maxdpdtolerance_374P END AS max_dpd_ever,
    CASE WHEN s.delinq_after_days > 0 AND s.daysoverduetolerancedd_3976961L <= 14 - s.delinq_after_days THEN 0
         ELSE s.daysoverduetolerancedd_3976961L END           AS max_days_overdue_hist,
    CASE WHEN s.maxdpdlast24m_143P IS NOT NULL THEN COALESCE(s.maxdpdfrom6mto36m_3546853P, 0) END AS max_dpd_6to36m,
    s.mindbddpdlast24m_3658935P                               AS min_days_late_24m,
    LEAST(s.numinstlswithdpd10_728L, 40)                      AS n_instalments_10d_late,
    s.pctinstlsallpaidlate1d_3546856L                         AS share_instalments_late_1d,
    s.pctinstlsallpaidlate4d_3546849L                         AS share_instalments_late_4d,
    s.pctinstlsallpaidlat10d_839L                             AS share_instalments_late_10d,
    LEAST(s.pctinstlsallpaidearl3d_427L, 1)                   AS share_instalments_early_3d,
    s.numinstpaidearly3d_3546850L                             AS n_instalments_early_3d,
    s.numinstpaidlate1d_3546852L                              AS n_instalments_late_1d,
    s.numinstlsallpaid_934L                                   AS n_instalments_paid,
    s.cntpmts24_3658933L                                      AS n_months_with_payment_24m,
    s.cntincpaycont9m_3716944L                                AS n_incoming_payments_9m,
    s.avginstallast24m_3658937A                               AS avg_instalment_24m,
    s.maxinstallast24m_3658928A                               AS max_instalment_24m,
    s.maxannuity_159A                                         AS max_past_monthly_payment,
    s.maxdebt4_972A                                           AS max_past_debt,
    s.totalsettled_863A                                       AS total_repaid,
    -- ---------------------------------------------------------------- contact / identity sharing (lifetime counts, capped)
    LEAST(s.mobilephncnt_593L, 6)                             AS n_people_same_mobile,
    LEAST(s.clientscnt12m_3712952L, 3)                        AS n_clients_same_mobile_12m,
    LEAST(s.applicationscnt_1086L, 13)                        AS n_apps_same_phone,
    LEAST(s.homephncnt_628L, 5)                               AS n_home_phones,
    -- ---------------------------------------------------------------- credit bureau enquiries, point-in-time windows
    cb.days120_123L - cb.days30_165L                          AS cb_enquiries_1_to_4m,
    cb.days180_256L - cb.days30_165L                          AS cb_enquiries_1_to_6m,
    cb.days360_512L - cb.days30_165L                          AS cb_enquiries_1_to_12m,
    cb.days360_512L - cb.days180_256L                         AS cb_enquiries_6_to_12m,
    CASE WHEN cb.days360_512L IS NULL THEN 0 ELSE 1 END       AS cb_has_enquiry_record
FROM s
LEFT JOIN src_static_cb_0 cb USING (case_id);

SELECT COUNT(*) AS rows, COUNT(DISTINCT case_id) AS cases,
       SUM(CASE WHEN max_dpd_24m IS NOT NULL THEN 1 ELSE 0 END) AS with_repayment_history,
       MIN(cb_enquiries_1_to_6m) AS min_cb_enquiries_1_to_6m
FROM stg_static;
