-- Sales Manager view: stage mix, targeted account action list, and CRM relationship hierarchy.
SELECT * FROM mart_pipeline_by_stage ORDER BY stage_order;
SELECT * FROM mart_account_360 WHERE targeted_reengagement_candidate=1 ORDER BY arr_usd DESC;
SELECT p.account_id AS parent_id, p.account_name AS parent_name,
       c.account_id AS child_id, c.account_name AS child_name,
       COALESCE(pa.arr_usd,0) AS parent_arr_usd, COALESCE(ca.arr_usd,0) AS child_arr_usd,
       c.is_deleted AS child_is_deleted
FROM dim_account c
JOIN dim_account p ON c.parent_account_id=p.account_id
LEFT JOIN mart_account_360 pa ON pa.account_id=p.account_id
LEFT JOIN mart_account_360 ca ON ca.account_id=c.account_id
ORDER BY parent_arr_usd + child_arr_usd DESC;
