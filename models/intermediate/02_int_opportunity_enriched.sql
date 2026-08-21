DROP TABLE IF EXISTS int_opportunity_enriched;
CREATE TABLE int_opportunity_enriched AS
WITH first_close_transition AS (
    SELECT opportunity_id, to_stage AS first_close_stage, date(changed_at) AS first_close_transition_date
    FROM (
        SELECT
            opportunity_id,
            to_stage,
            changed_at,
            ROW_NUMBER() OVER (PARTITION BY opportunity_id ORDER BY changed_at, history_id) AS rn
        FROM stg_opportunity_stage_history
        WHERE to_stage IN ('5-Closed Won', '6-Closed Lost')
    )
    WHERE rn = 1
),
last_stage_asof AS (
    SELECT opportunity_id, to_stage AS stage_asof, date(changed_at) AS stage_asof_changed_date
    FROM (
        SELECT
            opportunity_id,
            to_stage,
            changed_at,
            ROW_NUMBER() OVER (PARTITION BY opportunity_id ORDER BY changed_at DESC, history_id DESC) AS rn
        FROM stg_opportunity_stage_history
        WHERE date(changed_at) <= '{{AS_OF_DATE}}'
    )
    WHERE rn = 1
),
history_presence AS (
    SELECT opportunity_id, COUNT(*) AS history_rows
    FROM stg_opportunity_stage_history
    GROUP BY opportunity_id
),
fx_asof AS (
    SELECT currency, rate_to_usd
    FROM stg_fx_rates_daily
    WHERE rate_date = '{{AS_OF_DATE}}'
)
SELECT
    o.*,
    a.is_commercial_account,
    a.is_internal_test,
    a.is_deleted AS account_is_deleted,
    f.first_close_stage,
    f.first_close_transition_date,
    CASE
      WHEN o.close_date >= o.created_date THEN o.close_date
      WHEN f.first_close_transition_date IS NOT NULL THEN f.first_close_transition_date
      ELSE NULL
    END AS resolved_close_date,
    CASE
      WHEN f.first_close_transition_date IS NOT NULL THEN f.first_close_transition_date
      WHEN o.is_closed = 1 AND o.close_date >= o.created_date THEN o.close_date
      ELSE NULL
    END AS state_closed_date,
    CASE
      WHEN l.stage_asof IS NOT NULL THEN l.stage_asof
      -- If the opportunity has no history at all, current stage is the only state available.
      WHEN hp.history_rows IS NULL AND o.is_closed = 0 THEN o.stage_name
      -- If history exists only after the as-of watermark, do not leak that future state backwards.
      ELSE '1-Discovery'
    END AS stage_asof,
    l.stage_asof_changed_date,
    CASE WHEN o.is_monetary_valid = 1 THEN o.amount * fa.rate_to_usd END AS amount_usd_asof,
    CASE
      WHEN o.is_monetary_valid = 1
       AND (CASE WHEN o.close_date >= o.created_date THEN o.close_date WHEN f.first_close_transition_date IS NOT NULL THEN f.first_close_transition_date END) IS NOT NULL
      THEN o.amount * (
        SELECT x.rate_to_usd
        FROM stg_fx_rates_daily x
        WHERE x.currency = o.currency
          AND x.rate_date <= (CASE WHEN o.close_date >= o.created_date THEN o.close_date ELSE f.first_close_transition_date END)
        ORDER BY x.rate_date DESC
        LIMIT 1
      )
    END AS amount_usd_at_close
FROM stg_opportunities o
JOIN stg_accounts a ON a.account_id = o.account_id
LEFT JOIN first_close_transition f ON f.opportunity_id = o.opportunity_id
LEFT JOIN last_stage_asof l ON l.opportunity_id = o.opportunity_id
LEFT JOIN history_presence hp ON hp.opportunity_id = o.opportunity_id
LEFT JOIN fx_asof fa ON fa.currency = o.currency;
