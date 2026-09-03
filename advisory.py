"""
advisory.py

Pulls a 7-day forecast for West Point, NY from the National Weather
Service API (api.weather.gov -- free, no API key required), computes
a uniform recommendation / heat category / cold injury risk for each
day, formats it into a short text message, and sends it via an
email-to-SMS gateway.

Run manually:
    python advisory.py

Environment variables required (set as GitHub Actions secrets in
production, or in your own shell/`.env` for local testing):
    EMAIL_FROM          - Gmail address to send FROM
    EMAIL_APP_PASSWORD  - Gmail App Password (NOT your real password --
                           generate one at myaccount.google.com/apppasswords)
    EMAIL_TO             - your carrier's email-to-SMS address,
                           e.g. 5551234567@vtext.com (Verizon),
                           5551234567@txt.att.net (AT&T),
                           5551234567@tmomail.net (T-Mobile)

Optional:
    SMTP_SERVER (default: smtp.gmail.com)
    SMTP_PORT    (default: 587)
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from datetime import datetime

import requests

from heat_category import heat_category
from uniform_chart import uniform_for_temp, cold_risk

# ---- Location: West Point, NY ----
LAT = 41.3900
LON = -73.9639

# NWS API requires a descriptive User-Agent with contact info
HEADERS = {
    "User-Agent": "(morning-text-advisory, class-project-contact@example.com)",
    "Accept": "application/geo+json",
}


def get_forecast_urls(lat, lon):
    """Step 1 of the NWS API: look up the grid endpoint for this lat/lon."""
    url = f"https://api.weather.gov/points/{lat},{lon}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    props = resp.json()["properties"]
    return props["forecast"], props["forecastHourly"]


def get_periods(forecast_url):
    """12-hour day/night periods for the next 7 days."""
    resp = requests.get(forecast_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()["properties"]["periods"]


def get_hourly(forecast_hourly_url):
    """Hourly periods -- used to pull relative humidity."""
    resp = requests.get(forecast_hourly_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()["properties"]["periods"]


def humidity_near(hourly_periods, target_iso_time):
    """
    Find the hourly forecast entry closest to a given time, and return
    its relative humidity. Falls back to 50% if not found (keeps the
    script from crashing if the API shape changes slightly).
    """
    try:
        target = datetime.fromisoformat(target_iso_time)
    except ValueError:
        return 50

    best = None
    best_diff = None
    for hour in hourly_periods:
        try:
            hour_time = datetime.fromisoformat(hour["startTime"])
        except (ValueError, KeyError):
            continue
        diff = abs((hour_time - target).total_seconds())
        if best_diff is None or diff < best_diff:
            best = hour
            best_diff = diff

    if best and "relativeHumidity" in best and best["relativeHumidity"]:
        return best["relativeHumidity"].get("value", 50)
    return 50


def build_daily_summaries(periods, hourly_periods, max_days=7):
    """
    Builds one summary per calendar day from the NWS day/night periods.

    Temp range shown to the user is "overnight low -> daytime high"
    (standard weather-report convention: the low is the night that
    FOLLOWS the day, e.g. "Tue: 34-61" means 61 during Tuesday, dropping
    to 34 Tuesday night).

    But the uniform / cold-injury call is for 0630 PT/formation, which
    happens at the coldest point of the morning -- that's the low from
    the PRECEDING night (periods[i-1]), not the night that follows.
    Heat category is a midday/afternoon risk, so it's driven by the
    day's high temp instead.
    """
    summaries = []
    i = 0
    while i < len(periods) and len(summaries) < max_days:
        period = periods[i]
        if period.get("isDaytime"):
            high_temp = period["temperature"]

            evening_low = None
            if i + 1 < len(periods) and not periods[i + 1].get("isDaytime"):
                evening_low = periods[i + 1]["temperature"]

            morning_low = None
            if i - 1 >= 0 and not periods[i - 1].get("isDaytime"):
                morning_low = periods[i - 1]["temperature"]

            # Range shown to the user; falls back gracefully if either
            # side is missing (e.g. very first or last period).
            display_low = evening_low if evening_low is not None else morning_low

            day_label = period["name"].split()[0][:3]  # "Tuesday" -> "Tue"
            rh = humidity_near(hourly_periods, period["startTime"])

            morning_temp = morning_low if morning_low is not None else high_temp

            uniform = uniform_for_temp(morning_temp)
            risk_level, risk_note = cold_risk(morning_temp)
            heat = heat_category(high_temp, rh) if high_temp >= 76 else None

            summaries.append({
                "day": day_label,
                "high": high_temp,
                "low": display_low,
                "uniform": uniform,
                "cold_risk": risk_level,
                "cold_note": risk_note,
                "heat": heat,
            })
        i += 1
    return summaries


def format_text(summaries):
    """Builds the final SMS body -- one line per day."""
    lines = ["WX/UNIFORM"]
    notable = []

    for s in summaries:
        temp_range = f"{s['low']}-{s['high']}°F" if s["low"] is not None else f"{s['high']}°F"

        if s["heat"]:
            if s["heat"]["flag"] == "none":
                flag = f"Cat {s['heat']['category']}"
            else:
                flag = f"Cat {s['heat']['category']} {s['heat']['flag']}"
            if s["heat"]["category"] >= 3:
                notable.append(f"{s['day']} trending {s['heat']['flag']} — hydrate")
        elif s["cold_risk"] != "Low":
            flag = f"{s['cold_risk']} cold risk"
            notable.append(f"{s['day']}: {s['cold_note']}")
        else:
            flag = "low risk"

        lines.append(f"{s['day']}: {temp_range} | {s['uniform']} | {flag}")

    if notable:
        lines.append("")
        lines.append("Heads up: " + "; ".join(notable))

    return "\n".join(lines)


def send_text(body):
    email_from = os.environ["EMAIL_FROM"]
    app_password = os.environ["EMAIL_APP_PASSWORD"]
    email_to = os.environ["EMAIL_TO"]
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    msg = MIMEText(body)
    msg["From"] = email_from
    msg["To"] = email_to
    msg["Subject"] = ""  # most carrier gateways ignore/strip the subject

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls(context=context)
        server.login(email_from, app_password)
        server.sendmail(email_from, email_to, msg.as_string())


def main():
    forecast_url, forecast_hourly_url = get_forecast_urls(LAT, LON)
    periods = get_periods(forecast_url)
    hourly = get_hourly(forecast_hourly_url)

    summaries = build_daily_summaries(periods, hourly)
    text = format_text(summaries)

    print(text)  # always print -- doubles as the live demo output

    if os.environ.get("EMAIL_FROM"):
        send_text(text)
        print("\n[sent via email-to-SMS]")
    else:
        print("\n[EMAIL_FROM not set -- skipping send, printed only]")


if __name__ == "__main__":
    main()
