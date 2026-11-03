-- =====================================================================================================
-- 03_int_applprev_pit.sql · Point-in-time features from the client's previous applications with this lender
-- Inputs : table stg_base (sql/01_stg_base.sql)
--          train_applprev_1_*.parquet (raw; many rows per case, num_group1 = 0 is the most recent)
--          train_static_0_*.parquet (raw; current loan amount) and train_person_1.parquet (raw; applicant income)
-- Output : table int_applprev_pit, 1 row per case_id (1,526,659 rows), 33 columns prefixed ap_
--          Clients with no earlier application: counts = 0, other numerics NULL, categoricals = 'no_history'
--          (ap_n_approved and ap_n_repaid_ontime stay NULL so "no history" is not merged with "history, none approved").
--
-- Point-in-time rules (why: the source snapshot was taken ~14 days AFTER the decision, see docs/03)
--   R1  Only applications created strictly before the decision date are used (removes 144,679 rows, 2.2%).
--   R2  The source keeps at most 20 rows per case INCLUDING post-decision rows, so a client who applied again after the
--       decision would show fewer pre-decision rows. Only the 15 most recent pre-decision rows are used, which makes the
--       window independent of post-decision activity for all but 171 cases (99.99%).
--   R3  Status, DPD and balances were captured at the snapshot (decision + 14 days):
--       * "approved" = approval date before the decision (an event date), not the snapshot status;
--         "rejected" = status D, "cancelled" = status T (both fixed at application time).
--       * A previous contract is "closed before the decision" when its status is closed (K/H/Q) AND its last payment
--         (or scheduled end) is before the decision: its max days-past-due is final and used as is.
--       * For every other contract, max DPD is reduced by 14 days and floored at 0. DPD grows by at most 1 day per day,
--         so this is a guaranteed lower bound of what was known at the decision. (Evidence the raw value leaks:
--         of the earlier contracts whose first instalment falls after the decision, 3.7% of those with a recorded DPD
--         already show DPD 1-14 (858 rows); their loans default at 14.0% vs 4.2% for the other rows.)
--       * Snapshot balances (current debt, outstanding debt, actual DPD, card balances) are not used. Exposure at the
--         decision is rebuilt from the instalments of contracts approved before and not closed before the decision.
--   R4  Fair lending: education, family state, district, number of children and profession are never read.
-- Status codes (decoded from the data, see notebooks/02): D declined, T cancelled, A active, N approved not yet
-- activated, L delinquent/collections, K repaid and closed, H/Q old closed contracts.
-- Run    : python -m src.db sql/03_int_applprev_pit.sql
-- =====================================================================================================
CREATE OR REPLACE TABLE int_applprev_pit AS
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
    WHERE CAST(a.creationdate_885D AS DATE) < b.dd                                                   -- R1
),
ranked AS (
    SELECT *,
           row_number() OVER (PARTITION BY case_id ORDER BY c_dt DESC, num_group1) AS rn,             -- 1 = most recent
           dd - c_dt                                                              AS age_d,
           (appr_dt IS NOT NULL AND appr_dt < dd)                                 AS is_appr,
           (status = 'D')                                                         AS is_rej,
           (status = 'T')                                                         AS is_canc,
           (status IN ('K', 'H', 'Q')
              AND COALESCE(lastpmt_dt, firstinst_dt + to_months(CAST(tenor AS INTEGER))) < dd) AS closed_pre
    FROM raw
),
w AS (
    SELECT *,
           (is_appr AND (status IN ('A', 'N', 'L') OR (status IN ('K', 'H', 'Q') AND lastpmt_dt >= dd))) AS open_dd,
           CASE WHEN maxdpd IS NULL THEN NULL
                WHEN closed_pre     THEN maxdpd
                ELSE GREATEST(maxdpd - 14, 0) END                                 AS dpd_safe,                -- R3
           CASE WHEN is_appr THEN 'approved' WHEN status = 'D' THEN 'rejected'
                WHEN status = 'T' THEN 'cancelled' ELSE 'other' END               AS outcome
    FROM ranked
    WHERE rn <= 15                                                                                   -- R2
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

SELECT COUNT(*) AS rows, COUNT(DISTINCT case_id) AS cases, AVG((ap_n_apps > 0)::INTEGER) AS share_with_history,
       MIN(ap_days_since_last_app) AS min_days_since_last_app, MAX(ap_n_apps) AS max_apps_used
FROM int_applprev_pit;
