DROP TABLE IF EXISTS stg_product_usage_events;
CREATE TABLE stg_product_usage_events AS
WITH ranked AS (
    SELECT
        ingestion_row_id,
        TRIM(event_id) AS event_id,
        TRIM(account_id) AS account_id,
        LOWER(TRIM(user_email)) AS user_email,
        TRIM(event_name) AS event_name,
        event_ts,
        TRIM(session_id) AS session_id,
        ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY ingestion_row_id) AS rn
    FROM raw_product_usage_events
)
SELECT
    event_id, account_id, user_email, event_name, event_ts, session_id,
    CASE WHEN substr(event_ts, 1, 10) > '{{AS_OF_DATE}}' THEN 1 ELSE 0 END AS is_future_event
FROM ranked
WHERE rn = 1;

DROP TABLE IF EXISTS stg_cs_health_snapshots;
CREATE TABLE stg_cs_health_snapshots AS
WITH ranked AS (
    SELECT
        snapshot_id, account_id, snapshot_month, health_score, csm_user_id,
        renewal_risk, open_tickets, source_page, source_request,
        ROW_NUMBER() OVER (PARTITION BY snapshot_id ORDER BY ingestion_row_id) AS rn
    FROM raw_cs_health_snapshots
)
SELECT
    TRIM(snapshot_id) AS snapshot_id,
    TRIM(account_id) AS account_id,
    date(snapshot_month) AS snapshot_month,
    CAST(health_score AS REAL) AS health_score,
    TRIM(csm_user_id) AS csm_user_id,
    TRIM(renewal_risk) AS renewal_risk,
    CAST(open_tickets AS INTEGER) AS open_tickets,
    source_page,
    source_request
FROM ranked
WHERE rn = 1;
