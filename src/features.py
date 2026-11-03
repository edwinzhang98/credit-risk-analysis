"""Feature catalog: every model input with a plain-English label, a business group and its expected risk direction.

Labels double as decline-reason text, so they are written for a credit officer, not a data scientist.
Direction: "up" = higher value means higher risk, "down" = lower risk, "mixed" = not monotonic / categorical.
"""
from __future__ import annotations

import pandas as pd

ID_COLS = ["case_id", "date_decision", "decision_month", "split", "target"]
SEGMENT_COLS = ["is_new_to_lender"]
FAIR_COLS = ["fair_sex", "fair_age_years", "fair_income_type"]

# name: (label, group, direction)
CATALOG: dict[str, tuple[str, str, str]] = {
    # ---- loan terms (known at application)
    "loan_amount": ("Loan amount requested", "Loan terms", "mixed"),
    "monthly_payment": ("Monthly payment on this loan", "Loan terms", "mixed"),
    "loan_term_months": ("Loan term (months)", "Loan terms", "up"),
    "product_type": ("Product (cash, point-of-sale or card)", "Loan terms", "mixed"),
    "initial_transaction_type": ("How the loan is paid out", "Loan terms", "mixed"),
    "is_cross_sell": ("Loan offered to an existing client", "Loan terms", "down"),
    "down_payment": ("Down payment amount", "Loan terms", "down"),
    "goods_price": ("Price of the goods financed", "Loan terms", "mixed"),
    "disbursed_amount": ("Amount paid out at the start", "Loan terms", "mixed"),
    "down_payment_share": ("Down payment as share of the price", "Loan terms", "down"),
    "disbursed_share": ("Share of the limit drawn at the start", "Loan terms", "up"),
    # ---- affordability
    "income_main": ("Declared monthly income", "Affordability", "down"),
    "employment_years": ("Years with current employer", "Affordability", "down"),
    "payment_to_income": ("Monthly payment as share of income", "Affordability", "up"),
    "loan_to_income": ("Loan amount relative to income", "Affordability", "up"),
    "payment_vs_past_instalment": ("New payment vs past average instalment", "Affordability", "up"),
    "payment_vs_max_past_payment": ("New payment vs largest past payment", "Affordability", "up"),
    "loan_vs_max_past_debt": ("New loan vs largest past debt", "Affordability", "up"),
    "ap_sum_open_annuity": ("Payments on other open loans with us", "Affordability", "mixed"),
    "ap_open_annuity_to_income": ("Other open loans' payments vs income", "Affordability", "up"),
    "ap_last_income": ("Income stated on last application", "Affordability", "down"),
    "ap_income_ratio_cur_to_last": ("Stated income now vs last application", "Affordability", "up"),
    # ---- internal repayment history
    "avg_dpd_24m": ("Average days late, last 24 months", "Repayment history", "up"),
    "avg_days_late_24m": ("Average payment lateness, last 24 months", "Repayment history", "up"),
    "avg_worst_dpd_9m": ("Average worst lateness, last 9 months", "Repayment history", "up"),
    "max_days_late_12m": ("Latest payment in the last 12 months (days)", "Repayment history", "up"),
    "max_dpd_6m": ("Worst days past due, last 6 months", "Repayment history", "up"),
    "max_dpd_9m": ("Worst days past due, last 9 months", "Repayment history", "up"),
    "max_dpd_12m": ("Worst days past due, last 12 months", "Repayment history", "up"),
    "max_dpd_24m": ("Worst days past due, last 24 months", "Repayment history", "up"),
    "max_dpd_ever": ("Worst days past due on record", "Repayment history", "up"),
    "max_days_overdue_hist": ("Worst days overdue on past instalments", "Repayment history", "up"),
    "max_dpd_6to36m": ("Worst days past due, 6-36 months ago", "Repayment history", "up"),
    "min_days_late_24m": ("Least-late payment, last 24 months", "Repayment history", "up"),
    "n_instalments_10d_late": ("Instalments paid 10+ days late", "Repayment history", "up"),
    "share_instalments_late_1d": ("Share of instalments paid late", "Repayment history", "up"),
    "share_instalments_late_4d": ("Share of instalments 4+ days late", "Repayment history", "up"),
    "share_instalments_late_10d": ("Share of instalments 10+ days late", "Repayment history", "up"),
    "share_instalments_early_3d": ("Share of instalments paid early", "Repayment history", "down"),
    "n_instalments_early_3d": ("Instalments paid 3+ days early", "Repayment history", "down"),
    "n_instalments_late_1d": ("Instalments paid late", "Repayment history", "up"),
    "n_instalments_paid": ("Instalments paid to date", "Repayment history", "down"),
    "n_months_with_payment_24m": ("Months with a payment, last 24 months", "Repayment history", "down"),
    "n_incoming_payments_9m": ("Payments received, last 9 months", "Repayment history", "down"),
    "avg_instalment_24m": ("Average past instalment", "Repayment history", "down"),
    "max_instalment_24m": ("Largest past instalment", "Repayment history", "down"),
    "max_past_monthly_payment": ("Largest past monthly payment", "Repayment history", "mixed"),
    "max_past_debt": ("Largest past debt (4+ months ago)", "Repayment history", "down"),
    "total_repaid": ("Total repaid on past loans", "Repayment history", "down"),
    "net_punctuality": ("Early minus late payment share", "Repayment history", "down"),
    "dpd_worsening": ("Lateness got worse in last 6 months", "Repayment history", "up"),
    "has_repayment_history": ("Has a repayment record with us", "Repayment history", "mixed"),
    # ---- previous applications with this lender (point in time)
    "ap_n_apps": ("Previous applications (last 15)", "Previous applications", "up"),
    "ap_n_apps_30d": ("Applications in the last 30 days", "Previous applications", "up"),
    "ap_n_apps_90d": ("Applications in the last 90 days", "Previous applications", "up"),
    "ap_n_apps_365d": ("Applications in the last 12 months", "Previous applications", "up"),
    "ap_days_since_last_app": ("Days since last application", "Previous applications", "down"),
    "ap_days_since_first_app": ("Length of application history (days)", "Previous applications", "down"),
    "ap_n_approved": ("Previous applications approved", "Previous applications", "down"),
    "ap_n_rejected": ("Previous applications rejected", "Previous applications", "up"),
    "ap_n_rejected_90d": ("Rejections in the last 90 days", "Previous applications", "up"),
    "ap_n_rejected_365d": ("Rejections in the last 12 months", "Previous applications", "up"),
    "ap_share_rejected": ("Share of past applications rejected", "Previous applications", "up"),
    "ap_days_since_last_reject": ("Days since last rejection", "Previous applications", "down"),
    "ap_days_since_last_approval": ("Days since last approval", "Previous applications", "mixed"),
    "ap_last_app_outcome": ("Outcome of the last application", "Previous applications", "mixed"),
    "ap_last_reject_reason": ("Reason for the last rejection", "Previous applications", "mixed"),
    "ap_last_cancel_reason": ("Reason for the last cancellation", "Previous applications", "mixed"),
    "ap_last_rej_credamount": ("Amount asked on last rejected application", "Previous applications", "mixed"),
    "ap_last_appr_credamount": ("Amount of last approved loan", "Previous applications", "down"),
    "ap_mean_appr_credamount": ("Average approved loan amount", "Previous applications", "down"),
    "ap_max_appr_credamount": ("Largest approved loan amount", "Previous applications", "down"),
    "ap_ratio_cur_to_mean_prev_amt": ("Requested amount vs average past loan", "Previous applications", "up"),
    "ap_mean_appr_annuity": ("Average monthly payment on past loans", "Previous applications", "down"),
    "ap_last_appr_tenor": ("Term of last approved loan", "Previous applications", "up"),
    "ap_share_cash_apps": ("Share of past applications for cash", "Previous applications", "up"),
    "ap_share_xsell_apps": ("Share of past applications from our offers", "Previous applications", "down"),
    "ap_max_dpd_safe": ("Worst days past due on past loans with us", "Previous applications", "up"),
    "ap_share_closed_late": ("Share of repaid loans ever paid late", "Previous applications", "up"),
    "ap_n_loans_dpd30": ("Past loans more than 30 days late", "Previous applications", "up"),
    "ap_n_repaid_ontime": ("Loans repaid with no late payment", "Previous applications", "down"),
    # ---- credit bureau
    "cb_enquiries_1_to_4m": ("Credit checks 1-4 months before applying", "Credit bureau", "up"),
    "cb_enquiries_1_to_6m": ("Credit checks 1-6 months before applying", "Credit bureau", "up"),
    "cb_enquiries_1_to_12m": ("Credit checks 1-12 months before applying", "Credit bureau", "up"),
    "cb_enquiries_6_to_12m": ("Credit checks 6-12 months before applying", "Credit bureau", "up"),
    "cb_has_enquiry_record": ("Has a credit-bureau enquiry record", "Credit bureau", "mixed"),
    # ---- contact / identity sharing
    "n_people_same_mobile": ("People sharing the applicant's mobile", "Contact details", "up"),
    "n_clients_same_mobile_12m": ("Other clients on the same mobile (12m)", "Contact details", "up"),
    "n_apps_same_phone": ("Past applications using the same phone", "Contact details", "down"),
    "n_home_phones": ("Home phone numbers given", "Contact details", "mixed"),
}

CATEGORICAL = ["product_type", "initial_transaction_type", "ap_last_app_outcome", "ap_last_reject_reason", "ap_last_cancel_reason"]
FEATURES = list(CATALOG)
NUMERIC = [f for f in FEATURES if f not in CATEGORICAL]
LABELS = {k: v[0] for k, v in CATALOG.items()}
GROUPS = {k: v[1] for k, v in CATALOG.items()}
DIRECTION = {k: v[2] for k, v in CATALOG.items()}


def catalog_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [{"feature": k, "label": v[0], "group": v[1], "expected_direction": v[2], "type": "categorical" if k in CATEGORICAL else "numeric"} for k, v in CATALOG.items()]
    )


def check_against_table(columns) -> None:
    """Fail loudly if the catalog and the feature table disagree (a feature added in SQL but not documented, or vice versa)."""
    cols = set(columns) - set(ID_COLS) - set(SEGMENT_COLS) - set(FAIR_COLS)
    missing_in_table = set(FEATURES) - cols
    undocumented = cols - set(FEATURES)
    if missing_in_table or undocumented:
        raise ValueError(f"catalog mismatch: not in table {sorted(missing_in_table)}; not in catalog {sorted(undocumented)}")
