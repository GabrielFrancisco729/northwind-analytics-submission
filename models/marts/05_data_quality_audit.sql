DROP TABLE IF EXISTS audit_data_quality;
CREATE TABLE audit_data_quality AS
SELECT 4 AS severity_rank, 'HIGH' AS severity,
       'Opportunity amount is zero or negative' AS issue,
       (SELECT COUNT(*) FROM raw_crm_opportunities WHERE amount <= 0) AS affected_rows,
       'Keep for count-based funnel metrics; set monetary value to NULL / exclude from dollar metrics.' AS handling,
       'Sales Ops: confirm whether any negatives are intended contractions/credits; otherwise correct CRM.' AS escalate
UNION ALL
SELECT 4, 'HIGH', 'Opportunity close_date precedes created_date',
       (SELECT COUNT(*) FROM stg_opportunities WHERE close_date < created_date),
       'Use first recorded Closed Won/Lost transition only when available; otherwise quarantine resolved close date.',
       'Sales Ops: repair source close dates and validation rule.'
UNION ALL
SELECT 4, 'HIGH', 'Billing amendment overlap if replacement chain is ignored',
       (SELECT COUNT(*) FROM stg_billing_subscriptions WHERE replaced_by_subscription_id IS NOT NULL),
       'Clip predecessor effective_end_date to successor term_start_date.',
       'Finance/Billing Ops: confirm amendment semantics; do not use status alone for historical ARR.'
UNION ALL
SELECT 3, 'MEDIUM', 'Future-starting replacement subscriptions already marked Active',
       (SELECT COUNT(*) FROM stg_billing_subscriptions s
        WHERE s.status='Active' AND s.term_start_date > '{{AS_OF_DATE}}'
          AND EXISTS (SELECT 1 FROM stg_billing_subscriptions p WHERE p.replaced_by_subscription_id=s.subscription_id)),
       'Do not use status as the historical activity predicate; use effective term dates.',
       'Billing Ops: confirm whether Active means configured/current-record rather than economically effective.'
UNION ALL
SELECT 3, 'MEDIUM', 'Product event duplicate deliveries',
       (SELECT COUNT(*) - COUNT(DISTINCT event_id) FROM raw_product_usage_events),
       'Deduplicate on event_id, preserving first received copy.',
       'Data Platform: expected for at-least-once bus, but monitor duplicate rate.'
UNION ALL
SELECT 4, 'HIGH', 'Product events occur after the stated as-of date',
       (SELECT COUNT(DISTINCT event_id) FROM raw_product_usage_events WHERE substr(event_ts,1,10) > '{{AS_OF_DATE}}'),
       'Retain in raw; exclude from all as-of reporting and analysis.',
       'Data Platform: determine whether synthetic extract leakage mirrors a real watermark problem.'
UNION ALL
SELECT 3, 'MEDIUM', 'CS API duplicate snapshot IDs across pages',
       (SELECT COUNT(*) FROM (SELECT snapshot_id FROM raw_cs_health_snapshots GROUP BY snapshot_id HAVING COUNT(*) > 1)),
       'Deduplicate on snapshot_id after pagination.',
       'CS/Data Platform: API pagination should guarantee stable page boundaries.'
UNION ALL
SELECT 3, 'MEDIUM', 'CS API rate limit response encountered',
       (SELECT COUNT(*) FROM raw_ingestion_log WHERE source='cs_health_api' AND status='429'),
       'Honor retry_after_seconds and retry_url; log both failed and successful calls.',
       'Operational only unless retries exhaust.'
UNION ALL
SELECT 2, 'LOW', 'CRM account missing region',
       (SELECT COUNT(*) FROM stg_accounts WHERE region IS NULL),
       'Preserve as Unknown; never infer from rep region.',
       'RevOps: backfill account region.'
UNION ALL
SELECT 2, 'LOW', 'CRM account missing segment',
       (SELECT COUNT(*) FROM stg_accounts WHERE segment IS NULL),
       'Preserve as Unknown; do not infer.',
       'RevOps: backfill segmentation.'
UNION ALL
SELECT 3, 'MEDIUM', 'CRM account domains are shared by multiple account records',
       (SELECT COALESCE(SUM(n),0) FROM (SELECT domain, COUNT(*) n FROM stg_accounts GROUP BY domain HAVING COUNT(*) > 1)),
       'Do not auto-merge: billing/account_id remains grain; surface duplicates for MDM review.',
       'RevOps/Finance: decide legal-customer vs corporate-family identity and canonical account mapping.'
UNION ALL
SELECT 2, 'LOW', 'Opportunities have no stage-history rows',
       (SELECT COUNT(*) FROM stg_opportunities o WHERE NOT EXISTS (SELECT 1 FROM stg_opportunity_stage_history h WHERE h.opportunity_id=o.opportunity_id)),
       'Use current CRM fields for current-state metrics; exclude from historical stage-conversion analysis where state cannot be reconstructed.',
       'RevOps/Data Platform: determine stage-history retention gap.'
UNION ALL
SELECT 3, 'MEDIUM', 'Opportunity stage transitions occur after the stated as-of date',
       (SELECT COUNT(*) FROM stg_opportunity_stage_history WHERE date(changed_at) > '{{AS_OF_DATE}}'),
       'Exclude future transitions when reconstructing stage as of today.',
       'Data Platform: enforce extraction watermark for point-in-time datasets.'
UNION ALL
SELECT 3, 'MEDIUM', 'Opportunity currency differs from account billing currency',
       (SELECT COUNT(*) FROM stg_opportunities o JOIN stg_accounts a USING(account_id) WHERE o.currency <> a.billing_currency),
       'Trust opportunity.currency for deal conversion; flag mismatch rather than overwrite.',
       'Sales Ops/Finance: confirm allowed cross-currency deals.'
UNION ALL
SELECT 2, 'LOW', 'CS monthly coverage is incomplete',
       (SELECT COUNT(*) FROM (SELECT account_id FROM stg_cs_health_snapshots GROUP BY account_id HAVING COUNT(DISTINCT snapshot_month) < 12)),
       'Use latest available snapshot as of a date; never impute missing months into trends without labeling.',
       'CS Ops: confirm expected scoring cadence.';
