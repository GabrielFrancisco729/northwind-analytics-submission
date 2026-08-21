DROP TABLE IF EXISTS dim_account;
CREATE TABLE dim_account AS
SELECT
    a.*,
    h.root_account_id,
    h.hierarchy_depth,
    h.hierarchy_path,
    p.account_name AS parent_account_name,
    r.account_name AS root_account_name
FROM stg_accounts a
LEFT JOIN int_account_hierarchy h ON h.account_id = a.account_id
LEFT JOIN stg_accounts p ON p.account_id = a.parent_account_id
LEFT JOIN stg_accounts r ON r.account_id = h.root_account_id;

DROP TABLE IF EXISTS dim_user;
CREATE TABLE dim_user AS SELECT * FROM stg_users;

DROP TABLE IF EXISTS fct_subscription_terms;
CREATE TABLE fct_subscription_terms AS SELECT * FROM int_subscription_terms;

DROP TABLE IF EXISTS fct_opportunity;
CREATE TABLE fct_opportunity AS SELECT * FROM int_opportunity_enriched;

DROP TABLE IF EXISTS fct_usage_account_monthly;
CREATE TABLE fct_usage_account_monthly AS
SELECT
    account_id,
    substr(event_ts, 1, 7) || '-01' AS usage_month,
    COUNT(*) AS event_count,
    COUNT(DISTINCT user_email) AS active_users,
    COUNT(DISTINCT session_id) AS session_count
FROM stg_product_usage_events
WHERE is_future_event = 0
GROUP BY account_id, substr(event_ts, 1, 7) || '-01';

DROP TABLE IF EXISTS fct_cs_health_monthly;
CREATE TABLE fct_cs_health_monthly AS
SELECT snapshot_id, account_id, snapshot_month, health_score, csm_user_id, renewal_risk, open_tickets
FROM stg_cs_health_snapshots;

DROP TABLE IF EXISTS fct_arr_account_monthly;
CREATE TABLE fct_arr_account_monthly AS
WITH RECURSIVE dates(snapshot_date) AS (
    SELECT '2025-06-30'
    UNION ALL
    SELECT date(snapshot_date, 'start of month', '+2 months', '-1 day')
    FROM dates
    WHERE snapshot_date < '{{AS_OF_DATE}}'
)
SELECT
    d.snapshot_date,
    s.account_id,
    SUM(s.arr * fx.rate_to_usd) AS arr_usd,
    COUNT(*) AS active_subscription_lines
FROM dates d
JOIN int_subscription_terms s
  ON s.term_start_date <= d.snapshot_date
 AND d.snapshot_date < s.effective_end_date
JOIN stg_fx_rates_daily fx
  ON fx.rate_date = d.snapshot_date
 AND fx.currency = s.currency
GROUP BY d.snapshot_date, s.account_id;
