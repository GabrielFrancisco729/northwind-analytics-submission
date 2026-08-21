# Northwind Analytics — trusted revenue & funnel layer

## Assumptions and decisions — read this first

1. **Billing, not CRM, is the source of record for ARR.** CRM opportunities measure sales process/bookings; subscription terms measure contracted recurring revenue.
2. **“Today” is hard-coded to 2026-06-30 for this case.** Future product events and future stage transitions stay in raw but are excluded from as-of logic.
3. **Subscription status is not used to decide historical activity.** Effective coverage is `[term_start, min(term_end, replacement_start))`. This is necessary because future successors are already marked `Active`, while valid predecessors can already be marked `Amended`.
4. **I do not auto-merge CRM accounts by domain.** Duplicate domains are a real MDM issue, but account ID is the billing join grain and some duplicates may be separate legal entities. Parent/child hierarchy is preserved for reporting instead.
5. **Opportunity amounts must be positive to enter dollar metrics.** Nineteen rows are zero/negative. They remain available for count-based funnel outcomes but their monetary value is quarantined.
6. **Win Rate is count-based New Business win rate.** Closed Won / (Won + Lost), periodized by a resolved close date. This is intentionally not amount-weighted.
7. **Open Pipeline means growth pipeline: New Business + Expansion.** Renewal is excluded because its economics are measured in retention. For transparency, including Renewal would be $28.47M versus the signed $16.98M growth-pipeline figure.
8. **Pipeline Coverage cannot be signed from this dataset.** There is no bookings/quota target. I show the pipeline numerator and `N/A`; I would ask VP Sales / FP&A for the Q3 target and scope.
9. **Retention is calculated at billing account grain and constant period-end FX.** This avoids hiding one child's churn with another child's expansion and prevents FX noise from appearing as Net New ARR.
10. **The CS “engagement fell from March onwards” claim is rejected.** March 10–31 is a telemetry-completeness incident; April–June engagement is back above Jan–Feb. I recommend fixing telemetry and targeting four genuinely declining/risky accounts ($522.7k ARR) instead of a broad re-onboarding programme.
11. **Predictive artifact is a small, explainable bookings forecast.** Logistic regression is intentionally preferred over a more complex model. The Q2 holdout ranks reasonably (AUC 0.737) but underpredicts dollars by 25.6%, so I present uncertainty and do not call it production-ready.
12. **Deliberately left out:** optional Average Sales Cycle and stage-to-stage conversion. The stage-history gaps (300 opportunities) make those lower-confidence than the required metrics, and the case explicitly rewards stopping before adding weak metrics.

## Headline numbers

| Figure | Window | Result |
|---|---|---:|
| Active ARR, USD | as of 2026-06-30 | **$34,736,511** |
| Active customer accounts | as of 2026-06-30 | **296** |
| New Business won, USD | 2026-04-01 → 2026-06-30 | **$2,708,919** |
| New Business win rate | 2025-07-01 → 2026-06-30 | **25.71% (126 / 490)** |
| Open growth pipeline, USD | as of 2026-06-30 | **$16,978,396** |

The executable output is `outputs/headline_metrics.csv`; full signed definitions are in [`docs/METRICS.md`](docs/METRICS.md).

## Reproduce it

Python 3.11+ is sufficient for the warehouse build. SQLite is in the Python standard library; no database server or credentials are required.

```bash
# Curated layer + all 8 source ingestions + tests
python run_pipeline.py

# Full submission including analysis, forecast and static dashboard/screenshots
pip install -r requirements.txt
make all
```

The CS endpoint is ingested as an API, not flattened by hand: the runner starts at `cursor_01.json`, follows `next_cursor`, logs each request, receives the simulated 429 on page 5, sleeps for the requested 2 seconds, and retries `cursor_05_retry.json`.

A clean warehouse rebuild takes roughly seconds-to-tens-of-seconds locally, dominated by the ~1.1M-row gzip event stream. `warehouse/northwind.db` is disposable and rebuilt from `data/`.

## Architecture

```text
data/                     # supplied eight sources
src/pipeline.py            # reproducible ingestion + SQL runner
models/
  staging/                 # source cleanup, dedupe/watermark flags
  intermediate/            # reusable subscription and opportunity logic
  marts/                   # dimensional facts/dims, metrics, account 360, DQ audit
tests/run_tests.py         # 32 executable curated-layer assertions
analysis/                  # engagement investigation + bookings forecast
dashboard/                 # one static dashboard with Executive / Sales Manager toggle
docs/                      # metric contract, model design, DQ, recommendation, forecast
outputs/                   # grader-friendly CSV/JSON/PNG artifacts
warehouse/northwind.db     # local analytical warehouse
```

