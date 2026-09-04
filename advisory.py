"""
advisory.py

Pulls an hourly forecast for West Point, NY from the National Weather
Service API (api.weather.gov -- free, no API key required), computes
a uniform recommendation / heat category / cold injury risk for each
of the next 7 days, formats it into a short text digest, sends it as a
push notification via ntfy, and logs the predictions (and, before that,
yesterday's actual observed high/low) to CSV for later accuracy checks.

Only hours from 0500-2330 local time count toward each day's high/low --
outside that window isn't relevant to PT/formation or daytime training.

Run manually:
    python advisory.py

Environment variables required:
    NTFY_TOPIC   - the ntfy topic to publish to (required, no default --
                   pick something unguessable, ntfy.sh topics are public)

Optional:
    NTFY_SERVER  - defaults to https://ntfy.sh (set this if self-hosting)
"""

import os
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from heat_category import heat_category
from uniform_chart import cold_layer_uniform, heat_modifier_uniform, cold_risk
from stations import find_nearest_station, fetch_actual_high_low
from csv_log import append_predictions, append_actual

# ---- Location: West Point, NY ----
LAT = 41.3900
LON = -73.9639
LOCAL_TZ = ZoneInfo("America/New_York")

# Only these local hours count toward a day's high/low -- 0500-2330.
WINDOW_START_HOUR = 5
WINDOW_END_HOUR = 23

# Band width (F) for the "how hot/cold, and when" callouts.
BAND_WIDTH = 5

# NWS API requires a descriptive User-Agent with contact info
HEADERS = {
    "User-Agent": "(morning-text-advisory, jwmoran7@optonline.net)",
    "Accept": "application/geo+json",
}


def get_forecast_hourly_url(lat, lon):
    """Step 1 of the NWS API: look up the hourly forecast endpoint for this lat/lon."""
    url = f"https://api.weather.gov/points/{lat},{lon}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()["properties"]["forecastHourly"]


