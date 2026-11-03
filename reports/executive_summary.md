# Executive summary: is there room on the cut-off?

**Decision asked for:** Approve cost-based cut-offs and controlled tests before expanding approvals. Test quarter: January to March 2020, 222,681 booked loans; amounts in currency units (CU).

**Answer**

- The rule declines 9.3% of today's approvals, a tail with a 16.6% bad rate. The approved book's bad rate falls from 4.41% to 3.17%; modelled profit rises 92.3M CU a quarter and the total cost of wrong decisions falls 23%.
- Under the two-tier cost rules, the new model approves 1.8 percentage points fewer applicants than the scorecard. Its approved-book bad rate is 3.17% vs 3.57%, 0.4 percentage points lower. Modelled net profit rises 46.3M CU a quarter and modelled credit losses fall 64.6M CU. The trial is sized to detect the bad-rate difference. Separate after-the-fact comparisons on booked test loans show +3.3 percentage points of approvals at the scorecard's bad rate, or 22% lower modelled credit losses at the same approval rate. Each needs its own cut-off fixed in advance and its own test.
- Manual review adds 11.9M CU a quarter assuming a 40% bad catch rate, 10% good-decline rate and 300 CU a review. The range is 1.8M to 32.0M CU at 20% to 60% catch rates, holding other assumptions fixed. Capacity is 5% of each month's applications, averaging 3,711 reviews monthly.
- The below-cut-off test passes if at most 83 of 610 approved loans default (13.6%). It passes 82% of the time at the 25%-lower target rate of 12.5%. If the true rate is at that target, each declined tail loan funds about 1.5 new approvals, about 10,600 more loans a quarter; expansion uses the measured rate. Expected net cost is 2.7M CU on the declined tail's economics, likely more because today's rejects are probably riskier.

**Approvals requested**

| Owner | Approve |
|---|---|
| Credit Policy, Finance | Cost assumptions and rule; capped below-cut-off test and its budget |
| Model Validation, Credit Policy | Trial of the two-tier cost rules: 20% of traffic to the new model, 20,544 approved loans in its group and 82,176 scorecard loans |
| Underwriting Operations | Separate review pilot outside trial arms; measure catch rate before counting its gain |
| Compliance | Exclusions, decline reasons and lawful remedies for group risk under-prediction |
| Risk Analytics | Applicant-mix checks monthly; early delinquency at month 3 on book; detection speed not back-tested |

Trial bad-rate tolerance of 0.2 percentage points and early-delinquency alerts at +20% to investigate / +40% to act are proposals in `config.yaml` (`proposals`), to be agreed before launch.

**Key risks:** Booked loans only; rejects' outcomes are unknown. Today's policy approved every booked loan; a 0.5 cut-off is almost the same. At the assumed 60% loss rate, defaults imply 393.3M CU of modelled losses; money depends on assumed margins and loss rate. Test-quarter risk estimates are about 10% low for the new model and 14% low for the scorecard. Approval rates pass the four-fifths screen, but estimates for men and ages 18-24 are about 73% of actual default rates. Jurisdiction is undisclosed.

Detail: [decision memo](../docs/readout.md) · [full report](report.html)
