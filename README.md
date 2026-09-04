# Morning Text — Formation Weather & Uniform Advisory

Every morning, someone checks the weather and translates it into a uniform
call and a set of safety precautions — reactively, one day at a time. This
project automates that: it pulls a real forecast, runs it through the
Army's actual heat-category and cold-injury thresholds, and pushes a
7-day-ahead advisory to your phone every night, with zero manual effort.
It also logs every prediction it makes and what actually happened, so you
can measure how accurate the forecast was by lead time.

## Sample output

```
WX/UNIFORM
TDY: 79-84°F by 1400 | ACUs, de-bloused, mandatory water breaks | Cat 5 black
Sat: 75-80°F by 1300 | ACUs, de-bloused | Cat 4 black
Sun: 70-75°F by 1300 | ACUs | low risk
Mon: 73-78°F by 1400 | ACUs, sleeves rolled twice, boots unbloused | Cat 3 red
Tue: 53-58°F til 0700, 53-58°F by 1300 | ACUs + jacket | low risk
Wed: 19-24°F til 0800, 51-56°F by 1300 | ACUs + ECWCS parka, gloves, fleece cap | elevated cold risk
Thu: 78-83°F by 1400 | ACUs, de-bloused, mandatory water breaks | Cat 5 black

Heads up: TDY trending black — hydrate; Sat trending black — hydrate; Mon trending red — hydrate; Wed: inspect cold weather clothing; Thu trending black — hydrate
```

Note: the uniform call is always ACU-based, computed from the hourly
forecast restricted to **0500-2330 local time only**. On a day where heat
category is a factor (day high >= 76F), the heat-category ladder governs
the uniform call (Cat 1: no change, Cat 2: sleeves rolled once, Cat 3:
sleeves rolled twice + boots unbloused, Cat 4: de-bloused, Cat 5:
de-bloused + mandatory water breaks). Otherwise, cold-weather layers are
driven by the day's low within that window (jacket → fleece + gloves →
ECWCS parka + gloves + fleece cap → arctic layers) — see
`build_daily_summaries()` in `advisory.py` and `uniform_chart.py`.

Each line always shows the top 5-degree band of the day's high and when
it's reached ("how hot, and when"). It also shows the bottom 5-degree
band of the low and when it clears, but ONLY on days where that low is
actually driving a cold-layer uniform call — if heat governs the day, or
it never gets cold enough to need a layer, that band is left out since it
wouldn't change anything. Weekday labels come from the calendar date (not
the NWS period name, which gets swapped for holiday names like "Labor
Day" and would otherwise garble the label), and today is always TDY.

## What it's built on

- **Weather data:** [National Weather Service API](https://api.weather.gov)
  (`api.weather.gov`) — free, public, no API key required.
- **Heat category logic:** this unit's specified air-temperature
  thresholds (Cat 1 green: below 80°F, Cat 2 yellow: 80–85.9°F, Cat 3
  red: 86–94.9°F, Cat 4 black: 95–99.9°F, Cat 5 black: 100°F+) — see
  `heat_category.py`.
- **Uniform / cold injury logic:** the Army PT Uniform Weather Chart, and
  cold-injury inspection thresholds (25°F: inspect cold weather clothing,
  0°F: inspect for cold injuries).
- **Delivery:** [ntfy](https://ntfy.sh) push notification (or a
  self-hosted ntfy server).
- **Scheduling:** a crontab entry on the Raspberry Pi running this, at
  0530 local time every night.
- **Actual-conditions logging:** the nearest real NWS observation station
  is looked up dynamically each run (West Point has no station of its
  own) via the `/points` → `observationStations` API — never hardcoded.

## Project layout

```
advisory.py               # main script: fetch -> compute -> format -> log -> send
heat_category.py           # air-temp -> heat category table
uniform_chart.py           # temp -> PT uniform mapping + cold risk
stations.py                 # nearest-station lookup + actual high/low fetch
csv_log.py                  # predictions.csv / actuals.csv append helpers
accuracy_report.py          # joins predictions.csv + actuals.csv, prints MAE by lead time
predictions.csv             # one row per (run, target_date) -- every forecast ever made
actuals.csv                 # one row per calendar date -- what actually happened
requirements.txt
```

## Setup (on the Raspberry Pi)

### 1. Pick an ntfy topic and subscribe to it on your phone
Install the [ntfy app](https://ntfy.sh/app) (iOS/Android) and subscribe to
a topic name only you know (ntfy.sh topics are public by default — anyone
who knows the exact name can read/post to it, so don't use something
guessable like `weather`).

### 2. Create the venv and install dependencies
```bash
cd ~/Morning-Text
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### 3. Set NTFY_TOPIC and run it once manually
```bash
export NTFY_TOPIC=your-topic-name
venv/bin/python advisory.py
```
Confirm the digest prints AND a push notification lands on your phone.

### 4. Install the crontab entry
Runs every night at 5:30am, with NTFY_TOPIC set inline so cron's minimal
environment doesn't need a separate env file:
```
30 5 * * * cd ~/Morning-Text && NTFY_TOPIC=your-topic-name venv/bin/python advisory.py >> ~/morning-text.log 2>&1
```

### 5. Check prediction accuracy any time
```bash
venv/bin/python accuracy_report.py
```
This joins `predictions.csv` to `actuals.csv` and prints mean absolute
temperature error broken out by days_ahead (0 = morning-of, 6 = a full
week out), plus how often the uniform call would have changed if made
days ahead instead of the morning of.

## Known limitations (good talking points for the presentation)

- Heat category here is driven by air temperature only, per this unit's
  specified thresholds — not the DoD's official WBGT-based table (which
  factors in humidity and solar radiation and would need a physical
  sensor a weather API can't provide).
- Uniform temperature bands are a reasonable approximation, not a
  copy of any one unit's exact SOP.
- `actual_low` in `actuals.csv` is the calendar day's minimum observed
  temperature (from the nearest real station), used as the closest
  available proxy for the specific 0630 PT low — not a direct 0630 reading.
- Cron's schedule is fixed local time and doesn't need a DST adjustment
  (unlike GitHub Actions' UTC-only cron), since it runs on the Pi's own
  local clock.
