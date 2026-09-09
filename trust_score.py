"""
trust_score.py

Reads predictions.csv / actuals.csv (same files accuracy_report.py already
reads) and writes data/trust_score.json: per-lead-day (days_ahead 0-6)
accuracy stats, plus a single headline trust score for the website.

Reuses accuracy_report.py's own load_actuals()/load_predictions() and
uniform_chart.cold_layer_uniform() rather than re-deriving the join or the
uniform comparison, so this can never drift from what `python
accuracy_report.py` reports on the command line.

NOTE ON THE COMPOSITE FORMULA: the site's original request specified an
exact composite formula and JSON schema, but that detail didn't survive
context compaction on the Claude Code side -- what follows is a reasonable
formula built from the same two signals accuracy_report.py already prints
(temperature MAE and uniform-call correctness), weighted 60/40 toward
temperature accuracy since that's the more information-dense signal at low
sample sizes. Treat this as a first draft to tune once real numbers exist,
not as a locked-in spec.

Run manually:
    python trust_score.py
Intended to run daily right after advisory.py (same cron job, chained) --
see the crontab entry on this Pi.
"""

import json
import os
from collections import defaultdict
from datetime import datetime, timezone

from accuracy_report import load_actuals, load_predictions
from uniform_chart import cold_layer_uniform

OUT_PATH = os.path.join("data", "trust_score.json")

# Below this many total distinct actuals-days logged, the whole score is
# "still warming up" -- not enough history yet for ANY lead day to mean
# much, headline included.
WARMING_UP_DAYS = 14

# Below this many matched samples for a given lead day specifically, that
# day's stats are shown but flagged insufficient rather than trusted.
MIN_SAMPLES_PER_DAY = 5

# MAE (°F) treated as "0% accurate" when converting error into a 0-1 score.
# A 0°F MAE = perfect (1.0); MAE_FLOOR or worse = 0.0; linear in between.
MAE_FLOOR = 10.0


def temp_accuracy(mae):
    return max(0.0, 1.0 - (mae / MAE_FLOOR))


def main():
    actuals = load_actuals()
    predictions = load_predictions()

    by_day = {d: {"high_errors": [], "low_errors": [], "uniform_wrong": 0, "uniform_total": 0} for d in range(7)}

    for row in predictions:
        actual = actuals.get(row["target_date"])
        days_ahead = row["days_ahead"]
        if actual is None or days_ahead not in by_day:
            continue
        bucket = by_day[days_ahead]
        bucket["high_errors"].append(abs(row["predicted_high"] - actual["high"]))
        bucket["low_errors"].append(abs(row["predicted_low"] - actual["low"]))

        predicted_cold_layer = cold_layer_uniform(row["predicted_low"])
        actual_cold_layer = cold_layer_uniform(actual["low"])
        bucket["uniform_total"] += 1
        if predicted_cold_layer != actual_cold_layer:
            bucket["uniform_wrong"] += 1

    by_lead_day = []
    day_scores = []
    for days_ahead in range(7):
        b = by_day[days_ahead]
        n = len(b["high_errors"])
        insufficient = n < MIN_SAMPLES_PER_DAY

        entry = {
            "days_ahead": days_ahead,
            "n": n,
            "insufficient_data": insufficient,
            "high_mae": round(sum(b["high_errors"]) / n, 2) if n else None,
            "low_mae": round(sum(b["low_errors"]) / n, 2) if n else None,
            "uniform_wrong_pct": round(100.0 * b["uniform_wrong"] / b["uniform_total"], 1) if b["uniform_total"] else None,
        }
        by_lead_day.append(entry)

        if not insufficient:
            avg_mae = (entry["high_mae"] + entry["low_mae"]) / 2
            t_acc = temp_accuracy(avg_mae)
            u_acc = 1.0 - (b["uniform_wrong"] / b["uniform_total"])
            day_scores.append(0.6 * t_acc + 0.4 * u_acc)

    days_logged = len(actuals)
    warming_up = days_logged < WARMING_UP_DAYS

    trust_score = None
    if not warming_up and day_scores:
        trust_score = round(100 * sum(day_scores) / len(day_scores))

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days_logged": days_logged,
        "warming_up": warming_up,
        "warming_up_threshold_days": WARMING_UP_DAYS,
        "trust_score": trust_score,
        "by_lead_day": by_lead_day,
    }

    os.makedirs("data", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
        f.write("\n")

    print(f"Wrote {OUT_PATH}: days_logged={days_logged} warming_up={warming_up} trust_score={trust_score}")


if __name__ == "__main__":
    main()