This is deliberately **plain SQL + a small Python runner on SQLite** rather than dbt. For this four-hour-style case, it minimizes environment/setup risk while keeping layer boundaries, SQL, tests, lineage, and grains explicit. In a shared production repo I would port these model files to dbt/DuckDB or the company's warehouse so dbt owns dependency resolution, docs generation, freshness, and CI selection.

See [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) for every mart's grain and purpose.

## Dashboard

Open `dashboard/index.html` in a browser. It is one credential-free dashboard with a toggle:

- **Executive / CRO view:** board-call glance — ARR, Net New/retention, win rate, growth pipeline, forecast, and the telemetry warning.
- **Sales Manager view:** diagnose what moved — pipeline by stage, account-risk shortlist, and CRM parent/child relationship structure.

Screenshots are shipped in `dashboard/screenshots/` and the queries feeding the dashboard are in `dashboard/queries/`.

## Analytical recommendation

**Do not fund a broad re-onboarding programme from the March aggregate.** The event stream is normal through March 9, captures only ~15% of expected activity March 10–31, and recovers April 1. Apr–Jun activity is 3.4% above Jan–Feb. Instead: fix/monitor telemetry and run a focused re-engagement pilot on four accounts / **$522.7k ARR** where post-recovery usage decline, CS risk, and contract timing all agree.

Full one-page evidence: [`docs/RECOMMENDATION.md`](docs/RECOMMENDATION.md).

## Predictive artifact

I picked exactly one: **Q3 growth bookings forecast**. A regularized logistic regression estimates 92-day win probability from stage, type, source, account attributes, amount, age, and stage age. Current expectation is **$2.41M**, with simulated P10–P90 **$1.66M–$3.22M**. Holdout AUC is **0.737**, but the Q2 dollar backtest underpredicted by 25.6%, which is explicitly treated as a failure mode rather than hidden.

Details: [`docs/PREDICTIVE_ARTIFACT.md`](docs/PREDICTIVE_ARTIFACT.md).

## Data quality findings

The build writes both a queryable `audit_data_quality` mart and `outputs/data_quality_audit.csv`. High-impact findings include negative/zero opportunity amounts, impossible close dates, amendment overlap, event duplicates, future-dated usage/stage data, CS pagination duplicates, missing CS months, CRM duplicate domains, and missing account region/segment. Nothing that requires a business identity/economics decision is silently repaired.

Full list and owners: [`docs/DATA_QUALITY.md`](docs/DATA_QUALITY.md).

## Tests

`python tests/run_tests.py` currently runs **32 assertions**, including uniqueness, referential integrity, subscription interval validity, no post-replacement overlap, usage deduplication/watermark, account hierarchy resolution, ARR non-negativity, CRM outcome-flag consistency, and headline reconciliation.

Known source defects are **audits**, not failing curated tests. This distinction lets CI tell us whether the transformation is trustworthy while still surfacing upstream problems that need owners.

## Tools used

- **Python**: ingestion/orchestration, API retry, analysis, exports.
- **SQLite + SQL**: local warehouse and curated dimensional layer.
- **pandas / scikit-learn**: analytical validation and the small logistic-regression forecast.
- **matplotlib**: evidence/forecast figures.
- **Pillow + hand-built HTML/CSS/JS**: credential-free dashboard screenshots and interactive dashboard artifact.
- **ChatGPT / OpenAI assistant**: used to accelerate source profiling, challenge metric edge cases, structure SQL/tests, and draft documentation. I validated the decisions against the supplied schema/data; the live-session-ready logic lives in the repository, not in an external prompt.

## What I would ask stakeholders next

- **CFO / Finance:** should board-level NRR aggregate corporate families or contractual billing accounts? How should reactivations be labeled in Net New ARR?
- **VP Sales / FP&A:** what is the Q3 bookings target and does pipeline coverage include Expansion and/or Renewal? Budget FX or spot FX?
- **Sales Ops:** are negative opportunity amounts valid contraction/credit motions or bad CRM data? Can we enforce `close_date >= created_date`?
- **RevOps / Finance:** what is the canonical-account policy for shared domains and parent/child legal entities?
- **Product/Data Platform:** what changed on March 10 and April 1 in telemetry, and can we add completeness SLAs before CS health consumes usage?
- **CS Ops:** are missing monthly health snapshots expected, and is the health model itself using the under-captured March telemetry?
