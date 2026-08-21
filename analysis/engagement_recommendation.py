from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "warehouse" / "northwind.db"
OUT = ROOT / "outputs"


def main():
    OUT.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    daily = pd.read_sql_query(
        """
        SELECT substr(event_ts,1,10) AS event_date,
               COUNT(*) AS events,
               COUNT(DISTINCT account_id) AS active_accounts,
               COUNT(DISTINCT user_email) AS active_users,
               COUNT(DISTINCT session_id) AS sessions
        FROM stg_product_usage_events
        WHERE is_future_event=0
        GROUP BY substr(event_ts,1,10)
        ORDER BY event_date
        """,
        con,
        parse_dates=["event_date"],
    )
    daily.to_csv(OUT / "engagement_daily.csv", index=False)

    def avg(start, end):
        x = daily[(daily.event_date >= pd.Timestamp(start)) & (daily.event_date <= pd.Timestamp(end))]
        return float(x.events.mean()), int(x.events.sum()), len(x)

    pre_avg, _, _ = avg("2026-03-01", "2026-03-09")
    incident_avg, incident_total, incident_days = avg("2026-03-10", "2026-03-31")
    post_avg, _, _ = avg("2026-04-01", "2026-04-09")
    baseline = (pre_avg + post_avg) / 2
    expected_incident = baseline * incident_days
    capture_ratio = incident_total / expected_incident

    jan_feb = daily[(daily.event_date >= "2026-01-01") & (daily.event_date <= "2026-02-28")]
    apr_jun = daily[(daily.event_date >= "2026-04-01") & (daily.event_date <= "2026-06-30")]

    candidates = pd.read_sql_query(
        """
        SELECT account_id, account_name, region, segment, arr_usd,
               jan_feb_monthly_events, apr_jun_monthly_events,
               usage_ratio_post_vs_pre, health_score, renewal_risk,
               days_to_contract_event, next_contract_event_date
        FROM mart_account_360
        WHERE targeted_reengagement_candidate=1
        ORDER BY arr_usd DESC
        """,
        con,
    )
    candidates.to_csv(OUT / "targeted_reengagement_accounts.csv", index=False)

    health = pd.read_sql_query(
        """
        SELECT snapshot_month, AVG(health_score) AS avg_health_score,
               SUM(CASE WHEN renewal_risk='High' THEN 1 ELSE 0 END) AS high_risk_accounts,
               COUNT(*) AS scored_accounts
        FROM fct_cs_health_monthly
        GROUP BY snapshot_month
        ORDER BY snapshot_month
        """,
        con,
    )
    health.to_csv(OUT / "cs_health_monthly.csv", index=False)
    con.close()

    summary = {
        "pre_incident_daily_events": round(pre_avg, 1),
        "incident_daily_events": round(incident_avg, 1),
        "post_incident_daily_events": round(post_avg, 1),
        "estimated_capture_loss_pct": round((1 - capture_ratio) * 100, 1),
        "estimated_missing_events_mar10_mar31": round(expected_incident - incident_total),
        "jan_feb_daily_events": round(float(jan_feb.events.mean()), 1),
        "apr_jun_daily_events": round(float(apr_jun.events.mean()), 1),
        "apr_jun_vs_jan_feb_pct": round((apr_jun.events.mean() / jan_feb.events.mean() - 1) * 100, 1),
        "targeted_accounts": int(len(candidates)),
        "targeted_arr_usd": round(float(candidates.arr_usd.sum()), 2),
    }
    (OUT / "engagement_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.plot(daily.event_date, daily.events, linewidth=1.2)
    ax.axvspan(pd.Timestamp("2026-03-10"), pd.Timestamp("2026-03-31"), alpha=0.18)
    ax.axhline(baseline, linestyle="--", linewidth=1)
    ax.set_title("Product events: March drop is a bounded telemetry incident")
    ax.set_ylabel("Deduplicated events / day")
    ax.set_xlabel("")
    ax.text(pd.Timestamp("2026-03-20"), incident_avg + 120, "Mar 10–31\n~15% capture", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "engagement_telemetry.png", dpi=160)
    plt.close(fig)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
