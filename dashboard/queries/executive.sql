-- Executive / CRO view: signed KPIs plus trend and retention.
SELECT * FROM mart_headline_metrics;
SELECT * FROM mart_retention_metrics;
SELECT snapshot_date, SUM(arr_usd) AS arr_usd, COUNT(*) AS active_accounts
FROM fct_arr_account_monthly GROUP BY snapshot_date ORDER BY snapshot_date;
SELECT * FROM mart_pipeline_by_stage ORDER BY stage_order;
