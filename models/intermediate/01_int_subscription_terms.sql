DROP TABLE IF EXISTS int_subscription_terms;
CREATE TABLE int_subscription_terms AS
SELECT
    s.subscription_id,
    s.account_id,
    s.source_opportunity_id,
    s.product_name,
    s.arr,
    s.currency,
    s.term_start_date,
    s.term_end_date,
    s.billing_frequency,
    s.status,
    s.replaced_by_subscription_id,
    r.term_start_date AS replacement_start_date,
    CASE
      WHEN r.term_start_date IS NOT NULL AND r.term_start_date < s.term_end_date THEN r.term_start_date
      ELSE s.term_end_date
    END AS effective_end_date
FROM stg_billing_subscriptions s
LEFT JOIN stg_billing_subscriptions r
  ON s.replaced_by_subscription_id = r.subscription_id;
