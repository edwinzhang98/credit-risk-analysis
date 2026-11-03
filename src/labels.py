"""Readable column headers for tables shown to business readers (HTML report and dashboard). Keys are the cached-table column names."""
from __future__ import annotations

COLUMN_LABELS = {
    # policies and money
    "model": "Model", "policy": "Policy", "threshold": "PD cut-off", "approval_rate": "Approval rate", "approved": "Approved",
    "bad_rate_approved": "Bad rate of approved", "bad_rate_approved_by_amount": "Bad rate of approved (by amount)",
    "capture_rate": "Defaults declined (capture)", "false_positive_rate": "Good customers declined", "decline_precision": "Bad rate of declined",
    "credit_loss": "Credit loss (CU)", "forgone_margin": "Margin forgone (CU)", "total_cost": "Total cost of wrong decisions (CU)",
    "net_profit": "Net profit (CU)", "cost_vs_today": "Total cost vs today's policy", "approved_amount": "Amount approved (CU)",
    "product": "Product", "product_name": "Product", "margin_good": "Margin of a good loan", "loss_bad": "Loss on a bad loan",
    "cost_ratio": "Bad loan cost ÷ good loan margin", "breakeven_pd": "Break-even PD", "loans": "Loans", "median_amount": "Median loan (CU)",
    "applications": "Applications", "share": "Share", "bads": "Defaults", "bad_rate": "Bad rate", "bad_rate_ci_low": "95% CI low",
    "bad_rate_ci_high": "95% CI high", "loan_amount": "Loan amount (CU)", "credit_loss_if_approved": "Credit loss if approved (CU)",
    "margin_if_approved": "Margin if approved (CU)", "net_value_if_approved": "Net value if approved (CU)", "cell": "Cell", "comparison": "Comparison",
    # headroom and tests
    "swap_in_bad_rate": "Bad rate of new approvals", "swap_in_bad_rate_vs_book": "× book bad rate",
    "new_approvals_per_decline": "New approvals per declined loan", "swap_ins_affordable": "New approvals affordable",
    "swap_ins_per_month": "New approvals per month", "net_change_in_approvals": "Net change in approvals",
    "net_change_per_month": "Net change in approvals per month", "test": "Test", "question": "Question", "loans_needed": "Loans needed", "note": "Note",
    # swap profile
    "share_cash": "Share cash loans", "share_pos": "Share point-of-sale", "share_new_to_lender": "Share new to lender",
    "mean_pd_champion": "Mean PD, champion", "mean_pd_challenger": "Mean PD, challenger",
    # tiers and review
    "tier": "Tier", "per_month": "Per month", "approved_bads": "Approved defaults", "margin": "Margin (CU)", "review_cost": "Review cost (CU)",
    "bad_catch_rate": "Reviewer catch rate", "good_decline_rate": "Good applicants declined by reviewers", "review_share": "Review share",
    "net_profit_uplift_vs_two_tier": "Gain vs two-tier rule (CU)",
    # fairness
    "attribute": "Attribute", "group": "Group", "approval_rate_ratio": "Approval-rate ratio", "observed_bad_rate": "Observed bad rate",
    "bad_rate_approved_ci_low": "95% CI low", "bad_rate_approved_ci_high": "95% CI high", "passes_four_fifths": "Passes four-fifths screen",
    "auc_from_model_inputs": "AUC predicting it from model inputs",
    # model performance
    "window": "Window", "mean_pd": "Mean predicted PD", "calibration_ratio": "Calibration ratio", "auc": "AUC", "gini": "Gini", "ks": "KS",
    "brier": "Brier score", "segment": "Segment", "share_of_test": "Share of test loans", "valid_gini": "Gini, validation", "test_gini": "Gini, out-of-time test",
    "approach": "Approach", "test_auc": "Test AUC", "test_brier_raw": "Test Brier (raw output)", "mean_pd_raw": "Mean raw output",
    "approval_rate_if_cutoff_on_raw_output": "Approval rate if the rule uses raw output", "net_profit_if_cutoff_on_raw_output": "Net profit if the rule uses raw output (CU)",
    "approval_rate_after_recalibration": "Approval rate after recalibration", "net_profit_after_recalibration": "Net profit after recalibration (CU)",
    "feature": "Input", "label": "Description", "iv": "Information value", "coefficient": "Coefficient",
    "view": "View", "rule_approval_rate": "Rule: approval rate", "rule_bad_rate_of_approved": "Rule: bad rate of approved", "rule_net_profit": "Rule: net profit (CU)",
    "scenario": "Scenario", "breakeven_cash": "Break-even, cash", "breakeven_pos": "Break-even, point-of-sale", "breakeven_revolving": "Break-even, revolving",
    "net_profit_gain_vs_approve_all": "Gain vs today's policy (CU)",
    # data quality and leakage
    "source_table": "Source table", "grain": "Grain", "n_rows": "Rows", "n_cases": "Loans", "share_of_base_cases": "Share of booked loans",
    "n_orphan_cases": "Loans missing from the base table", "check_name": "Check", "violations": "Violations", "expected": "Expected", "status": "Status",
    "rule": "Rule", "n_loans": "Loans", "action": "Action", "match_rate": "Match rate", "first_month": "First month flagged", "months_flagged": "Months flagged",
    "max_csi": "Max CSI", "expected_bad_rate_of_approved": "Expected bad rate of approved", "observed_bad_rate_of_approved": "Observed bad rate of approved",
}
