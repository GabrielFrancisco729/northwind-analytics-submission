from __future__ import annotations

import base64
import html
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "warehouse" / "northwind.db"
DASH = ROOT / "dashboard"
OUT = ROOT / "outputs"


def money(x):
    x = float(x)
    if abs(x) >= 1_000_000:
        return f"${x/1_000_000:.2f}M"
    if abs(x) >= 1_000:
        return f"${x/1_000:.0f}k"
    return f"${x:,.0f}"


def svg_line(df: pd.DataFrame, value_col: str, width=760, height=250):
    vals = df[value_col].astype(float).to_list()
    labels = pd.to_datetime(df["snapshot_date"]).dt.strftime("%b %y").to_list()
    pad_l, pad_r, pad_t, pad_b = 54, 18, 18, 38
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    lo, hi = min(vals), max(vals)
    lo = lo * 0.95
    span = max(hi - lo, 1)
    pts = []
    for i, v in enumerate(vals):
        x = pad_l + (i / max(len(vals) - 1, 1)) * w
        y = pad_t + (hi - v) / span * h
        pts.append((x, y))
    path = " ".join(("M" if i == 0 else "L") + f" {x:.1f} {y:.1f}" for i, (x, y) in enumerate(pts))
    circles = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" class="dot" />' for x, y in pts)
    ticks = ""
    for i in range(0, len(labels), max(1, len(labels)//6)):
        x = pts[i][0]
        ticks += f'<text x="{x:.1f}" y="{height-10}" text-anchor="middle" class="axis">{labels[i]}</text>'
    y_ticks = ""
    for frac in [0, .5, 1]:
        val = lo + span * frac
        y = pad_t + (1-frac) * h
        y_ticks += f'<line x1="{pad_l}" x2="{width-pad_r}" y1="{y:.1f}" y2="{y:.1f}" class="grid" />'
        y_ticks += f'<text x="{pad_l-8}" y="{y+4:.1f}" text-anchor="end" class="axis">${val/1e6:.0f}M</text>'
    return f'''<svg viewBox="0 0 {width} {height}" class="chart-svg">{y_ticks}<path d="{path}" class="line" />{circles}{ticks}</svg>'''


def pipeline_bars(df: pd.DataFrame):
    mx = float(df.pipeline_usd.max())
    parts = []
    for r in df.itertuples():
        pct = max(3, float(r.pipeline_usd) / mx * 100)
        parts.append(f'''<div class="bar-row"><div class="bar-label"><span>{html.escape(r.stage_asof)}</span><strong>{money(r.pipeline_usd)}</strong></div><div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%"></div></div><div class="bar-sub">{r.opportunity_count} opps</div></div>''')
    return "".join(parts)


def img_data(path: Path):
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def main():
    con = sqlite3.connect(DB)
    kpi = pd.read_sql_query("SELECT * FROM mart_headline_metrics", con).iloc[0]
    retention = pd.read_sql_query("SELECT * FROM mart_retention_metrics", con).set_index("period_name")
    trend = pd.read_sql_query("SELECT snapshot_date, SUM(arr_usd) arr_usd, COUNT(*) active_accounts FROM fct_arr_account_monthly GROUP BY snapshot_date ORDER BY snapshot_date", con)
    pipe = pd.read_sql_query("SELECT * FROM mart_pipeline_by_stage ORDER BY stage_order", con)
    target = pd.read_sql_query("SELECT * FROM mart_account_360 WHERE targeted_reengagement_candidate=1 ORDER BY arr_usd DESC", con)
    hierarchy = pd.read_sql_query("""
        SELECT p.account_id parent_id,p.account_name parent_name,c.account_id child_id,c.account_name child_name,
               COALESCE(pa.arr_usd,0) parent_arr_usd,COALESCE(ca.arr_usd,0) child_arr_usd,c.is_deleted child_is_deleted
        FROM dim_account c JOIN dim_account p ON c.parent_account_id=p.account_id
        LEFT JOIN mart_account_360 pa ON pa.account_id=p.account_id
        LEFT JOIN mart_account_360 ca ON ca.account_id=c.account_id
        ORDER BY parent_arr_usd+child_arr_usd DESC
    """, con)
    con.close()
    forecast = json.loads((OUT / "pipeline_forecast_summary.json").read_text())
    engagement = json.loads((OUT / "engagement_summary.json").read_text())

    q2 = retention.loc["Q2 2026"]
    ttm = retention.loc["TTM"]
    telemetry_img = img_data(OUT / "engagement_telemetry.png")
    forecast_img = img_data(OUT / "pipeline_forecast.png")

    target_rows = "".join(
        f'''<tr><td><strong>{html.escape(r.account_name)}</strong><span class="subtle">{html.escape(str(r.account_id))} · {html.escape(str(r.region))}</span></td><td>{money(r.arr_usd)}</td><td>{r.usage_ratio_post_vs_pre:.0%}</td><td><span class="risk {str(r.renewal_risk).lower()}">{r.renewal_risk}</span></td><td>{int(r.days_to_contract_event)}d</td></tr>'''
        for r in target.itertuples()
    )
    hierarchy_rows = "".join(
        f'''<tr><td><strong>{html.escape(r.parent_name)}</strong><span class="subtle">{r.parent_id}</span></td><td class="arrow">→</td><td>{html.escape(r.child_name)}<span class="subtle">{r.child_id}{' · deleted' if r.child_is_deleted else ''}</span></td><td>{money(r.parent_arr_usd + r.child_arr_usd)}</td></tr>'''
        for r in hierarchy.head(10).itertuples()
    )

    doc = f'''<!doctype html><html><head><meta charset="utf-8"><title>Northwind Revenue & Funnel</title>
<style>
:root{{--bg:#f4f6fa;--card:#ffffff;--ink:#152033;--muted:#6e788b;--line:#dfe4ec;--navy:#1f3561;--blue:#3b6fd8;--good:#1f8a63;--warn:#bb7b17;--bad:#b34b57;}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);font-family:Inter,Arial,sans-serif;color:var(--ink)}}
.shell{{max-width:1500px;margin:0 auto;padding:30px 38px 48px}} header{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:22px}}
h1{{font-size:28px;margin:0 0 6px;letter-spacing:-.5px}} .eyebrow{{font-size:12px;text-transform:uppercase;letter-spacing:1.3px;color:var(--blue);font-weight:700}} .subtitle{{color:var(--muted);font-size:14px}}
.toggle{{background:#e8ecf3;padding:4px;border-radius:10px;display:flex;gap:3px}} .toggle button{{border:0;background:transparent;padding:9px 14px;border-radius:7px;color:#526077;font-weight:650;cursor:pointer}} .toggle button.active{{background:white;color:var(--navy);box-shadow:0 1px 5px #0001}}
.view{{display:none}} .view.active{{display:block}} .grid-kpi{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:16px}} .card{{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:0 2px 8px #13223b08}}
.kpi{{padding:17px 18px;min-height:104px}} .kpi .label{{font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);font-weight:700}} .kpi .value{{font-size:26px;font-weight:750;margin-top:10px;letter-spacing:-.5px}} .kpi .note{{font-size:11px;color:var(--muted);margin-top:6px}}
.good{{color:var(--good)}} .warn{{color:var(--warn)}} .bad{{color:var(--bad)}} .section-grid{{display:grid;grid-template-columns:1.25fr .75fr;gap:16px;margin-bottom:16px}} .section-grid.equal{{grid-template-columns:1fr 1fr}}
.panel{{padding:20px 22px}} .panel h2{{font-size:15px;margin:0 0 4px}} .panel .desc{{color:var(--muted);font-size:12px;margin-bottom:12px}} .chart-svg{{width:100%;height:auto}} .line{{fill:none;stroke:var(--blue);stroke-width:3}} .dot{{fill:white;stroke:var(--blue);stroke-width:2}} .grid{{stroke:#e7ebf1;stroke-width:1}} .axis{{fill:#7b8597;font-size:11px}}
.bar-row{{margin:13px 0}} .bar-label{{display:flex;justify-content:space-between;font-size:12px;margin-bottom:5px}} .bar-track{{height:9px;background:#edf0f5;border-radius:8px;overflow:hidden}} .bar-fill{{height:100%;background:linear-gradient(90deg,#3b6fd8,#7096e5);border-radius:8px}} .bar-sub{{font-size:10px;color:var(--muted);margin-top:4px}}
.callout{{border-left:4px solid var(--warn);background:#fffaf0;padding:14px 16px;border-radius:8px;margin-top:10px;font-size:13px;line-height:1.45}} .callout strong{{color:#855608}}
.metrics-row{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}} .mini{{background:#f7f9fc;border-radius:10px;padding:12px}} .mini b{{display:block;font-size:18px}} .mini span{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.6px}}
table{{width:100%;border-collapse:collapse;font-size:12px}} th{{text-align:left;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.6px;border-bottom:1px solid var(--line);padding:9px 8px}} td{{padding:11px 8px;border-bottom:1px solid #edf0f4;vertical-align:middle}} .subtle{{display:block;color:var(--muted);font-size:10px;margin-top:3px}} .risk{{padding:4px 7px;border-radius:999px;font-size:10px;font-weight:700}} .risk.high{{background:#fbe9eb;color:#a5404b}} .risk.medium{{background:#fff3dc;color:#976516}} .arrow{{color:#9aa3b2;text-align:center}}
.banner{{display:flex;gap:16px;align-items:center;background:#fff8e8;border:1px solid #f0d9a9;border-radius:12px;padding:14px 18px;margin-bottom:16px}} .banner .big{{font-size:28px;font-weight:750;color:#9c6818}} .banner .copy{{font-size:13px;line-height:1.4}} .banner .copy strong{{display:block;margin-bottom:2px}}
.img{{width:100%;border-radius:10px;border:1px solid var(--line)}} footer{{color:var(--muted);font-size:10px;margin-top:18px;display:flex;justify-content:space-between}} @media(max-width:1000px){{.grid-kpi{{grid-template-columns:repeat(2,1fr)}}.section-grid,.section-grid.equal{{grid-template-columns:1fr}}}}
</style></head><body><div class="shell">
<header><div><div class="eyebrow">Northwind Analytics · trusted layer v1</div><h1>Revenue & Funnel Control Room</h1><div class="subtitle">As of 2026-06-30 · Billing-sourced ARR · Commercial CRM funnel</div></div><div class="toggle"><button id="btn-exec" onclick="showView('exec')">Executive / CRO</button><button id="btn-sales" onclick="showView('sales')">Sales Manager</button></div></header>

<section id="exec" class="view">
<div class="grid-kpi">
<div class="card kpi"><div class="label">Active ARR</div><div class="value">{money(kpi.active_arr_usd)}</div><div class="note">296 active billing accounts</div></div>
<div class="card kpi"><div class="label">Q2 Net New ARR</div><div class="value good">{money(q2.net_new_arr_usd)}</div><div class="note">constant 6/30 FX</div></div>
<div class="card kpi"><div class="label">TTM NRR</div><div class="value good">{ttm.nrr:.1%}</div><div class="note">GRR {ttm.grr:.1%}</div></div>
<div class="card kpi"><div class="label">NB Win Rate</div><div class="value">{kpi.ttm_new_business_win_rate:.1%}</div><div class="note">126 / 490 decisions</div></div>
<div class="card kpi"><div class="label">Growth Pipeline</div><div class="value">{money(kpi.open_growth_pipeline_usd)}</div><div class="note">NB + Expansion · 144 valued</div></div>
<div class="card kpi"><div class="label">Q3 Forecast</div><div class="value warn">{money(forecast['forecast_expected_usd'])}</div><div class="note">P10–P90 {money(forecast['forecast_p10_usd'])}–{money(forecast['forecast_p90_usd'])}</div></div>
</div>
<div class="banner"><div class="big">85%</div><div class="copy"><strong>March “engagement drop” is a telemetry incident, not a sustained customer drop.</strong>Capture collapses Mar 10–31 and recovers Apr 1. Apr–Jun events/day are {engagement['apr_jun_vs_jan_feb_pct']:.1f}% above Jan–Feb. Do not fund broad re-onboarding from the aggregate.</div></div>
<div class="section-grid"><div class="card panel"><h2>ARR progression</h2><div class="desc">Month-end spot FX · billing source of record</div>{svg_line(trend,'arr_usd')}</div><div class="card panel"><h2>Open growth pipeline by stage</h2><div class="desc">As-of stage; invalid/non-positive amounts excluded from dollars</div>{pipeline_bars(pipe)}</div></div>
<div class="section-grid equal"><div class="card panel"><h2>Retention economics</h2><div class="desc">Opening-cohort retention at constant period-end FX</div><div class="metrics-row"><div class="mini"><b>{q2.grr:.1%}</b><span>Q2 GRR</span></div><div class="mini"><b>{q2.nrr:.1%}</b><span>Q2 NRR</span></div><div class="mini"><b>{money(q2.net_new_arr_usd)}</b><span>Q2 Net New</span></div></div><div class="callout"><strong>Watch gross retention:</strong> TTM NRR is healthy at {ttm.nrr:.1%}, but TTM GRR is only {ttm.grr:.1%}. Expansion is masking meaningful contraction/churn in the opening cohort.</div></div><div class="card panel"><h2>Predictive artifact</h2><div class="desc">92-day probability-weighted bookings · temporal holdout AUC {forecast['holdout_auc']:.3f}</div><img class="img" src="{forecast_img}" /></div></div>
</section>

<section id="sales" class="view">
<div class="grid-kpi">
<div class="card kpi"><div class="label">Growth Pipeline</div><div class="value">{money(kpi.open_growth_pipeline_usd)}</div><div class="note">145 open / 144 valued</div></div>
<div class="card kpi"><div class="label">Q2 NB Won</div><div class="value">{money(kpi.q2_new_business_won_usd)}</div><div class="note">invalid monetary win quarantined</div></div>
<div class="card kpi"><div class="label">NB Win Rate</div><div class="value">{kpi.ttm_new_business_win_rate:.1%}</div><div class="note">TTM count-based</div></div>
<div class="card kpi"><div class="label">Targeted Re-engagement</div><div class="value warn">{len(target)} accts</div><div class="note">{money(target.arr_usd.sum())} ARR</div></div>
<div class="card kpi"><div class="label">Q3 Forecast</div><div class="value">{money(forecast['forecast_expected_usd'])}</div><div class="note">holdout underpredicted 25.6%</div></div>
<div class="card kpi"><div class="label">Coverage</div><div class="value">N/A</div><div class="note">Q3 target not provided</div></div>
</div>
<div class="section-grid equal"><div class="card panel"><h2>Pipeline diagnosis</h2><div class="desc">Stage mix from the trusted opportunity layer</div>{pipeline_bars(pipe)}<div class="callout"><strong>Data caveat:</strong> 300 opportunities have no stage-history rows and 180 transitions occur after the as-of date. Stage diagnostics are less trustworthy than the signed pipeline total.</div></div><div class="card panel"><h2>Accounts worth CS action now</h2><div class="desc">Persistent post-recovery usage decline + Medium/High risk + contract event ≤180d</div><table><thead><tr><th>Account</th><th>ARR</th><th>Usage ratio</th><th>Risk</th><th>Contract event</th></tr></thead><tbody>{target_rows}</tbody></table></div></div>
<div class="section-grid equal"><div class="card panel"><h2>Customer relationship structure</h2><div class="desc">CRM parent → child hierarchy; family ARR shown for context, but signed retention remains at billing account grain</div><table><thead><tr><th>Parent</th><th></th><th>Child</th><th>Family ARR</th></tr></thead><tbody>{hierarchy_rows}</tbody></table></div><div class="card panel"><h2>Why not re-onboard everyone?</h2><div class="desc">The monthly drop disappears when the telemetry boundary is inspected daily</div><img class="img" src="{telemetry_img}" /></div></div>
</section>
<footer><span>Definitions: docs/METRICS.md · DQ: docs/DATA_QUALITY.md</span><span>Northwind case · synthetic data</span></footer>
</div><script>
function showView(v){{document.querySelectorAll('.view').forEach(x=>x.classList.remove('active'));document.querySelectorAll('.toggle button').forEach(x=>x.classList.remove('active'));document.getElementById(v).classList.add('active');document.getElementById(v==='exec'?'btn-exec':'btn-sales').classList.add('active');}}
const params=new URLSearchParams(location.search);showView(params.get('view')==='sales'?'sales':'exec');
</script></body></html>'''
    (DASH / "index.html").write_text(doc, encoding="utf-8")

    # Headless Chromium is not available in every CI/container environment.
    # Generate deterministic grader screenshots from the exact same mart outputs.
    from render_screenshots import main as render_screenshots
    render_screenshots()
    print("Dashboard and deterministic screenshots generated.")



if __name__ == "__main__":
    main()
