# Decision memo: room on the cut-off

**To:** Head of Credit Policy
**From:** Credit Risk Analyst, Consumer Lending
**Date:** 3 November 2026
**Subject:** Room on the cut-off: tighten now, test before loosening, trial the new model

## Bottom line

On the current scorecard there is room to tighten and none we can prove to loosen: the approvals it should stop making defaulted at 14.9%, against 4.41% for the book. A cut-off set from what a wrong decision costs, run on the new model, would decline 9.3% of the applicants we approved in January to March 2020, lower the book's bad rate to 3.17% and add 92.3M CU a quarter against today's policy (95% interval 86.0M to 98.7M); at the scorecard's bad rate instead, the new model approves 3.3 percentage points more applicants (2.9 to 3.6). Whether we can also approve people we reject today cannot be read from our data, because their outcomes were never observed; a test of about 589 loans just below today's approval line, with expected net losses of 2.6M CU or more, would answer it.

## What we recommend

Out-of-time test quarter (January to March 2020, 222,681 booked loans); money in the dataset's currency units (CU). The current scorecard is the champion, a stand-in we rebuilt because the lender's incumbent model is not in the data; the new model is the LightGBM challenger. Gains are measured against today's policy, which approved every loan in this book (a 0.5 cut-off approves 99.98% of it and lands in the same place); intervals are 95% ranges from 200 resamples of the test quarter. Monthly volumes are booked loans: the review queue and test durations must be reset on through-the-door volume, which is not in our data.

| # | For whom | What to do | Expected impact | How we measure it | Main risk |
|---|---|---|---|---|---|
| 1 | Credit Policy | Approve when expected profit is positive: estimated chance of default below 25.0% (cash), 14.3% (revolving), 7.7% (point-of-sale) | Declines 9.3% of today's approvals (bad rate 16.6%); book bad rate 3.17%; credit losses down 35% and total cost of wrong decisions down 23% versus today's policy; +92.3M CU a quarter (86.0M to 98.7M) | Approval rate and bad rate by vintage | Margins are assumptions; Finance to confirm |
| 2 | Model Validation | Controlled trial of the new model on 20% of applications | Versus a rebuilt scorecard under the same rule: +3.3 pp approvals at its bad rate (2.9 to 3.6; about 2,458 booked loans a month), or 22% lower credit losses at its approval rate (20% to 23%) | 32,438 approved loans per arm (about 2.4 months on booked volume); early read at month 3 | Less transparent; every decline needs a plain-language reason |
| 3 | Credit Policy, Finance | Below-cut-off test: random sample just below today's approval line (applicants the current policy rejects), amounts capped | Measures the bad rate of today's rejects, which decides whether approvals can rise; a pass (12.5% or less) funds about 1.5 new approvals per declined loan, about 10,600 more loans a quarter at an unchanged book bad rate | 589 approved test loans; bad rate against the declined tail's 16.6% | Expected net losses of about 2.6M CU (4,474 CU a loan) are a floor: today's rejects are probably riskier than the tail they are priced on |
| 4 | Underwriting Operations | Manual-review tier for the grey zone, within capacity; log every outcome | 86.6% auto-approve, 5.0% review (3,711 a month), 8.4% decline; +11.8M CU a quarter if reviewers catch 40% of bad applicants | Reviewer catch rate, cost per case | The 40% is an assumption; no review data yet |
| 5 | Compliance | Sign off excluded attributes and decline reasons; rule on equal approval rates versus equal accuracy by sex and age | Documented fair-lending position before go-live | Approval-rate ratio and estimate accuracy by group | Inputs still carry age information |
| 6 | Risk Analytics | Monthly monitoring: applicant mix, early delinquency, estimate accuracy | Population and outcome shifts caught within one to three months | Alerts raised and actioned | In April to October 2020 the new model's score mix stayed within limits (stability index at most 0.08) while the bad rate halved; the scorecard's index reached 0.15, but in step with a collapse in the employment field's fill rate, not with the outcome shift |

## Why

- A bad loan costs about 60% of its amount; a wrongly declined good customer costs the product's margin (20% cash, 10% revolving, 5% point-of-sale). Today's policy approved every loan in this book and paid the full credit loss, 393.3M CU on the quarter (a 0.5 cut-off approves 99.98% of the book and pays almost all of it, 391.4M CU).
- The rule on the new model declines 20,627 loans (1,062.4M CU lent) that defaulted at 16.6%: 139.2M CU of losses avoided, 46.9M CU of margin given up, 92.3M CU net. On the scorecard the same rule declines 7.5% (bad rate 14.9%), worth 45.9M CU, leaving the book at 3.57%. Most of the new model's edge comes from using more of the available information (90 inputs against the scorecard's 16), not from the algorithm. Under the recommended rule, 8,708 loans (576.0M CU) move from approved to declined (swap-outs) and defaulted at 14.7%; 4,776 (150.4M CU) move the other way (swap-ins) and defaulted at 7.1%, a gap of 7.6 points (6.6 to 8.6).
- Approval rates: 90.8% women, 90.6% men; lowest age-band ratio 0.89 (18 to 24), above the 0.80 screen. The model under-states the risk of men and of 18 to 24-year-olds by about a quarter; employment status does not fix it and stays out.

## What the data cannot tell us, and how we will find out

Every loan in the data was approved under the old policy, so the approval rates above are shares of previously approved applicants and the bad rate of past rejects is unknown: tightening is measured, loosening is not. A declined tail loan funds new approvals at an unchanged book bad rate only if the newcomers default less often than the tail's 16.6%: 2.8 new approvals per declined loan if they default at 8.8%, 1.5 at 12.5%, 1.4 at 13.2%, one for one (no net gain) at 16.6%. The below-cut-off test answers this: about 589 approved loans from applicants just below today's approval line, those the current policy rejects, tell whether they default at 12.5% or less (a quarter below the tail); a pass would fund about 1.5 new approvals per declined loan, about 10,600 more loans a quarter. The expected net loss, about 4,474 CU a loan (2.6M CU in all), is priced on our declined tail and is a floor, because today's rejects are probably riskier; the test's duration depends on today's reject volume, which is not in our data.

The 2020 back-test of the monitoring plan is illustrative: from April 2020 the bad rate halves in one step and then stays flat, and the fall may reflect COVID-era measures, the lender's own tightening or loans too recent to have defaulted (the outcome horizon is not disclosed); the data cannot separate these.

## What we need from you

1. Adopt the cost-based rule (you), once Finance confirms the margin, loss and exposure assumptions.
2. Approve the 20% controlled trial and its written decision rule (you), after Model Validation's review.
3. Approve the below-cut-off test and its expected net loss of 2.6M CU or more (you, Finance).
4. Confirm review capacity (3,711 cases a month on booked volume) and cost per case (300 CU assumed) (Underwriting Operations).
5. Sign off excluded attributes, decline reasons and the equal-approval versus equal-accuracy question (Compliance).

## Next steps and timing

- Weeks 1 to 4: Finance confirms the cost assumptions; Model Validation reviews the new model; Compliance reviews attributes and decline reasons; decision rules for both tests signed; monitoring built; risk estimates refreshed on the latest mature vintages (about 10% low on the test quarter).
- Months 2 to 4: the trial collects 32,438 approved loans per arm (about 2.4 months on booked volume; the calendar is set by through-the-door volume); the below-cut-off test runs alongside until 589 loans are booked.
- Month 3 on book: early read from 30+ days past due; after the outcome window, go/no-go on the model switch and on any loosening.
