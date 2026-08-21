# Metric definitions

**Metric contract owner:** Finance + Sales Operations  
**Reporting cut-off for this case:** 2026-06-30  
**Primary grains:** billing `account_id` for revenue metrics; CRM `opportunity_id` for funnel metrics.

The guiding principle is to separate **revenue truth** from **sales-process truth**. Billing is the stated source of record for ARR; CRM opportunities describe funnel activity and bookings. Corporate parent/child relationships are a reporting roll-up, not a reason to merge billing account IDs.

## 1. Active ARR

**Plain-English definition.** Annualised recurring revenue under contract on the as-of date.

**Grain.** Calculated at subscription line, then summed to billing account and any requested reporting slice.

**Inclusions.** A subscription contributes when `term_start_date <= as_of_date < effective_end_date`, where `effective_end_date` is the earlier of the contractual `term_end_date` and the successor subscription's `term_start_date` when `replaced_by_subscription_id` is populated.

**Exclusions.** Future terms do not contribute. A predecessor stops contributing when its replacement begins even if its original term end is later. I do **not** use `status='Active'` as the eligibility rule because status is a current-state field and the data contains future-dated successors already marked Active. Test/deleted CRM records are not used to override valid billing contracts; if billing ever showed active ARR on one of those accounts I would escalate it rather than silently discard revenue.

**Currency.** Each active line is converted with the observed spot FX rate on the as-of date (`amount_local * rate_to_usd`). If an exact date were missing, I would use the latest observed rate on or before the date and flag the stale-rate age.

**Edge case that made me stop.** 52 amended subscription terms overlap their successors if dates are used naïvely. At 2026-06-30, 16 predecessors are marked `Amended` even though their replacement has not started yet, while future successors are already marked `Active`. Date-only logic overstates ARR; status-only logic understates it. Clipping the predecessor to the replacement start produces non-overlapping effective terms.

## 2. Net New ARR

**Plain-English definition.** The change in recurring revenue over a period, decomposed into New, Expansion, Contraction, and Churn.

**Grain.** Account at the two period boundaries. Product-line activity is first resolved into effective subscription terms, then aggregated to account.

**Exact rules.** For each account, compare ARR at the start and end boundary:

- **New ARR:** start = 0, end > 0.
- **Expansion ARR:** start > 0 and end > start; contribution = end - start.
- **Contraction ARR:** start > 0 and 0 < end < start; contribution = start - end.
- **Churn ARR:** start > 0 and end = 0; contribution = start.
- **Net New ARR = New + Expansion - Contraction - Churn**, which reconciles exactly to ending ARR minus opening ARR under constant currency.

**Currency.** Both opening and ending ARR are converted with the **period-end FX rate**. This deliberately removes FX movement from Net New ARR; otherwise exchange-rate changes would masquerade as customer growth or contraction.

**Edge case.** An account can have several products and a mid-term amendment. I classify movement only after all effective product lines have been aggregated to account, preventing an amendment from appearing as simultaneous churn and new ARR.

**Stakeholder confirmation.** I would ask the CFO whether a reactivated logo should be reported separately from New ARR. In this version, an account at zero on the opening boundary and positive on the ending boundary is New ARR for the reconciliation, with reactivation available as a future subcategory if Finance wants it.

## 3. Gross Revenue Retention (GRR) and Net Revenue Retention (NRR)

**Plain-English definition.** Retention of the opening customer cohort. GRR asks how much opening ARR survived before upsell; NRR includes expansion.

**Grain.** Account in the opening cohort (`opening_arr > 0`). New logos acquired during the period are excluded from both ratios.

**Exact rules.**  
`GRR = (Opening ARR - Contraction ARR - Churn ARR) / Opening ARR`  
`NRR = Ending ARR of the opening cohort / Opening ARR`

Expansion is excluded from GRR and included in NRR. An account that fully churns contributes zero ending ARR. New accounts contribute neither numerator nor denominator.

**Currency.** Opening and ending values use the same period-end FX rate, making retention operational rather than an FX report.

