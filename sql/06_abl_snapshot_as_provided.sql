-- =====================================================================================================
-- 06_abl_snapshot_as_provided.sql · ABLATION ONLY (not used by the production model)
-- Purpose: rebuild the features the way a naive modeller would, using the provided snapshot fields as-is, so that
--          notebooks/02 can measure how much the ~14-day look-ahead leak inflates offline results.
-- Inputs : table stg_base (sql/01); raw train_applprev_1_*, train_static_0_*, train_static_cb_0 and train_person_1 (applicant income)
-- Output : table abl_features_as_provided, 1 row per case_id, with
--          * the same ap_* columns as int_applprev_pit but computed over ALL previous applications (no "created before
--            the decision" filter, no 15-row window) and with raw snapshot days-past-due;
--          * raw (uncapped) days-past-due maxima under the same names as stg_static;
--          * raw bureau enquiry counts (days30 ... days360) instead of point-in-time window differences;
--          * the dropped snapshot fields: dated "last event" fields as signed days before the decision (negative = after),
--            their companions, short-window and current-status fields.
--          Fairness attributes, interest rate, campaign fields and mid-2019 roll-out columns stay excluded so the
--          comparison isolates the timing leak.
-- Run    : python -m src.db sql/06_abl_snapshot_as_provided.sql
-- =====================================================================================================
CREATE OR REPLACE TEMP TABLE abl_applprev_naive AS
WITH
base AS (
    SELECT case_id, date_decision AS dd FROM stg_base
),
cur AS (   -- current application: amount (static_0) and stated main income (person_1, applicant row)
    SELECT b.case_id, s.credamount_770A AS cur_credamount, p.mainoccupationinc_384A AS cur_income
    FROM base b
    LEFT JOIN read_parquet(getvariable('data_dir') || '/train_static_0_*.parquet', union_by_name = true) s USING (case_id)
    LEFT JOIN (
        SELECT case_id, mainoccupationinc_384A
        FROM read_parquet(getvariable('data_dir') || '/train_person_1.parquet')
        WHERE num_group1 = 0
    ) p USING (case_id)
),
raw AS (
    SELECT a.case_id, a.num_group1, b.dd,
           CAST(a.creationdate_885D AS DATE)          AS c_dt,
           CAST(a.approvaldate_319D AS DATE)          AS appr_dt,
           CAST(a.dtlastpmtallstes_3545839D AS DATE)  AS lastpmt_dt,
           CAST(a.firstnonzeroinstldate_307D AS DATE) AS firstinst_dt,
           a.status_219L                AS status,
           a.credtype_587L              AS credtype,
           a.rejectreason_755M          AS rej_reason,
           a.cancelreason_3545846M      AS canc_reason,
           a.credamount_590A            AS credamount,
           a.annuity_853A               AS annuity,
           a.tenor_203L                 AS tenor,
           a.maxdpdtolerance_577P       AS maxdpd,
           a.mainoccupationinc_437A     AS income,
           a.isbidproduct_390L          AS is_xsell
    FROM read_parquet(getvariable('data_dir') || '/train_applprev_1_*.parquet', union_by_name = true) a
    JOIN base b USING (case_id)
),
ranked AS (
    SELECT *,
           row_number() OVER (PARTITION BY case_id ORDER BY c_dt DESC, num_group1) AS rn,             -- 1 = most recent
           dd - c_dt                                                              AS age_d,
           (appr_dt IS NOT NULL)                                                  AS is_appr,
           (status = 'D')                                                         AS is_rej,
           (status = 'T')                                                         AS is_canc,
           (status IN ('K', 'H', 'Q')
              AND COALESCE(lastpmt_dt, firstinst_dt + to_months(CAST(tenor AS INTEGER))) < dd) AS closed_pre
    FROM raw
),
w AS (
    SELECT *,
           (is_appr AND (status IN ('A', 'N', 'L') OR (status IN ('K', 'H', 'Q') AND lastpmt_dt >= dd))) AS open_dd,
           maxdpd                                                                 AS dpd_safe,      -- naive: raw snapshot value
           CASE WHEN is_appr THEN 'approved' WHEN status = 'D' THEN 'rejected'
                WHEN status = 'T' THEN 'cancelled' ELSE 'other' END               AS outcome
    FROM ranked
),
agg AS (
    SELECT case_id,
        -- volume and velocity
        count(*)                                                AS ap_n_apps,
        count(*) FILTER (WHERE age_d <= 30)                     AS ap_n_apps_30d,
        count(*) FILTER (WHERE age_d <= 90)                     AS ap_n_apps_90d,
        count(*) FILTER (WHERE age_d <= 365)                    AS ap_n_apps_365d,
        min(age_d)                                              AS ap_days_since_last_app,
        max(age_d)                                              AS ap_days_since_first_app,
        -- outcomes
        count(*) FILTER (WHERE is_appr)                         AS ap_n_approved,
        count(*) FILTER (WHERE is_rej)                          AS ap_n_rejected,
        count(*) FILTER (WHERE is_rej AND age_d <= 90)          AS ap_n_rejected_90d,
        count(*) FILTER (WHERE is_rej AND age_d <= 365)         AS ap_n_rejected_365d,
        avg(is_rej::INTEGER)                                    AS ap_share_rejected,
        min(age_d) FILTER (WHERE is_rej)                        AS ap_days_since_last_reject,
        min(dd - appr_dt) FILTER (WHERE is_appr)                AS ap_days_since_last_approval,
        arg_min(outcome, rn)                                    AS ap_last_app_outcome,
        arg_min(rej_reason, rn) FILTER (WHERE is_rej)           AS last_rej_reason_raw,
        arg_min(canc_reason, rn) FILTER (WHERE is_canc)         AS last_canc_reason_raw,
        arg_min(credamount, rn) FILTER (WHERE is_rej)           AS ap_last_rej_credamount,
        -- terms of previous approved loans
        arg_min(credamount, rn) FILTER (WHERE is_appr)          AS ap_last_appr_credamount,
        avg(credamount) FILTER (WHERE is_appr)                  AS ap_mean_appr_credamount,
        max(credamount) FILTER (WHERE is_appr)                  AS ap_max_appr_credamount,
        avg(annuity) FILTER (WHERE is_appr AND annuity > 0)     AS ap_mean_appr_annuity,
        arg_min(tenor, rn) FILTER (WHERE is_appr)               AS ap_last_appr_tenor,
        avg((credtype = 'CAL')::INTEGER) FILTER (WHERE credtype IS NOT NULL) AS ap_share_cash_apps,
        avg(is_xsell::INTEGER)                                  AS ap_share_xsell_apps,
        -- repayment behaviour (point-in-time safe DPD, R3)
        max(dpd_safe)                                           AS ap_max_dpd_safe,
        avg((maxdpd > 0)::INTEGER) FILTER (WHERE closed_pre AND maxdpd IS NOT NULL) AS ap_share_closed_late,
        count(*) FILTER (WHERE dpd_safe > 30)                   AS ap_n_loans_dpd30,
        count(*) FILTER (WHERE closed_pre AND maxdpd = 0)       AS ap_n_repaid_ontime,
        -- exposure on loans open at the decision (R3)
        sum(annuity) FILTER (WHERE open_dd)                     AS ap_sum_open_annuity,
        -- income stated on the most recent previous application that has one
        arg_min(income, rn)                                     AS ap_last_income
    FROM w
    GROUP BY case_id
)
SELECT
    b.case_id,
    COALESCE(g.ap_n_apps, 0)            AS ap_n_apps,
    COALESCE(g.ap_n_apps_30d, 0)        AS ap_n_apps_30d,
    COALESCE(g.ap_n_apps_90d, 0)        AS ap_n_apps_90d,
    COALESCE(g.ap_n_apps_365d, 0)       AS ap_n_apps_365d,
    g.ap_days_since_last_app,
    g.ap_days_since_first_app,
    g.ap_n_approved,
    COALESCE(g.ap_n_rejected, 0)        AS ap_n_rejected,
    COALESCE(g.ap_n_rejected_90d, 0)    AS ap_n_rejected_90d,
    COALESCE(g.ap_n_rejected_365d, 0)   AS ap_n_rejected_365d,
    g.ap_share_rejected,
    g.ap_days_since_last_reject,
    g.ap_days_since_last_approval,
    COALESCE(g.ap_last_app_outcome, 'no_history') AS ap_last_app_outcome,
    CASE WHEN g.ap_n_apps IS NULL THEN 'no_history'
         WHEN g.last_rej_reason_raw IS NULL THEN 'never_rejected'
         WHEN g.last_rej_reason_raw = 'a55475b1' THEN 'not_recorded'
         WHEN g.last_rej_reason_raw IN ('P94_109_143', 'P99_56_166', 'P45_84_106', 'P198_131_9') THEN g.last_rej_reason_raw
         ELSE 'other' END               AS ap_last_reject_reason,
    CASE WHEN g.ap_n_apps IS NULL THEN 'no_history'
         WHEN g.last_canc_reason_raw IS NULL THEN 'never_cancelled'
         WHEN g.last_canc_reason_raw = 'a55475b1' THEN 'not_recorded'
         WHEN g.last_canc_reason_raw IN ('P73_130_169', 'P180_60_137', 'P198_89_166', 'P85_114_140', 'P24_27_36',
                                         'P141_135_146', 'P11_56_131', 'P19_105_83') THEN g.last_canc_reason_raw
         ELSE 'other' END               AS ap_last_cancel_reason,
    g.ap_last_rej_credamount,
    g.ap_last_appr_credamount,
    g.ap_mean_appr_credamount,
    g.ap_max_appr_credamount,
    c.cur_credamount / NULLIF(g.ap_mean_appr_credamount, 0)       AS ap_ratio_cur_to_mean_prev_amt,
    g.ap_mean_appr_annuity,
    g.ap_last_appr_tenor,
    g.ap_share_cash_apps,
    g.ap_share_xsell_apps,
    g.ap_max_dpd_safe,
    g.ap_share_closed_late,
    COALESCE(g.ap_n_loans_dpd30, 0)     AS ap_n_loans_dpd30,
    g.ap_n_repaid_ontime,
    COALESCE(g.ap_sum_open_annuity, 0)  AS ap_sum_open_annuity,
    COALESCE(g.ap_sum_open_annuity, 0) / NULLIF(c.cur_income, 0)  AS ap_open_annuity_to_income,
    g.ap_last_income,
    c.cur_income / NULLIF(g.ap_last_income, 0)                    AS ap_income_ratio_cur_to_last
FROM base b
LEFT JOIN agg g USING (case_id)
LEFT JOIN cur c USING (case_id);


CREATE OR REPLACE TEMP VIEW src_static_0 AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_static_0_*.parquet', union_by_name = true);
CREATE OR REPLACE TEMP VIEW src_static_cb_0 AS SELECT * FROM read_parquet(getvariable('data_dir') || '/train_static_cb_0.parquet');

CREATE OR REPLACE TABLE abl_features_as_provided AS
SELECT
    b.case_id,
    -- previous applications, naive (ALL rows, raw DPD)
    n.* EXCLUDE (case_id),
    -- raw days-past-due maxima (no point-in-time cap), same names as the production features
    x.maxdpdlast6m_474P                   AS max_dpd_6m,
    x.maxdpdlast9m_1059P                  AS max_dpd_9m,
    x.maxdpdlast12m_727P                  AS max_dpd_12m,
    x.maxdpdlast24m_143P                  AS max_dpd_24m,
    x.maxdpdtolerance_374P                AS max_dpd_ever,
    x.daysoverduetolerancedd_3976961L     AS max_days_overdue_hist,
    x.maxdbddpdtollast12m_3658940P        AS max_days_late_12m,
    -- raw bureau enquiry counts (the "30 days" window really covers decision -16d to +14d)
    cb.days30_165L                        AS raw_cb_enquiries_30d,
    cb.days90_310L                        AS raw_cb_enquiries_90d,
    cb.days120_123L                       AS raw_cb_enquiries_120d,
    cb.days180_256L                       AS raw_cb_enquiries_180d,
    cb.days360_512L                       AS raw_cb_enquiries_360d,
    -- dated "last event" fields as signed days before the decision (negative = after the decision)
    DATEDIFF('day', TRY_CAST(x.lastapplicationdate_877D AS DATE), b.date_decision)  AS raw_days_since_last_application,
    DATEDIFF('day', TRY_CAST(x.lastrejectdate_50D AS DATE), b.date_decision)        AS raw_days_since_last_rejection,
    DATEDIFF('day', TRY_CAST(x.lastapprdate_640D AS DATE), b.date_decision)         AS raw_days_since_last_approval,
    DATEDIFF('day', TRY_CAST(x.lastactivateddate_801D AS DATE), b.date_decision)    AS raw_days_since_last_activation,
    DATEDIFF('day', TRY_CAST(x.lastdelinqdate_224D AS DATE), b.date_decision)       AS raw_days_since_last_delinquency,
    DATEDIFF('day', TRY_CAST(x.datelastunpaid_3546854D AS DATE), b.date_decision)   AS raw_days_since_last_unpaid,
    DATEDIFF('day', TRY_CAST(x.maxdpdinstldate_3546855D AS DATE), b.date_decision)  AS raw_days_since_worst_instalment,
    DATEDIFF('day', TRY_CAST(x.firstdatedue_489D AS DATE), b.date_decision)         AS raw_days_since_first_due,
    -- companions of those events, as provided
    x.lastst_736L                         AS raw_last_status,
    x.lastrejectreason_759M               AS raw_last_reject_reason,
    x.lastcancelreason_561M               AS raw_last_cancel_reason,
    x.lastrejectcredamount_222A           AS raw_last_reject_amount,
    x.lastapprcredamount_781A             AS raw_last_approved_amount,
    x.maininc_215A                        AS raw_income_last_approved_app,
    x.maxdpdinstlnum_3546846P             AS raw_worst_instalment_number,
    -- short-window and current-status snapshot fields
    x.applications30d_658L                AS raw_applications_30d,
    x.numcontrs3months_479L               AS raw_contracts_3m,
    x.sellerplacecnt_915L                 AS raw_sellerplaces_3m,
    x.numrejects9m_859L                   AS raw_rejections_9m,
    x.maxdpdlast3m_392P                   AS raw_max_dpd_3m,
    x.actualdpdtolerance_344P             AS raw_current_dpd,
    x.currdebt_22A                        AS raw_current_debt,
    x.numactivecreds_622L                 AS raw_active_credits,
    x.numinsttopaygr_769L                 AS raw_unpaid_instalments,
    x.numnotactivated_1143L               AS raw_not_activated_credits,
    CAST(x.opencred_647L AS INTEGER)      AS raw_open_credit_flag,
    x.annuitynextmonth_57A                AS raw_annuity_next_month
FROM stg_base b
JOIN abl_applprev_naive n USING (case_id)
JOIN src_static_0 x USING (case_id)
LEFT JOIN src_static_cb_0 cb USING (case_id);

SELECT COUNT(*) AS rows, COUNT(DISTINCT case_id) AS cases,
       AVG((raw_days_since_last_application < 0)::INTEGER) AS share_last_application_after_decision,
       AVG((ap_days_since_last_app < 0)::INTEGER) AS share_naive_ap_after_decision
FROM abl_features_as_provided;
