from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "warehouse" / "northwind.db"
AS_OF = "2026-06-30"

TESTS = [
    ("accounts_key_not_null", "SELECT COUNT(*) FROM stg_accounts WHERE account_id IS NULL OR TRIM(account_id)=''", 0),
    ("users_key_not_null", "SELECT COUNT(*) FROM stg_users WHERE user_id IS NULL OR TRIM(user_id)=''", 0),
    ("opportunities_key_not_null", "SELECT COUNT(*) FROM stg_opportunities WHERE opportunity_id IS NULL OR TRIM(opportunity_id)=''", 0),
    ("subscriptions_key_not_null", "SELECT COUNT(*) FROM stg_billing_subscriptions WHERE subscription_id IS NULL OR TRIM(subscription_id)=''", 0),
    ("history_key_not_null", "SELECT COUNT(*) FROM stg_opportunity_stage_history WHERE history_id IS NULL OR TRIM(history_id)=''", 0),
    ("usage_event_key_not_null", "SELECT COUNT(*) FROM stg_product_usage_events WHERE event_id IS NULL OR TRIM(event_id)=''", 0),
    ("cs_snapshot_key_not_null", "SELECT COUNT(*) FROM stg_cs_health_snapshots WHERE snapshot_id IS NULL OR TRIM(snapshot_id)=''", 0),
    ("accounts_unique_key", "SELECT COUNT(*) - COUNT(DISTINCT account_id) FROM stg_accounts", 0),
    ("users_unique_key", "SELECT COUNT(*) - COUNT(DISTINCT user_id) FROM stg_users", 0),
    ("opportunities_unique_key", "SELECT COUNT(*) - COUNT(DISTINCT opportunity_id) FROM stg_opportunities", 0),
    ("subscriptions_unique_key", "SELECT COUNT(*) - COUNT(DISTINCT subscription_id) FROM stg_billing_subscriptions", 0),
    ("stage_history_unique_key", "SELECT COUNT(*) - COUNT(DISTINCT history_id) FROM stg_opportunity_stage_history", 0),
    ("fx_unique_key", "SELECT COUNT(*) - COUNT(DISTINCT rate_date || '|' || currency) FROM stg_fx_rates_daily", 0),
    ("usage_deduped_event_key", "SELECT COUNT(*) - COUNT(DISTINCT event_id) FROM stg_product_usage_events", 0),
    ("cs_deduped_snapshot_key", "SELECT COUNT(*) - COUNT(DISTINCT snapshot_id) FROM stg_cs_health_snapshots", 0),
    ("opportunity_account_fk", "SELECT COUNT(*) FROM stg_opportunities o LEFT JOIN stg_accounts a USING(account_id) WHERE a.account_id IS NULL", 0),
    ("subscription_account_fk", "SELECT COUNT(*) FROM stg_billing_subscriptions s LEFT JOIN stg_accounts a USING(account_id) WHERE a.account_id IS NULL", 0),
    ("history_opportunity_fk", "SELECT COUNT(*) FROM stg_opportunity_stage_history h LEFT JOIN stg_opportunities o USING(opportunity_id) WHERE o.opportunity_id IS NULL", 0),
    ("usage_account_fk", "SELECT COUNT(*) FROM stg_product_usage_events u LEFT JOIN stg_accounts a USING(account_id) WHERE a.account_id IS NULL", 0),
    ("cs_account_fk", "SELECT COUNT(*) FROM stg_cs_health_snapshots c LEFT JOIN stg_accounts a USING(account_id) WHERE a.account_id IS NULL", 0),
    ("cs_csm_fk", "SELECT COUNT(*) FROM stg_cs_health_snapshots c LEFT JOIN stg_users u ON c.csm_user_id=u.user_id WHERE u.user_id IS NULL", 0),
    ("replacement_fk", "SELECT COUNT(*) FROM stg_billing_subscriptions s LEFT JOIN stg_billing_subscriptions r ON s.replaced_by_subscription_id=r.subscription_id WHERE s.replaced_by_subscription_id IS NOT NULL AND r.subscription_id IS NULL", 0),
    ("subscription_positive_arr", "SELECT COUNT(*) FROM stg_billing_subscriptions WHERE arr <= 0", 0),
    ("subscription_valid_effective_interval", "SELECT COUNT(*) FROM int_subscription_terms WHERE effective_end_date <= term_start_date", 0),
    ("no_effective_subscription_overlap", """
        SELECT COUNT(*) FROM int_subscription_terms a
        JOIN int_subscription_terms b
          ON a.account_id=b.account_id AND a.product_name=b.product_name AND a.subscription_id<b.subscription_id
         AND a.term_start_date < b.effective_end_date AND b.term_start_date < a.effective_end_date
    """, 0),
    ("curated_usage_respects_asof", f"SELECT COUNT(*) FROM stg_product_usage_events WHERE is_future_event=0 AND substr(event_ts,1,10) > '{AS_OF}'", 0),
    ("arr_snapshot_nonnegative", "SELECT COUNT(*) FROM fct_arr_account_monthly WHERE arr_usd < 0", 0),
    ("hierarchy_resolves_every_account", "SELECT (SELECT COUNT(*) FROM stg_accounts) - (SELECT COUNT(*) FROM int_account_hierarchy)", 0),
    ("closed_won_flag_stage_consistency", "SELECT COUNT(*) FROM stg_opportunities WHERE is_won=1 AND (is_closed<>1 OR stage_name<>'5-Closed Won')", 0),
    ("closed_lost_flag_stage_consistency", "SELECT COUNT(*) FROM stg_opportunities WHERE is_closed=1 AND is_won=0 AND stage_name<>'6-Closed Lost'", 0),
    ("headline_active_arr_positive", "SELECT CASE WHEN active_arr_usd > 0 THEN 0 ELSE 1 END FROM mart_headline_metrics", 0),
    ("headline_customer_count_matches_arr_accounts", f"""
        SELECT ABS(
          (SELECT active_customer_accounts FROM mart_headline_metrics) -
          (SELECT COUNT(DISTINCT account_id) FROM int_subscription_terms WHERE term_start_date<='{AS_OF}' AND '{AS_OF}'<effective_end_date)
        )
    """, 0),
]


def run_tests():
    if not DB.exists():
        raise FileNotFoundError(f"Warehouse not found: {DB}. Run python run_pipeline.py first.")
    conn = sqlite3.connect(DB)
    failures = []
    for name, sql, expected in TESTS:
        actual = conn.execute(sql).fetchone()[0]
        if actual == expected:
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name}: expected {expected}, got {actual}")
            failures.append((name, expected, actual))
    conn.close()
    if failures:
        raise AssertionError(f"{len(failures)} curated-layer test(s) failed: {failures}")
    print(f"{len(TESTS)} curated-layer tests passed.")
    return True


if __name__ == "__main__":
    run_tests()
