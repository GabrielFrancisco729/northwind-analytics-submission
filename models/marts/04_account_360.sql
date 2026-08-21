DROP TABLE IF EXISTS mart_account_360;
CREATE TABLE mart_account_360 AS
WITH arr_current AS (
    SELECT
      s.account_id,
      SUM(s.arr * fx.rate_to_usd) AS arr_usd,
      MIN(s.effective_end_date) AS next_contract_event_date
    FROM int_subscription_terms s
    JOIN stg_fx_rates_daily fx
      ON fx.rate_date = '{{AS_OF_DATE}}' AND fx.currency = s.currency
    WHERE s.term_start_date <= '{{AS_OF_DATE}}'
      AND '{{AS_OF_DATE}}' < s.effective_end_date
    GROUP BY s.account_id
),
usage AS (
    SELECT
      account_id,
      SUM(CASE WHEN usage_month IN ('2026-01-01','2026-02-01') THEN event_count ELSE 0 END) / 2.0 AS jan_feb_monthly_events,
      SUM(CASE WHEN usage_month IN ('2026-04-01','2026-05-01','2026-06-01') THEN event_count ELSE 0 END) / 3.0 AS apr_jun_monthly_events,
      SUM(CASE WHEN usage_month IN ('2026-04-01','2026-05-01','2026-06-01') THEN active_users ELSE 0 END) / 3.0 AS apr_jun_monthly_users
    FROM fct_usage_account_monthly
    GROUP BY account_id
),
latest_health AS (
    SELECT account_id, snapshot_month, health_score, renewal_risk, open_tickets, csm_user_id
    FROM (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY snapshot_month DESC, snapshot_id DESC) AS rn
      FROM fct_cs_health_monthly
      WHERE snapshot_month <= '2026-06-01'
    )
    WHERE rn = 1
)
SELECT
    a.account_id,
    a.account_name,
    a.domain,
    a.region,
    a.segment,
    a.industry,
    a.parent_account_id,
    a.parent_account_name,
    a.root_account_id,
    a.root_account_name,
    a.hierarchy_depth,
    ac.arr_usd,
    ac.next_contract_event_date,
    CAST(julianday(ac.next_contract_event_date) - julianday('{{AS_OF_DATE}}') AS INTEGER) AS days_to_contract_event,
    u.jan_feb_monthly_events,
    u.apr_jun_monthly_events,
    CASE WHEN u.jan_feb_monthly_events > 0 THEN u.apr_jun_monthly_events / u.jan_feb_monthly_events END AS usage_ratio_post_vs_pre,
    u.apr_jun_monthly_users,
    h.snapshot_month AS latest_health_month,
    h.health_score,
    h.renewal_risk,
    h.open_tickets,
    h.csm_user_id,
    CASE
      WHEN u.jan_feb_monthly_events > 0
       AND u.apr_jun_monthly_events / u.jan_feb_monthly_events < 0.80
       AND h.renewal_risk IN ('High','Medium')
       AND CAST(julianday(ac.next_contract_event_date) - julianday('{{AS_OF_DATE}}') AS INTEGER) <= 180
      THEN 1 ELSE 0
    END AS targeted_reengagement_candidate
FROM dim_account a
JOIN arr_current ac ON ac.account_id = a.account_id
LEFT JOIN usage u ON u.account_id = a.account_id
LEFT JOIN latest_health h ON h.account_id = a.account_id;
