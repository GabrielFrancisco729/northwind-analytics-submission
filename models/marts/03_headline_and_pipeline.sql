DROP TABLE IF EXISTS mart_headline_metrics;
CREATE TABLE mart_headline_metrics AS
WITH active_arr AS (
    SELECT
      SUM(s.arr * fx.rate_to_usd) AS active_arr_usd,
      COUNT(DISTINCT s.account_id) AS active_customer_accounts
    FROM int_subscription_terms s
    JOIN stg_fx_rates_daily fx
      ON fx.rate_date = '{{AS_OF_DATE}}' AND fx.currency = s.currency
    WHERE s.term_start_date <= '{{AS_OF_DATE}}'
      AND '{{AS_OF_DATE}}' < s.effective_end_date
),
q2_won AS (
    SELECT SUM(amount_usd_at_close) AS new_business_won_usd
    FROM int_opportunity_enriched
    WHERE is_commercial_account = 1
      AND opportunity_type = 'New Business'
      AND is_won = 1
      AND resolved_close_date BETWEEN '2026-04-01' AND '2026-06-30'
      AND is_monetary_valid = 1
),
win_rate AS (
    SELECT
      SUM(CASE WHEN is_won = 1 THEN 1 ELSE 0 END) AS wins,
      COUNT(*) AS decisions
    FROM int_opportunity_enriched
    WHERE is_commercial_account = 1
      AND opportunity_type = 'New Business'
      AND is_closed = 1
      AND resolved_close_date BETWEEN '2025-07-01' AND '2026-06-30'
),
open_pipeline AS (
    SELECT
      SUM(amount_usd_asof) AS open_pipeline_usd,
      COUNT(CASE WHEN is_monetary_valid = 1 THEN 1 END) AS valued_open_opportunities,
      COUNT(*) AS open_opportunities
    FROM int_opportunity_enriched
    WHERE is_commercial_account = 1
      AND opportunity_type IN ('New Business','Expansion')
      AND created_date <= '{{AS_OF_DATE}}'
      AND (state_closed_date IS NULL OR state_closed_date > '{{AS_OF_DATE}}')
)
SELECT
    '{{AS_OF_DATE}}' AS as_of_date,
    ROUND(active_arr.active_arr_usd, 2) AS active_arr_usd,
    active_arr.active_customer_accounts,
    ROUND(q2_won.new_business_won_usd, 2) AS q2_new_business_won_usd,
    win_rate.wins AS ttm_new_business_wins,
    win_rate.decisions AS ttm_new_business_decisions,
    CAST(win_rate.wins AS REAL) / NULLIF(win_rate.decisions, 0) AS ttm_new_business_win_rate,
    ROUND(open_pipeline.open_pipeline_usd, 2) AS open_growth_pipeline_usd,
    open_pipeline.valued_open_opportunities,
    open_pipeline.open_opportunities,
    NULL AS pipeline_coverage,
    'Q3 bookings target not supplied' AS pipeline_coverage_note
FROM active_arr, q2_won, win_rate, open_pipeline;

DROP TABLE IF EXISTS mart_pipeline_by_stage;
CREATE TABLE mart_pipeline_by_stage AS
SELECT
    stage_asof,
    CASE stage_asof
      WHEN '1-Discovery' THEN 1
      WHEN '2-Qualified' THEN 2
      WHEN '3-Proposal' THEN 3
      WHEN '4-Negotiation' THEN 4
      ELSE 99 END AS stage_order,
    COUNT(*) AS opportunity_count,
    SUM(CASE WHEN is_monetary_valid = 1 THEN amount_usd_asof ELSE 0 END) AS pipeline_usd,
    SUM(CASE WHEN opportunity_type = 'New Business' AND is_monetary_valid = 1 THEN amount_usd_asof ELSE 0 END) AS new_business_pipeline_usd,
    SUM(CASE WHEN opportunity_type = 'Expansion' AND is_monetary_valid = 1 THEN amount_usd_asof ELSE 0 END) AS expansion_pipeline_usd
FROM int_opportunity_enriched
WHERE is_commercial_account = 1
  AND opportunity_type IN ('New Business','Expansion')
  AND created_date <= '{{AS_OF_DATE}}'
  AND (state_closed_date IS NULL OR state_closed_date > '{{AS_OF_DATE}}')
GROUP BY stage_asof;
