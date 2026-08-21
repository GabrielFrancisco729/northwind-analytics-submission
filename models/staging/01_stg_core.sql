DROP TABLE IF EXISTS stg_accounts;
CREATE TABLE stg_accounts AS
SELECT
    TRIM(account_id) AS account_id,
    TRIM(account_name) AS account_name,
    LOWER(TRIM(domain)) AS domain,
    NULLIF(TRIM(region), '') AS region,
    NULLIF(TRIM(segment), '') AS segment,
    NULLIF(TRIM(industry), '') AS industry,
    TRIM(owner_user_id) AS owner_user_id,
    datetime(created_at) AS created_at,
    CAST(is_deleted AS INTEGER) AS is_deleted,
    NULLIF(TRIM(parent_account_id), '') AS parent_account_id,
    TRIM(billing_currency) AS billing_currency,
    CASE
      WHEN LOWER(TRIM(domain)) IN ('example.test', 'northwind-example.com')
        OR LOWER(account_name) LIKE '%test%'
        OR LOWER(account_name) LIKE '%demo%'
        OR LOWER(account_name) LIKE '%do not use%'
        OR LOWER(account_name) LIKE '%internal%'
      THEN 1 ELSE 0
    END AS is_internal_test,
    CASE
      WHEN CAST(is_deleted AS INTEGER) = 0
       AND NOT (
         LOWER(TRIM(domain)) IN ('example.test', 'northwind-example.com')
         OR LOWER(account_name) LIKE '%test%'
         OR LOWER(account_name) LIKE '%demo%'
         OR LOWER(account_name) LIKE '%do not use%'
         OR LOWER(account_name) LIKE '%internal%'
       )
      THEN 1 ELSE 0
    END AS is_commercial_account
FROM raw_crm_accounts;

DROP TABLE IF EXISTS stg_users;
CREATE TABLE stg_users AS
SELECT
    TRIM(user_id) AS user_id,
    TRIM(full_name) AS full_name,
    LOWER(TRIM(email)) AS email,
    TRIM(role) AS role,
    NULLIF(TRIM(manager_user_id), '') AS manager_user_id,
    NULLIF(TRIM(region), '') AS region,
    NULLIF(TRIM(team), '') AS team,
    date(hire_date) AS hire_date,
    CAST(is_active AS INTEGER) AS is_active
FROM raw_crm_users;

DROP TABLE IF EXISTS stg_opportunities;
CREATE TABLE stg_opportunities AS
SELECT
    TRIM(opportunity_id) AS opportunity_id,
    TRIM(account_id) AS account_id,
    TRIM(opportunity_name) AS opportunity_name,
    TRIM(owner_user_id) AS owner_user_id,
    TRIM(opportunity_type) AS opportunity_type,
    CAST(amount AS REAL) AS amount,
    TRIM(currency) AS currency,
    date(created_date) AS created_date,
    date(close_date) AS close_date,
    TRIM(stage_name) AS stage_name,
    CAST(is_closed AS INTEGER) AS is_closed,
    CAST(is_won AS INTEGER) AS is_won,
    TRIM(forecast_category) AS forecast_category,
    TRIM(lead_source) AS lead_source,
    CASE WHEN amount > 0 THEN 1 ELSE 0 END AS is_monetary_valid
FROM raw_crm_opportunities;

DROP TABLE IF EXISTS stg_opportunity_stage_history;
CREATE TABLE stg_opportunity_stage_history AS
SELECT
    TRIM(history_id) AS history_id,
    TRIM(opportunity_id) AS opportunity_id,
    NULLIF(TRIM(from_stage), '') AS from_stage,
    TRIM(to_stage) AS to_stage,
    datetime(changed_at) AS changed_at,
    TRIM(changed_by_user_id) AS changed_by_user_id
FROM raw_crm_opportunity_stage_history;

DROP TABLE IF EXISTS stg_billing_subscriptions;
CREATE TABLE stg_billing_subscriptions AS
SELECT
    TRIM(subscription_id) AS subscription_id,
    TRIM(account_id) AS account_id,
    NULLIF(TRIM(source_opportunity_id), '') AS source_opportunity_id,
    TRIM(product_name) AS product_name,
    CAST(arr AS REAL) AS arr,
    TRIM(currency) AS currency,
    date(term_start_date) AS term_start_date,
    date(term_end_date) AS term_end_date,
    TRIM(billing_frequency) AS billing_frequency,
    TRIM(status) AS status,
    NULLIF(TRIM(replaced_by_subscription_id), '') AS replaced_by_subscription_id
FROM raw_billing_subscriptions;

DROP TABLE IF EXISTS stg_fx_rates_daily;
CREATE TABLE stg_fx_rates_daily AS
SELECT date(rate_date) AS rate_date, TRIM(currency) AS currency, CAST(rate_to_usd AS REAL) AS rate_to_usd
FROM raw_fx_rates_daily;
