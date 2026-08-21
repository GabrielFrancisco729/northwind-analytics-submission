# RevOps Analytics & BI Lead — Practical Case

**Time budget: 4 hours, hard cap.** You have 4 calendar days to return it. We would
rather see 4 hours of good judgment than 20 hours of polish, and we grade partial
work fairly — see *If you run out of time* at the end.

**Use whatever tools you normally use, AI assistants included.** We do not care
whether an LLM wrote your SQL. We care that you can defend every decision in it,
because the next stage is a live session where we will ask you to change things.
Just tell us in your README what you used and for what.

**`SCHEMA.md` in this pack maps every source and how they join.** Read it first —
we would rather you spent your four hours on judgment than on guessing column
names.

---

## The situation

You have joined **Northwind Analytics**, a B2B SaaS company selling compliance
software, around $34M ARR across four regions. This is a fictional company and a
fully synthetic dataset — no real customer data anywhere in it.

Right now, three different people produce three different ARR numbers. The CRO's
board deck, the Finance model, and the Sales team's own dashboard disagree, and
every leadership meeting starts with twenty minutes of reconciliation instead of
decisions. Nobody trusts the funnel metrics enough to act on them.

You have been hired to fix this. Stand up the first version of a trusted data layer
and the reporting on top of it, then tell the leadership team something they do not
already know.

**Treat today as 2026-06-30.** Any metric "as of today" means as of that date.

---

## What you are given

Everything is in `data/`, and `SCHEMA.md` describes all of it.

| Source | Format |
|---|---|
| `crm_accounts.csv` | CSV — accounts, with a parent/child hierarchy |
| `crm_opportunities.csv` | CSV — deals: New Business / Expansion / Renewal |
| `crm_opportunity_stage_history.csv` | CSV — stage transitions, timestamped |
| `crm_users.csv` | CSV — reps, managers, CSMs |
| `billing_subscriptions.csv` | CSV — the ARR source of record |
| `fx_rates_daily.csv` | CSV — daily rates to USD |
| `product_usage_events.jsonl.gz` | gzipped JSONL — ~1.1M product events |
| `cs_health_api/` | JSON files — a **paginated REST API** you have to walk |

The CS health data is deliberately not a file. Start at `cursor_01.json`, follow
`next_cursor` until it is null, and treat each file as one HTTP GET. At least one
call fails the way real APIs fail. Handle it the way you would in production.

**This data is not clean.** It is a realistic export from a CRM real humans have
typed into for two years, plus an event stream with at-least-once delivery. Assume
nothing. Part of what we are assessing is what you notice.

---

## What we want back

A single Git repository. Send a GitHub/GitLab link, or a zip — but if you zip it,
**include the `.git` directory**; we want to see your commit history.

### 1. A curated data layer

dbt is what we use, so dbt is the easy answer — SQLMesh, plain SQL + a runner, or
Python is fine if you are faster in it and can explain the trade-off. Warehouse is
your call; DuckDB locally is completely acceptable.

- Clear layering from raw → staging → marts, with the reason for each layer visible
  in the structure
- A **dimensional design** for the marts, with the grain of every table stated
  explicitly
- **Tests** that would actually have caught the problems you found — uniqueness,
  not-null, referential integrity, and at least a couple of business-logic
  assertions
- Documentation of what each model is *for*, not a restatement of its columns
- Reproducible ingestion: we clone your repo, run one documented command, and all
  eight sources land

### 2. A metric definitions document

The actual deliverable of this role. For each metric: a plain-English definition,
the grain, the exact inclusion and exclusion rules, how you handled currency, and
the edge case that made you stop and think.

**Required — five metrics:**

- **Active ARR** (as of a date)
- **Net New ARR** (for a period)
- **Gross and Net Revenue Retention**
- **Win Rate**
- **Open Pipeline and Pipeline Coverage**

**Optional, only if you have time:** Average Sales Cycle, stage-to-stage conversion
rate.

Write it as if Finance and Sales will both have to sign it. Where the data forces a
judgment call, make the call, state it, and say what you would verify with a
stakeholder. "It depends" is not an answer; "I chose X because Y, and I would
confirm Z with the CFO" is.

