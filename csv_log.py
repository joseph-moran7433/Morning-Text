"""
csv_log.py

Append-only logging so prediction accuracy can be checked later.

predictions.csv -- one row per (run, target_date) pair. Every nightly run
appends a fresh row for each of the 7 days it forecasts, so the same
target_date accumulates up to 7 rows over time (one per days_ahead lead
time: 6 days out, 5 days out, ..., down to 0 -- the morning-of call).

actuals.csv -- one row per calendar date, appended once (the night after
that date, right before generating the next forecast). Duplicate runs on
the same day won't double-log a date that's already present.
"""

import csv
import os

PREDICTIONS_FILE = "predictions.csv"
ACTUALS_FILE = "actuals.csv"

PREDICTIONS_HEADER = [
    "run_timestamp",
    "target_date",
    "days_ahead",
    "predicted_high",
    "predicted_low",
    "predicted_uniform",
    "predicted_heat_category",
    "predicted_cold_risk",
]

ACTUALS_HEADER = ["date", "actual_high", "actual_low", "station_id_used"]


def _ensure_header(path, header):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        with open(path, "w", newline="") as f:
            csv.writer(f).writerow(header)


def append_predictions(run_timestamp, summaries):
    """summaries: list of per-day dicts from advisory.build_daily_summaries,
    in order, where list index == days_ahead."""
    _ensure_header(PREDICTIONS_FILE, PREDICTIONS_HEADER)
    with open(PREDICTIONS_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        for days_ahead, s in enumerate(summaries):
            heat_cat = s["heat"]["category"] if s["heat"] else ""
            writer.writerow([
                run_timestamp,
                s["target_date"],
                days_ahead,
                s["high"],
                s["low"],
                s["uniform"],
                heat_cat,
                s["cold_risk"],
            ])


def already_logged_actual(date_str):
    if not os.path.exists(ACTUALS_FILE):
        return False
    with open(ACTUALS_FILE, newline="") as f:
        for row in csv.DictReader(f):
            if row["date"] == date_str:
                return True
    return False


def append_actual(date_str, actual_high, actual_low, station_id):
    if already_logged_actual(date_str):
        return False
    _ensure_header(ACTUALS_FILE, ACTUALS_HEADER)
    with open(ACTUALS_FILE, "a", newline="") as f:
        csv.writer(f).writerow([date_str, actual_high, actual_low, station_id])
    return True
