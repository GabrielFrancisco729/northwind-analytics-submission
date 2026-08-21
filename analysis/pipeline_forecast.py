from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "outputs"
ASOF = pd.Timestamp("2026-06-30")


def load_data():
    opp = pd.read_csv(DATA / "crm_opportunities.csv", parse_dates=["created_date", "close_date"])
    hist = pd.read_csv(DATA / "crm_opportunity_stage_history.csv", parse_dates=["changed_at"])
    acc = pd.read_csv(DATA / "crm_accounts.csv")
    fx = pd.read_csv(DATA / "fx_rates_daily.csv", parse_dates=["rate_date"])
    acc["is_internal_test"] = (
        acc.domain.isin(["example.test", "northwind-example.com"])
        | acc.account_name.str.contains(r"(?i)\btest\b|\bdemo\b|do not use|internal", regex=True)
    )
    commercial = set(acc.loc[(~acc.is_deleted) & (~acc.is_internal_test), "account_id"])
    first_close = (
        hist[hist.to_stage.isin(["5-Closed Won", "6-Closed Lost"])]
        .sort_values(["opportunity_id", "changed_at", "history_id"])
        .groupby("opportunity_id")
        .head(1)[["opportunity_id", "changed_at"]]
        .rename(columns={"changed_at": "hist_closed_at"})
    )
    opp = opp.merge(first_close, on="opportunity_id", how="left")
    opp["resolved_close_date"] = opp.close_date
    invalid = opp.close_date < opp.created_date
    fix = invalid & opp.hist_closed_at.notna()
    opp.loc[fix, "resolved_close_date"] = opp.loc[fix, "hist_closed_at"].dt.normalize()
    opp["state_closed_at"] = opp.hist_closed_at.fillna(opp.resolved_close_date)
    return opp, hist, acc, fx, commercial


def rates_asof(fx, date):
    return fx[fx.rate_date <= date].sort_values("rate_date").groupby("currency").tail(1).set_index("currency").rate_to_usd


def snapshot(opp, hist, acc, fx, commercial, date):
    date = pd.Timestamp(date)
    x = opp[
        opp.account_id.isin(commercial)
        & opp.opportunity_type.isin(["New Business", "Expansion"])
        & (opp.created_date <= date)
        & (opp.amount > 0)
    ].copy()
    x = x[(~x.is_closed) | (x.state_closed_at > date)].copy()

    h = (
        hist[hist.changed_at <= date]
        .sort_values(["opportunity_id", "changed_at", "history_id"])
        .groupby("opportunity_id")
        .tail(1)[["opportunity_id", "to_stage", "changed_at"]]
    )
    x = x.merge(h, on="opportunity_id", how="left")
    # For historical snapshots, falling back to today's CRM stage would leak future state.
    # No observed transition by the snapshot is therefore treated conservatively as Discovery.
    x["stage_asof"] = x.to_stage.fillna("1-Discovery")
    x["stage_changed_at"] = x.changed_at.fillna(x.created_date)
    x["stage_age_days"] = (date - x.stage_changed_at).dt.days.clip(lower=0)
    x["age_days"] = (date - x.created_date).dt.days.clip(lower=0)
    r = rates_asof(fx, date)
    x["amount_usd"] = x.amount * x.currency.map(r)
    x["log_amount"] = np.log1p(x.amount_usd)
    x["won_92d"] = (
        x.is_won & x.is_closed & (x.resolved_close_date > date) & (x.resolved_close_date <= date + pd.Timedelta(days=92))
    )
    x["won_amount_92d"] = np.where(x.won_92d, x.amount_usd, 0.0)
    x = x.merge(acc[["account_id", "region", "segment"]], on="account_id", how="left")
    x["snapshot"] = date
    return x


def main():
    OUT.mkdir(exist_ok=True)
    opp, hist, acc, fx, commercial = load_data()
    train_dates = pd.to_datetime([
        "2024-06-30", "2024-09-30", "2024-12-31", "2025-03-31",
        "2025-06-30", "2025-09-30", "2025-12-31",
    ])
    train = pd.concat([snapshot(opp, hist, acc, fx, commercial, d) for d in train_dates], ignore_index=True)
    holdout = snapshot(opp, hist, acc, fx, commercial, "2026-03-31")
    current = snapshot(opp, hist, acc, fx, commercial, ASOF)

    numeric = ["log_amount", "age_days", "stage_age_days"]
    categorical = ["stage_asof", "opportunity_type", "lead_source", "region", "segment"]
    pre = ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), numeric),
        ("cat", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical),
    ])
    model = Pipeline([("pre", pre), ("model", LogisticRegression(max_iter=2000, C=1.0))])
    model.fit(train[numeric + categorical], train.won_92d.astype(int))

    p_test = model.predict_proba(holdout[numeric + categorical])[:, 1]
    p_current = model.predict_proba(current[numeric + categorical])[:, 1]
    holdout_expected = float((p_test * holdout.amount_usd).sum())
    holdout_actual = float(holdout.won_amount_92d.sum())
    current_expected = float((p_current * current.amount_usd).sum())

    rng = np.random.default_rng(42)
    simulations = ((rng.random((50000, len(current))) < p_current) * current.amount_usd.to_numpy()).sum(axis=1)
    p10, p50, p90 = np.quantile(simulations, [0.10, 0.50, 0.90])

    scored = current[["opportunity_id", "account_id", "opportunity_type", "stage_asof", "lead_source", "amount_usd"]].copy()
    scored["p_win_next_92d"] = p_current
    scored["expected_bookings_usd"] = scored.amount_usd * scored.p_win_next_92d
    scored.sort_values("expected_bookings_usd", ascending=False).to_csv(OUT / "pipeline_forecast_scores.csv", index=False)

    summary = {
        "artifact": "Q3 2026 growth bookings forecast",
        "current_open_growth_pipeline_usd": round(float(current.amount_usd.sum()), 2),
        "forecast_expected_usd": round(current_expected, 2),
        "forecast_p10_usd": round(float(p10), 2),
        "forecast_p50_usd": round(float(p50), 2),
        "forecast_p90_usd": round(float(p90), 2),
        "holdout": "2026-03-31 snapshot -> next 92 days",
        "holdout_auc": round(float(roc_auc_score(holdout.won_92d, p_test)), 3),
        "holdout_average_precision": round(float(average_precision_score(holdout.won_92d, p_test)), 3),
        "holdout_brier": round(float(brier_score_loss(holdout.won_92d, p_test)), 3),
        "holdout_expected_bookings_usd": round(holdout_expected, 2),
        "holdout_actual_bookings_usd": round(holdout_actual, 2),
        "holdout_error_pct": round((holdout_expected / holdout_actual - 1) * 100, 1),
        "training_rows": int(len(train)),
        "holdout_rows": int(len(holdout)),
        "current_scored_opportunities": int(len(current)),
    }
    (OUT / "pipeline_forecast_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(8, 4.8))
    labels = ["Q2 holdout\nexpected", "Q2 holdout\nactual", "Q3 forecast\nexpected"]
    values = [holdout_expected / 1e6, holdout_actual / 1e6, current_expected / 1e6]
    ax.bar(labels, values)
    ax.errorbar(2, current_expected / 1e6,
                yerr=[[current_expected / 1e6 - p10 / 1e6], [p90 / 1e6 - current_expected / 1e6]],
                fmt="none", capsize=6)
    ax.set_ylabel("Growth bookings (USD, millions)")
    ax.set_title("Small predictive artifact: probability-weighted 92-day bookings")
    fig.tight_layout()
    fig.savefig(OUT / "pipeline_forecast.png", dpi=160)
    plt.close(fig)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
