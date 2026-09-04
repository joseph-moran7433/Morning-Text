"""
accuracy_report.py

Joins predictions.csv to actuals.csv on target_date and reports:
  1. Mean absolute temperature error (high and low), broken out by
     days_ahead -- so you can see whether 1-day-out forecasts really are
     more accurate than 6-day-out ones.
  2. How often the uniform call would have been WRONG at each lead time,
     compared to what the uniform call actually should have been that
     morning (derived from the real observed low) -- broken out by
     days_ahead.

Note on actual_low: NWS stations don't report a "0630 low" specifically --
actual_low here is the calendar day's minimum observed temperature, which
in practice occurs near dawn most of the year and is used as the closest
available real-world proxy for the 0630 PT low.

Note on the uniform comparison: predicted_uniform can include a "de-bloused"
call driven by the afternoon heat category, but actuals.csv only logs
temperature (no humidity/heat-category history), so that part can't be
re-verified after the fact. This comparison instead recomputes the
cold-layer portion of the uniform call (the part driven purely by the
morning low, which IS verifiable) from predicted_low and actual_low, and
checks whether that would have come out differently.

Run manually:
    python accuracy_report.py
"""

import csv
import os
from collections import defaultdict

from uniform_chart import cold_layer_uniform

PREDICTIONS_FILE = "predictions.csv"
ACTUALS_FILE = "actuals.csv"


def load_actuals():
    actuals = {}
    if not os.path.exists(ACTUALS_FILE):
        return actuals
    with open(ACTUALS_FILE, newline="") as f:
        for row in csv.DictReader(f):
            try:
                actuals[row["date"]] = {
                    "high": float(row["actual_high"]),
                    "low": float(row["actual_low"]),
                }
            except ValueError:
                continue
    return actuals


def load_predictions():
    rows = []
    if not os.path.exists(PREDICTIONS_FILE):
        return rows
    with open(PREDICTIONS_FILE, newline="") as f:
        for row in csv.DictReader(f):
            try:
                row["days_ahead"] = int(row["days_ahead"])
                row["predicted_high"] = float(row["predicted_high"])
                row["predicted_low"] = float(row["predicted_low"])
            except (ValueError, KeyError):
                continue
            rows.append(row)
    return rows


def main():
    actuals = load_actuals()
    predictions = load_predictions()

    if not actuals:
        print("No actuals.csv data yet -- nothing to compare against.")
        return
    if not predictions:
        print("No predictions.csv data yet -- nothing to compare against.")
        return

    high_errors = defaultdict(list)
    low_errors = defaultdict(list)
    uniform_total = defaultdict(int)
    uniform_wrong = defaultdict(int)
    matched = 0

    for row in predictions:
        actual = actuals.get(row["target_date"])
        if actual is None:
            continue
        matched += 1
        days_ahead = row["days_ahead"]

        high_errors[days_ahead].append(abs(row["predicted_high"] - actual["high"]))
        low_errors[days_ahead].append(abs(row["predicted_low"] - actual["low"]))

        predicted_cold_layer = cold_layer_uniform(row["predicted_low"])
        actual_cold_layer = cold_layer_uniform(actual["low"])
        uniform_total[days_ahead] += 1
        if predicted_cold_layer != actual_cold_layer:
            uniform_wrong[days_ahead] += 1

    if matched == 0:
        print("No target_date overlap between predictions.csv and actuals.csv yet.")
        return

    print(f"Matched {matched} prediction rows against {len(actuals)} actual days.\n")

    print("Mean absolute temp error by days_ahead (lead time):")
    print(f"  {'days_ahead':>10} | {'high MAE':>9} | {'low MAE':>9} | {'n':>4}")
    for days_ahead in sorted(high_errors):
        h = high_errors[days_ahead]
        l = low_errors[days_ahead]
        print(f"  {days_ahead:>10} | {sum(h)/len(h):9.2f} | {sum(l)/len(l):9.2f} | {len(h):>4}")

    print("\nHow often the cold-layer uniform call would have changed vs. the morning-of call:")
    print(f"  {'days_ahead':>10} | {'% wrong':>8} | {'n':>4}")
    for days_ahead in sorted(uniform_total):
        total = uniform_total[days_ahead]
        wrong = uniform_wrong[days_ahead]
        pct = 100.0 * wrong / total
        print(f"  {days_ahead:>10} | {pct:7.1f}% | {total:>4}")


if __name__ == "__main__":
    main()
