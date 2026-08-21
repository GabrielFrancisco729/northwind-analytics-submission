# Curated data model

The structure intentionally mirrors a dbt-style project while using plain SQL + a small SQLite runner. Raw ingestion preserves source behavior; staging makes source-specific cleanup explicit; intermediate models contain reusable business logic; marts expose stable business grains.

## Layers and model purpose

| Layer / model | Grain | What it is for |
|---|---|---|
| `raw_*` | exact source row / API response row | Reproducible landing zone. Preserves duplicates, future-dated records, invalid amounts, and API page provenance for auditability. |
| `stg_accounts` | one CRM account record | Normalizes text and creates explicit commercial/test/deleted flags without attempting MDM merges. |
| `stg_users` | one CRM user | Stable employee identity and reporting attributes. |
| `stg_opportunities` | one opportunity | Normalizes dates/flags and marks whether monetary amount is valid; does not hide invalid source rows. |
| `stg_opportunity_stage_history` | one recorded stage transition | Clean event history used for point-in-time state reconstruction and close-date repair. |
| `stg_billing_subscriptions` | one source subscription term | Clean billing source-of-record before amendment logic. |
| `stg_fx_rates_daily` | one date × currency | Conversion lookup for point-in-time and constant-currency metrics. |
| `stg_product_usage_events` | one unique `event_id` | Deduplicated at-least-once event stream with an explicit future-event watermark flag. |
| `stg_cs_health_snapshots` | one unique `snapshot_id` | Deduplicated API result with page provenance. |
| `int_subscription_terms` | one subscription term | Resolves replacements into non-overlapping effective intervals; this is the reusable ARR contract logic. |
| `int_opportunity_enriched` | one opportunity | Adds commercial-account eligibility, resolved close date, as-of stage, and safe USD values. |
| `int_account_hierarchy` | one account record | Resolves CRM parent → root relationships with a recursive CTE while preserving account grain. |
| `dim_account` | one CRM account record | Reporting dimension with hierarchy context and commercial/test flags. |
| `dim_user` | one employee | Reporting dimension for AE/manager/CSM ownership. |
| `fct_subscription_terms` | one effective subscription term | Finance fact for any ARR snapshot or movement calculation. |
| `fct_opportunity` | one opportunity | Sales funnel fact with safe monetary fields and temporal-state fields. |
| `fct_arr_account_monthly` | one account × month-end | ARR/account trend used by the executive dashboard. |
| `fct_usage_account_monthly` | one account × month | Engagement trend after event deduplication and as-of watermarking. |
| `fct_cs_health_monthly` | one account × available health month | CS risk/health history; gaps are intentionally preserved. |
| `mart_retention_metrics` | one requested period | Signed Net New ARR / GRR / NRR reconciliation at constant period-end FX. |
| `mart_headline_metrics` | one as-of row | Comparison table requested in the case brief. |
| `mart_pipeline_by_stage` | one current stage | Dashboard-ready growth pipeline breakdown. |
| `mart_account_360` | one active billing account | Joins ARR, current contract timing, engagement, health, and hierarchy for action-oriented account review. |
| `audit_data_quality` | one identified source issue | Makes known data problems, handling decisions, and owners/escalations queryable. |

## Why not auto-deduplicate CRM accounts by domain?

218 account rows share a domain with another record. Some are obviously stale/test duplicates, but many look like plausible legal entities with distinct account IDs and, in some cases, parent relationships. Billing joins on account ID and is the ARR source of record. Auto-merging by domain could therefore combine legal customers and change both customer counts and retention. The mart preserves account IDs and exposes hierarchy/domain issues for RevOps/Finance MDM review.
