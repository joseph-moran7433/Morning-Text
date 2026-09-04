"""
stations.py

Finds the nearest real NWS observation station to a lat/lon (dynamically,
via the /points -> observationStations API -- never hardcoded, since the
nearest station can change if NWS adds/retires one), and pulls that
station's actual observed high/low temperature for a given calendar date.

West Point, NY has no dedicated NWS station of its own, so this looks up
whatever real station is currently closest (in practice usually Stewart
Airport / KSWF) at run time.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

LOCAL_TZ = ZoneInfo("America/New_York")


def find_nearest_station(lat, lon, headers, timeout=15):
    """
    Returns the station identifier (e.g. "KSWF") of the nearest real NWS
    observation station to (lat, lon). The /points endpoint's
    observationStations link already returns stations sorted nearest-first.
    """
    points_url = f"https://api.weather.gov/points/{lat},{lon}"
    resp = requests.get(points_url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    stations_url = resp.json()["properties"]["observationStations"]

    resp = requests.get(stations_url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    features = resp.json()["features"]
    if not features:
        raise RuntimeError("No observation stations returned for this location")

    nearest = features[0]
    station_id = nearest["properties"].get("stationIdentifier")
    if not station_id:
        # fall back to parsing it off the station's own URL/id
        station_id = nearest["id"].rstrip("/").split("/")[-1]
    return station_id


def fetch_actual_high_low(station_id, target_date, headers, timeout=15):
    """
    Fetches all observations for `station_id` covering `target_date`
    (a date object, interpreted in America/New_York local time) and
    returns (actual_high_f, actual_low_f) computed from the hourly
    (METAR-derived) temperature readings for that local calendar day.

    Returns (None, None) if no valid temperature observations were found
    (e.g. station was offline that day).
    """
    start_local = datetime.combine(target_date, datetime.min.time(), tzinfo=LOCAL_TZ)
    end_local = start_local + timedelta(days=1)

    url = (
        f"https://api.weather.gov/stations/{station_id}/observations"
        f"?start={start_local.isoformat()}&end={end_local.isoformat()}"
    )
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    features = resp.json()["features"]

    temps_c = []
    for feature in features:
        temp = feature["properties"].get("temperature", {})
        value = temp.get("value")
        if value is not None:
            temps_c.append(value)

    if not temps_c:
        return None, None

    high_f = round(max(temps_c) * 9.0 / 5.0 + 32, 1)
    low_f = round(min(temps_c) * 9.0 / 5.0 + 32, 1)
    return high_f, low_f
