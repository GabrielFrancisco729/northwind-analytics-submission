from __future__ import annotations

import csv
import gzip
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB = ROOT / "warehouse" / "northwind.db"
AS_OF_DATE = "2026-06-30"

CSV_SCHEMAS = {
    "crm_accounts.csv": (
        "raw_crm_accounts",
        """
        account_id TEXT, account_name TEXT, domain TEXT, region TEXT, segment TEXT,
        industry TEXT, owner_user_id TEXT, created_at TEXT, is_deleted INTEGER,
        parent_account_id TEXT, billing_currency TEXT
        """,
    ),
    "crm_users.csv": (
        "raw_crm_users",
        """
        user_id TEXT, full_name TEXT, email TEXT, role TEXT, manager_user_id TEXT,
        region TEXT, team TEXT, hire_date TEXT, is_active INTEGER
        """,
    ),
    "crm_opportunities.csv": (
        "raw_crm_opportunities",
        """
        opportunity_id TEXT, account_id TEXT, opportunity_name TEXT, owner_user_id TEXT,
        opportunity_type TEXT, amount REAL, currency TEXT, created_date TEXT, close_date TEXT,
        stage_name TEXT, is_closed INTEGER, is_won INTEGER, forecast_category TEXT, lead_source TEXT
        """,
    ),
    "crm_opportunity_stage_history.csv": (
        "raw_crm_opportunity_stage_history",
        """
        history_id TEXT, opportunity_id TEXT, from_stage TEXT, to_stage TEXT,
        changed_at TEXT, changed_by_user_id TEXT
        """,
    ),
    "billing_subscriptions.csv": (
        "raw_billing_subscriptions",
        """
        subscription_id TEXT, account_id TEXT, source_opportunity_id TEXT, product_name TEXT,
        arr REAL, currency TEXT, term_start_date TEXT, term_end_date TEXT,
        billing_frequency TEXT, status TEXT, replaced_by_subscription_id TEXT
        """,
    ),
    "fx_rates_daily.csv": (
        "raw_fx_rates_daily",
        "rate_date TEXT, currency TEXT, rate_to_usd REAL",
    ),
}

BOOL_COLUMNS = {"is_deleted", "is_active", "is_closed", "is_won"}
REAL_COLUMNS = {"amount", "arr", "rate_to_usd"}


def norm_value(key: str, value: str):
    if value == "":
        return None
    if key in BOOL_COLUMNS:
        return 1 if value.strip().lower() == "true" else 0
    if key in REAL_COLUMNS:
        return float(value)
    return value


def log_ingestion(conn: sqlite3.Connection, source: str, request: str, status: str, rows: int, detail: str = ""):
    conn.execute(
        "INSERT INTO raw_ingestion_log(source, request, status, row_count, detail, ingested_at_utc) VALUES(?,?,?,?,?,?)",
        (source, request, status, rows, detail, datetime.now(timezone.utc).isoformat()),
    )


def ingest_csv(conn: sqlite3.Connection, filename: str, table: str, ddl: str):
    conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.execute(f"CREATE TABLE {table} ({ddl})")
    path = DATA / filename
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        placeholders = ",".join("?" for _ in cols)
        sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
        batch = []
        n = 0
        for row in reader:
            batch.append(tuple(norm_value(c, row[c]) for c in cols))
            if len(batch) >= 5000:
                conn.executemany(sql, batch)
                n += len(batch)
                batch.clear()
        if batch:
            conn.executemany(sql, batch)
            n += len(batch)
    log_ingestion(conn, filename, filename, "200", n)


def ingest_product_usage(conn: sqlite3.Connection):
    table = "raw_product_usage_events"
    conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.execute(
        f"""CREATE TABLE {table} (
            ingestion_row_id INTEGER PRIMARY KEY,
            event_id TEXT, account_id TEXT, user_email TEXT,
            event_name TEXT, event_ts TEXT, session_id TEXT
        )"""
    )
    path = DATA / "product_usage_events.jsonl.gz"
    sql = f"INSERT INTO {table}(event_id,account_id,user_email,event_name,event_ts,session_id) VALUES(?,?,?,?,?,?)"
    batch = []
    n = 0
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            batch.append((r["event_id"], r["account_id"], r["user_email"], r["event_name"], r["event_ts"], r["session_id"]))
            if len(batch) >= 10000:
                conn.executemany(sql, batch)
                n += len(batch)
                batch.clear()
        if batch:
            conn.executemany(sql, batch)
            n += len(batch)
    log_ingestion(conn, "product_usage_events.jsonl.gz", "product_usage_events.jsonl.gz", "200", n)


