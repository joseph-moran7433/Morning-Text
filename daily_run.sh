#!/bin/bash
# Runs the morning advisory, updates the trust score, and pushes anything
# that changed. Meant to be the single cron entry for this repo -- folds
# trust_score.py into the same run as advisory.py instead of a separate
# nightly job, so there's only ever one process touching the git repo
# per day (no collision window to worry about).
set -e
cd /home/math-pi-6/Morning-Text
source venv/bin/activate

NTFY_TOPIC=weather_predictions_for_commander python advisory.py
python trust_score.py

if ! git diff --quiet -- predictions.csv actuals.csv data/trust_score.json 2>/dev/null || \
   [ -n "$(git status --porcelain -- predictions.csv actuals.csv data/trust_score.json)" ]; then
  git add predictions.csv actuals.csv data/trust_score.json
  git commit -m "Daily data sync $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  git push origin main
fi