**Edge case.** Corporate parents can have multiple billed children. I calculate retention at billing account ID so one child's churn is not hidden by another child's expansion. The dashboard may roll those accounts to a CRM parent for context, but the signed metric remains at the contractual-account grain. I would confirm with Finance whether board reporting instead treats a corporate family as one economic customer.

## 4. Win Rate

**Plain-English definition.** Of New Business opportunities that reached a final decision during the period, the share that were won.

**Grain.** Opportunity.

**Exact rules.**  
`New Business Win Rate = Closed Won New Business count / (Closed Won + Closed Lost New Business count)`.

The period is based on a **resolved close date**. Normally that is CRM `close_date`. When `close_date < created_date`, I replace it with the first recorded transition into Closed Won/Lost if one exists; an unrepairable date is quarantined from period-based calculations. Internal/test and soft-deleted CRM accounts are excluded. Open deals are not in the denominator. Amount is irrelevant to this count-based metric, so a deal with an invalid monetary amount can still represent a funnel decision.

**Currency.** Not applicable because this is count-based. I deliberately did not use amount-weighted win rate as the default; that is a separate metric with a different business meaning.

**Edge case.** 37 opportunities have `close_date` before `created_date`; 300 opportunities have no stage-history rows. The repair uses history only when the primary close date is impossible, rather than redefining all close dates using stage timestamps (which often differ by several days from the CRM business date).

## 5. Open Pipeline and Pipeline Coverage

**Plain-English definition.** Open, commercially valid growth opportunities as of the reporting date. Coverage compares that pipeline with the bookings target for the same future period.

**Grain.** Opportunity, summed for reporting.

**Exact rules for Open Pipeline.** Include opportunities created by the as-of date that are not closed as of that date, on commercial accounts, with type **New Business or Expansion**. Renewal is excluded from growth pipeline because renewal economics are represented in retention metrics. Monetary pipeline includes only `amount > 0`; invalid values remain visible in data-quality reporting but do not reduce or inflate pipeline dollars.

**Currency.** Open opportunity amounts are converted using FX as of the reporting date, not their future forecast close date. Future FX is unknowable. This produces a consistent present-value view of the current pipeline.

**Pipeline Coverage.** `Open growth pipeline for target period / bookings target for target period`.

**Missing input.** The dataset contains no quota/bookings target, so I do **not** invent coverage. The dashboard shows the numerator and `N/A` for coverage. I would ask **VP Sales / FP&A** for the Q3 2026 bookings target, including whether it covers New Business only or New Business + Expansion and whether the target is reported at budget FX or spot FX.

**Edge case.** One currently open New Business opportunity has a negative amount. Treating it literally would make pipeline smaller by USD 43.5k. I quarantine the monetary value instead. As a sensitivity check, including Renewal opportunities would produce a materially larger pipeline; that is a definition change, not a reconciliation error.

## Headline numbers

| Figure | Window | Result |
|---|---|---:|
| Active ARR | as of 2026-06-30 | **$34,736,511** |
| Active customer accounts | as of 2026-06-30 | **296** |
| New Business won | 2026-04-01 → 2026-06-30 | **$2,708,919** |
| New Business win rate | 2025-07-01 → 2026-06-30 | **25.71% (126 / 490)** |
| Open growth pipeline | as of 2026-06-30 | **$16,978,396** |
| Pipeline coverage | Q3 2026 | **N/A — bookings target not supplied** |

For reconciliation sensitivity: open pipeline **including Renewal** and still excluding invalid non-positive amounts is **$28.47M**. I do not use that as the signed headline because renewals are intentionally outside the growth-pipeline definition above.

### Supporting retention figures used in the dashboard

At constant 2026-06-30 FX:

| Period | Net New ARR | GRR | NRR |
|---|---:|---:|---:|
| Q2 2026 (2026-03-31 → 2026-06-30) | $2.476M | 90.08% | 100.21% |
| TTM (2025-06-30 → 2026-06-30) | $12.853M | 81.12% | 112.12% |
