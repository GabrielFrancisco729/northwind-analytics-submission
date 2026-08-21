# Data quality findings

The executable version of this list is `audit_data_quality` in `warehouse/northwind.db` and `outputs/data_quality_audit.csv`. Curated-layer tests fail on violations introduced by transformation; known source issues are retained as audits so a successful build never implies the source is clean.

| Finding | Size observed | Handling in v1 | Human escalation |
|---|---:|---|---|
| Opportunity `amount <= 0` | 19 opportunities | Keep rows for count-based funnel metrics; monetary fields become NULL/excluded. | Sales Ops: determine whether these are data-entry errors or intended credits/contractions and model them explicitly if the latter. |
| `close_date < created_date` | 37 opportunities | When possible, repair period date from first Closed Won/Lost transition; otherwise quarantine resolved date. | Sales Ops: validation rule + source repair. |
| Billing amendment overlap | 52 predecessor/successor chains | Clip predecessor at successor start. | Finance/Billing Ops: confirm replacement semantics. |
| Future successors already marked `Active` | 16 future-starting successor rows as of 6/30 | Do not use status as historical ARR eligibility. | Billing Ops: clarify status lifecycle. |
| Product event duplicate delivery | 3,200 extra rows | Deduplicate by `event_id` (first copy retained). | Platform: monitor duplicate rate; at-least-once delivery itself is expected. |
| Product events after case “today” | 240 unique events | Retain raw, exclude from all as-of analysis. | Platform: enforce source watermark. |
| Sharp telemetry under-capture | Mar 10–31 captures ~15% of expected event volume | Do not interpret March raw event volume as customer disengagement. | Product/Data Platform: investigate instrumentation/ingestion incident before using usage in CS scoring. |
| CS API HTTP 429 | 1 request (`cursor_05`) | Honor `retry_after_seconds=2` and retry URL; both calls logged. | Operational; alert only if retries exhaust. |
| CS duplicate snapshot IDs across page boundary | 40 IDs | Deduplicate by `snapshot_id`; duplicates are exact. | CS/API owner: stable pagination boundary. |
| Incomplete CS monthly history | 207 accounts have <12 monthly snapshots | Use latest available snapshot, never fabricate missing months. | CS Ops: expected scoring cadence / backfill policy. |
| Missing account region | 33 | Preserve `Unknown`; never substitute owner region. | RevOps backfill. |
| Missing account segment | 25 | Preserve `Unknown`. | RevOps backfill. |
| Shared CRM domains | 218 rows are in duplicate-domain groups | No automatic merge; billing account ID remains customer grain. | RevOps + Finance MDM/canonical-account decision. |
| Opportunities with no stage history | 300 | Current-state funnel can use CRM fields; historical stage-conversion/forecasting uses conservative fallback and documents the limitation. | RevOps/Data Platform: stage-history retention. |
| Stage-history rows after 2026-06-30 | 180 | Exclude when reconstructing “as of today”. | Platform: point-in-time extraction watermark. |
| Opportunity currency differs from account billing currency | 23 | Trust the opportunity's own currency for deal conversion. | Sales Ops/Finance: confirm cross-currency deals are allowed. |

## Problems deliberately *not* fixed in code

I do not canonicalize account names/domains, infer missing geography, overwrite negative opportunity amounts with zero, or invent missing CS months. Those actions require a business owner because they change customer identity, sales economics, or historical facts. The curated layer isolates their effect; the audit tells the owner exactly what needs resolution.
