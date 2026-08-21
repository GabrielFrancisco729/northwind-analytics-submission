DROP TABLE IF EXISTS mart_retention_metrics;
CREATE TABLE mart_retention_metrics AS
WITH periods(period_name, start_date, end_date) AS (
    VALUES
      ('Q2 2026', '2026-03-31', '2026-06-30'),
      ('TTM', '2025-06-30', '2026-06-30')
),
account_values AS (
    SELECT
        p.period_name,
        p.start_date,
        p.end_date,
        s.account_id,
        SUM(CASE WHEN s.term_start_date <= p.start_date AND p.start_date < s.effective_end_date
                 THEN s.arr * fx.rate_to_usd ELSE 0 END) AS start_arr_usd,
        SUM(CASE WHEN s.term_start_date <= p.end_date AND p.end_date < s.effective_end_date
                 THEN s.arr * fx.rate_to_usd ELSE 0 END) AS end_arr_usd
    FROM periods p
    JOIN int_subscription_terms s
      ON (s.term_start_date <= p.start_date AND p.start_date < s.effective_end_date)
      OR (s.term_start_date <= p.end_date AND p.end_date < s.effective_end_date)
    JOIN stg_fx_rates_daily fx
      ON fx.rate_date = p.end_date
     AND fx.currency = s.currency
    GROUP BY p.period_name, p.start_date, p.end_date, s.account_id
),
components AS (
    SELECT
        *,
        CASE WHEN start_arr_usd = 0 AND end_arr_usd > 0 THEN end_arr_usd ELSE 0 END AS new_arr,
        CASE WHEN start_arr_usd > 0 AND end_arr_usd > start_arr_usd THEN end_arr_usd - start_arr_usd ELSE 0 END AS expansion_arr,
        CASE WHEN start_arr_usd > 0 AND end_arr_usd > 0 AND end_arr_usd < start_arr_usd THEN start_arr_usd - end_arr_usd ELSE 0 END AS contraction_arr,
        CASE WHEN start_arr_usd > 0 AND end_arr_usd = 0 THEN start_arr_usd ELSE 0 END AS churn_arr
    FROM account_values
)
SELECT
    period_name,
    MIN(start_date) AS start_date,
    MIN(end_date) AS end_date,
    SUM(start_arr_usd) AS opening_arr_usd,
    SUM(end_arr_usd) AS ending_arr_usd,
    SUM(new_arr) AS new_arr_usd,
    SUM(expansion_arr) AS expansion_arr_usd,
    SUM(contraction_arr) AS contraction_arr_usd,
    SUM(churn_arr) AS churn_arr_usd,
    SUM(end_arr_usd) - SUM(start_arr_usd) AS net_new_arr_usd,
    (SUM(start_arr_usd) - SUM(contraction_arr) - SUM(churn_arr)) / NULLIF(SUM(start_arr_usd), 0) AS grr,
    SUM(CASE WHEN start_arr_usd > 0 THEN end_arr_usd ELSE 0 END) / NULLIF(SUM(start_arr_usd), 0) AS nrr,
    SUM(CASE WHEN start_arr_usd > 0 THEN 1 ELSE 0 END) AS opening_accounts,
    SUM(CASE WHEN end_arr_usd > 0 THEN 1 ELSE 0 END) AS ending_accounts
FROM components
GROUP BY period_name;