**If a metric needs an input this dataset does not contain, say so.** State what you
would need, who you would ask for it, and what you did in the meantime. Do not
silently invent it, and do not skip the metric.

### 3. Your headline numbers

A small table with these, so we can compare against ours. Windows are given so
there is no ambiguity:

| Figure | Window |
|---|---|
| Active ARR, in USD | as of 2026-06-30 |
| Count of active customer accounts | as of 2026-06-30 |
| New Business won, in USD | 2026-04-01 → 2026-06-30 |
| New Business win rate | 2025-07-01 → 2026-06-30 |
| Open pipeline, in USD | as of 2026-06-30 |

Add the optional metrics to the table only if you built them.

### 4. A dashboard

Any tool: Looker Studio, Metabase, Superset, Evidence, Hex, Streamlit, Power BI,
Tableau, or a hand-built page. Ship screenshots or a recorded walkthrough in the
repo so we can grade it without your credentials, plus the underlying queries.

**One dashboard is enough.** Use a filter or a toggle rather than building separate
pages. But state in one line who each view is for — the CRO glancing at it before a
board call needs something different from a sales manager working out why a number
moved.

We will be looking at whether a reader can tell good from bad without reading a
legend, whether the layout has a hierarchy, and whether you resisted putting
everything on the page. Include at least one view of the **account hierarchy or
customer relationship structure** — the data has parents and children in it.

### 5. One analytical recommendation

One page, or three slides.

> The CS team has told leadership that **product engagement fell sharply from March
> onwards**, and wants budget next quarter for a re-onboarding programme aimed at
> disengaged accounts. Before we fund it: is that the right place to intervene?
> Show us what the data supports, and what you would do instead if it doesn't.

A claim, the evidence, the size of the opportunity, and a concrete action. One
well-defended finding beats five observations. If something in the data made you
distrust a conclusion you had initially reached, tell us — we weight that heavily.

### 6. A small predictive artifact — pick exactly one

Deliberately scoped small. Choose whichever you would actually reach for:

- a next-quarter bookings or pipeline forecast, with stated uncertainty
- a churn or expansion propensity score for accounts
- a segmentation that changes how someone would act

Same requirements whichever you pick: state your features, how you would validate it
(show a backtest or holdout if you can), its failure modes, and one sentence on how a
rep or leader would use it. A well-reasoned logistic regression beats a mysterious
gradient-boosted model. We want to see that you know when a model is worth building
and when a well-chosen ratio does the job.

---

## How we will assess it

| Dimension | Weight |
|---|---|
| Metric definitions & business-logic correctness | 25% |
| Data modeling & warehouse design | 20% |
| Dashboard and visualization craft | 20% |
| Ingestion & pipeline hygiene | 15% |
| Analytical narrative & recommendation | 12% |
| Predictive artifact | 8% |

Two things sit outside the rubric and matter as much as it:

**Assumptions and decisions.** Your README should list what you assumed, what you
decided, what you deliberately left out, and what you would ask a stakeholder. This
is the section we read first.

**Data quality findings.** A short list of every problem you found in the data, what
you did about it, and which ones you would escalate to a human rather than fix in
code. We know exactly what is in there.

---

## The live session

90 minutes, within a week of your submission. You will present for 15 minutes, we
will ask about your decisions for 30, then we will hand you a **new requirement you
have not seen** and work through it together for 25 — reasoning out loud matters more
than finishing. The last 20 minutes are a conversation with a stakeholder who thinks
one of your numbers is wrong.

Nothing to prepare beyond knowing your own work.

---

## If you run out of time

Stop at the cap and submit what you have. Build in this order, and say in your README
where you stopped and what you would have done next:

1. Ingestion of the CRM + billing sources, and a defensible **Active ARR**
2. The curated model layer with tests
3. The metric definitions document and your headline numbers
4. The dashboard
5. **Validating the CS team's engagement claim**, and the recommendation
6. The remaining sources (usage events, CS health) fully modelled
7. The predictive artifact

Deciding what to cut *is* part of the exercise. A submission that stops at step 4
with clear reasoning scores better than one that reaches step 7 by rushing
everything.

Questions about the case are welcome and cost you nothing — ask.