def ingest_cs_health(conn: sqlite3.Connection):
    table = "raw_cs_health_snapshots"
    conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.execute(
        f"""CREATE TABLE {table} (
            ingestion_row_id INTEGER PRIMARY KEY,
            snapshot_id TEXT, account_id TEXT, snapshot_month TEXT, health_score REAL,
            csm_user_id TEXT, renewal_risk TEXT, open_tickets INTEGER,
            source_page INTEGER, source_request TEXT
        )"""
    )
    api_dir = DATA / "cs_health_api"
    request = "cursor_01.json"
    seen_requests = 0
    while request:
        seen_requests += 1
        if seen_requests > 100:
            raise RuntimeError("CS API pagination exceeded 100 requests; possible cursor loop")
        path = api_dir / request
        with path.open(encoding="utf-8") as f:
            payload = json.load(f)
        if "error" in payload:
            retry_after = int(payload.get("retry_after_seconds", 0))
            log_ingestion(conn, "cs_health_api", request, str(payload.get("status", "error")), 0, payload["error"])
            time.sleep(retry_after)
            request = payload["retry_url"]
            continue
        rows = [
            (
                r["snapshot_id"], r["account_id"], r["snapshot_month"], float(r["health_score"]),
                r["csm_user_id"], r["renewal_risk"], int(r["open_tickets"]),
                int(payload["page"]), request,
            )
            for r in payload["results"]
        ]
        conn.executemany(
            f"""INSERT INTO {table}(
                snapshot_id,account_id,snapshot_month,health_score,csm_user_id,renewal_risk,open_tickets,source_page,source_request
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            rows,
        )
        log_ingestion(conn, "cs_health_api", request, "200", len(rows), f"page={payload['page']}")
        nxt = payload.get("next_cursor")
        request = f"{nxt}.json" if nxt else None


def execute_model_file(conn: sqlite3.Connection, path: Path):
    sql = path.read_text(encoding="utf-8").replace("{{AS_OF_DATE}}", AS_OF_DATE)
    conn.executescript(sql)


def export_query(conn: sqlite3.Connection, sql: str, out_path: Path):
    cur = conn.execute(sql)
    headers = [d[0] for d in cur.description]
    rows = cur.fetchall()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def build_database():
    DB.parent.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute(
        """CREATE TABLE raw_ingestion_log(
            source TEXT, request TEXT, status TEXT, row_count INTEGER, detail TEXT, ingested_at_utc TEXT
        )"""
    )
    for filename, (table, ddl) in CSV_SCHEMAS.items():
        ingest_csv(conn, filename, table, ddl)
    ingest_product_usage(conn)
    ingest_cs_health(conn)
    conn.commit()

    ordered_dirs = [ROOT / "models" / "staging", ROOT / "models" / "intermediate", ROOT / "models" / "marts"]
    for d in ordered_dirs:
        for path in sorted(d.glob("*.sql")):
            print(f"[model] {path.relative_to(ROOT)}")
            execute_model_file(conn, path)
            conn.commit()

    export_query(conn, "SELECT * FROM mart_headline_metrics", ROOT / "outputs" / "headline_metrics.csv")
    export_query(conn, "SELECT * FROM audit_data_quality ORDER BY severity_rank DESC, issue", ROOT / "outputs" / "data_quality_audit.csv")
    export_query(conn, "SELECT * FROM mart_account_360 ORDER BY arr_usd DESC", ROOT / "outputs" / "account_360.csv")
    export_query(conn, "SELECT * FROM fct_arr_account_monthly ORDER BY snapshot_date, account_id", ROOT / "outputs" / "arr_account_monthly.csv")
    export_query(conn, "SELECT * FROM mart_pipeline_by_stage ORDER BY stage_order", ROOT / "outputs" / "pipeline_by_stage.csv")
    conn.close()


def main():
    print(f"Building Northwind warehouse as of {AS_OF_DATE} -> {DB}")
    build_database()
    from tests.run_tests import run_tests
    run_tests()
    print("Build complete. Headline metrics: outputs/headline_metrics.csv")


if __name__ == "__main__":
    main()
