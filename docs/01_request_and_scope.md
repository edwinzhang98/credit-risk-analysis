# 01 · Request and scope

## The request (verbatim, as received)

> 方向 A，Head of Credit Policy 问：「业务要求提高审批通过率，但坏账率不能涨。现在的 cut-off 有没有调整空间？如果调，哪些人会从拒变批、哪些人会从批变拒，损失多少？」
>
> 公司里这类问题的标准产出是：模型文档（model card）、cut-off / swap-set 分析、策略建议和监控方案。

**English translation.** Head of Credit Policy: "The business wants a higher approval rate, but the bad rate must not go up. Is there room to move the current cut-off? If we move it, who goes from declined to approved, who goes from approved to declined, and how much money is at stake?" The standard outputs for this kind of question are a model card, a cut-off / swap-set analysis, a policy recommendation and a monitoring plan.

## What is actually being decided

| | |
|---|---|
| **Decision** | Which credit decision policy to run for new consumer-loan applications: (a) keep the current scorecard and cut-off, (b) move the cut-off on the current scorecard, or (c) switch to a new model with a new cut-off and a three-tier process (auto-approve / manual review / decline). |
| **Decision maker** | Head of Credit Policy (owns cut-offs and the risk appetite). |
| **Must sign off** | Model Risk / Validation (any model change), Compliance (fair lending, adverse-action reasons), Underwriting Operations (manual-review capacity), Finance (loss and margin assumptions). |
| **What would change the decision** | A new model is worth pursuing only if, on out-of-time data, it (1) approves materially more applicants at the same bad rate or cuts expected loss at the same approval rate, (2) does not create a disparity in approval rates between sexes or age bands beyond the usual 80% (four-fifths) screen, and (3) is stable over time (score PSI below 0.10). If any of these fail, the recommendation is to keep the current scorecard and fix the cut-off only. |
| **Timing** | Input to the next credit-policy committee; the rollout itself would be a controlled champion/challenger test, not a big-bang switch. |

## Clarified analysis questions

1. **Room on the current cut-off.** On the current scorecard, what does the approval-rate vs bad-rate trade-off look like, and where does the cost-based (break-even) cut-off sit? Can approvals go up without the bad rate going up?
2. **Value of a better model.** At the same bad rate, how many more applicants would a stronger model approve? At the same approval rate, how much lower would the bad rate and expected loss be?
3. **Swap set.** If we switch, who swaps in (declined today, approved tomorrow) and who swaps out (approved today, declined tomorrow): how many, what bad rates, how much money?
4. **Cut-off from economics.** Given what a bad loan costs versus what a wrongly declined good applicant costs, which PD cut-off minimises expected loss? How sensitive is it to those cost assumptions?
5. **Grey zone.** Which applicants should go to manual review, how many per month, at what cost, and does that fit current review capacity?
6. **Fair lending.** Which data must not be used, and does the recommended policy approve men and women, and younger and older applicants, at comparable rates?
7. **Monitoring.** How will we know when the model or the cut-off stops working, and what triggers action?

## Scope

**In scope:** application-time PD model (champion scorecard vs challenger), cut-off strategy, swap set, three-tier policy, decline reasons, fairness checks, monitoring plan.

**Out of scope:** risk-based pricing, credit-limit assignment, collections strategy, fraud detection, macro stress testing.

## Constraints that shape the answer

- **Only booked loans have outcomes.** All 1.53M cases in the data were approved under the historical policy (each has a default flag). Every approval rate in this project is therefore a *simulated* approval rate on the historically approved population, not the company's real through-the-door approval rate. Applicants the historical policy rejected are invisible (the reject-inference problem). Swap-in performance for truly rejected applicants needs a small controlled test below the current cut-off; this is part of the recommendation.
- **The incumbent model is not in the data.** We rebuild an equivalent incumbent: a WOE logistic-regression scorecard, the standard production model in consumer lending, and treat it as the champion. The challenger is a gradient-boosted model (LightGBM).
- **Money is in the dataset's local currency (not disclosed).** Absolute amounts are reported in currency units; relative changes (%, percentage points) are the robust numbers.
- **Point-in-time correctness.** Part of the provided data was snapshotted about 14 days after the decision; those fields are rebuilt or removed (see `03_data_quality_checks.md`).

## Success measures

Approval rate at constant bad rate · expected loss and net expected profit (currency units) · bad rate of swap-ins vs swap-outs · manual-review volume vs capacity · approval-rate ratio by sex and age band (≥ 0.80) · score PSI (< 0.10 stable, 0.10 to < 0.25 watch, ≥ 0.25 act).