def get_hourly(forecast_hourly_url):
    resp = requests.get(forecast_hourly_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()["properties"]["periods"]


def hours_by_date(hourly_periods):
    """
    Groups hourly forecast entries by local calendar date, keeping only
    the 0500-2330 window, sorted chronologically within each date.
    Each entry is (local_dt, temp_f).
    """
    by_date = defaultdict(list)
    for p in hourly_periods:
        try:
            dt = datetime.fromisoformat(p["startTime"]).astimezone(LOCAL_TZ)
        except (ValueError, KeyError):
            continue
        if not (WINDOW_START_HOUR <= dt.hour <= WINDOW_END_HOUR):
            continue
        temp = p.get("temperature")
        if temp is None:
            continue
        by_date[dt.strftime("%Y-%m-%d")].append((dt, temp))

    for date_str in by_date:
        by_date[date_str].sort(key=lambda entry: entry[0])
    return by_date


def band_around(hours, extreme_index, is_high):
    """
    Given the sorted (dt, temp) list and the index of its high/low,
    extends outward from that index while still within BAND_WIDTH of the
    extreme, and returns the boundary datetime "on the way in" -- i.e.
    the earliest time it's within band of the high, or the latest time
    it's still within band of the low.
    """
    extreme_temp = hours[extreme_index][1]
    if is_high:
        i = extreme_index
        while i - 1 >= 0 and hours[i - 1][1] >= extreme_temp - BAND_WIDTH:
            i -= 1
        return hours[i][0]
    else:
        i = extreme_index
        while i + 1 < len(hours) and hours[i + 1][1] <= extreme_temp + BAND_WIDTH:
            i += 1
        return hours[i][0]


def build_daily_summaries(hourly_periods, max_days=7):
    """
    Builds one summary per calendar date (today + next 6) from the hourly
    forecast, using only the 0500-2330 window.

    The uniform call is ACU-based:
      - If the day's high (within the window) is >= 76F, heat category is
        computed and the heat-category uniform ladder governs the call
        (see uniform_chart.HEAT_CATEGORY_UNIFORM).
      - Otherwise, cold-weather layers are driven by the day's low
        (within the window) -- this stands in for the 0630 PT/formation
        temperature, since 0500 is the start of the window and the
        coldest part of the day happens at or shortly after it.

    Rather than showing the full day's low-high range, each line shows
    the top BAND_WIDTH-degree band of the high and when it's reached
    (always -- "how hot, and when" is generally useful info), and the
    bottom BAND_WIDTH-degree band of the low and when it clears, but
    ONLY when that low is what's actually driving a cold-layer uniform
    call -- on a day where heat governs the uniform, or where it never
    gets cold enough to need a layer, the bottom band doesn't change
    anything and is left out.
    """
    by_date = hours_by_date(hourly_periods)
    dates = sorted(by_date.keys())[:max_days]

    summaries = []
    for idx, date_str in enumerate(dates):
        hours = by_date[date_str]
        if not hours:
            continue

        high_idx = max(range(len(hours)), key=lambda i: hours[i][1])
        low_idx = min(range(len(hours)), key=lambda i: hours[i][1])
        day_high = hours[high_idx][1]
        day_low = hours[low_idx][1]

        peak_band_start = band_around(hours, high_idx, is_high=True)
        low_band_end = band_around(hours, low_idx, is_high=False)

        day_label = "TDY" if idx == 0 else datetime.strptime(date_str, "%Y-%m-%d").strftime("%a")

        heat = heat_category(day_high) if day_high >= 76 else None
        cold_uniform = cold_layer_uniform(day_low)
        risk_level, risk_note = cold_risk(day_low)

        if heat:
            uniform = heat_modifier_uniform(heat)
            show_bottom_band = False
        else:
            uniform = cold_uniform
            show_bottom_band = cold_uniform != "ACUs"

        top_desc = f"{day_high - BAND_WIDTH:.0f}-{day_high:.0f}°F by {peak_band_start:%H%M}"
        if show_bottom_band:
            bottom_desc = f"{day_low:.0f}-{day_low + BAND_WIDTH:.0f}°F til {low_band_end:%H%M}"
            temp_desc = f"{bottom_desc}, {top_desc}"
        else:
            temp_desc = top_desc

        summaries.append({
            "day": day_label,
            "target_date": date_str,
            "high": day_high,
            "low": day_low,
            "temp_desc": temp_desc,
            "uniform": uniform,
            "cold_risk": risk_level,
            "cold_note": risk_note,
            "heat": heat,
        })
    return summaries


def format_text(summaries):
    """Builds the final push-notification body -- one line per day."""
    lines = ["WX/UNIFORM"]
    notable = []

    for s in summaries:
        if s["heat"]:
            flag = f"Cat {s['heat']['category']} {s['heat']['flag']}"
            if s["heat"]["category"] >= 3:
                notable.append(f"{s['day']} trending {s['heat']['flag']} — hydrate")
        elif s["cold_risk"] != "normal":
            flag = f"{s['cold_risk']} cold risk"
            notable.append(f"{s['day']}: {s['cold_note']}")
        else:
            flag = "low risk"

        lines.append(f"{s['day']}: {s['temp_desc']} | {s['uniform']} | {flag}")

    if notable:
        lines.append("")
        lines.append("Heads up: " + "; ".join(notable))

    return "\n".join(lines)


def send_ntfy(body):
    topic = os.environ["NTFY_TOPIC"]
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")

    resp = requests.post(
        f"{server}/{topic}",
        data=body.encode("utf-8"),
        headers={
            "Title": "Morning Text - WX/Uniform",
            "Priority": "default",
        },
        timeout=15,
    )
    resp.raise_for_status()


def log_yesterdays_actual():
    """Looks up the nearest real observation station and logs yesterday's
    actual observed high/low before generating tonight's forecast."""
    yesterday = datetime.now(LOCAL_TZ).date() - timedelta(days=1)
    try:
        station_id = find_nearest_station(LAT, LON, HEADERS)
        actual_high, actual_low = fetch_actual_high_low(station_id, yesterday, HEADERS)
    except (requests.RequestException, RuntimeError, KeyError) as exc:
        print(f"[actuals] could not fetch yesterday's observations: {exc}")
        return

    if actual_high is None:
        print(f"[actuals] no observations found for {yesterday} at station")
        return

    logged = append_actual(yesterday.isoformat(), actual_high, actual_low, station_id)
    if logged:
        print(f"[actuals] logged {yesterday}: {actual_low}-{actual_high}°F ({station_id})")
    else:
        print(f"[actuals] {yesterday} already logged, skipping")


def main():
    log_yesterdays_actual()

    forecast_hourly_url = get_forecast_hourly_url(LAT, LON)
    hourly = get_hourly(forecast_hourly_url)

    summaries = build_daily_summaries(hourly)
    text = format_text(summaries)

    print(text)  # always print -- doubles as the live demo output

    run_timestamp = datetime.now(LOCAL_TZ).isoformat()
    append_predictions(run_timestamp, summaries)
    print(f"\n[predictions] logged {len(summaries)} days for run {run_timestamp}")

    if os.environ.get("NTFY_TOPIC"):
        send_ntfy(text)
        print("[sent via ntfy]")
    else:
        print("[NTFY_TOPIC not set -- skipping send, printed only]")


if __name__ == "__main__":
    main()
