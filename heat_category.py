"""
heat_category.py

Approximates WBGT (Wet Bulb Globe Temperature) from air temperature and
relative humidity, then maps it to the Army's official Heat Category /
Work-Rest / Water Consumption table (U.S. Army Public Health Command).

IMPORTANT CAVEAT (worth mentioning in your presentation):
Real WBGT devices measure a wet-bulb thermometer, a black globe
(solar radiation), and a dry-bulb thermometer. We don't have a solar
radiation reading from a weather API, so this uses a well-known
simplified formula (temp + humidity only). It runs a few degrees low
on sunny days with no cloud cover. A real unit would calibrate this
against an actual WBGT meter -- flagged here as a known limitation,
not hidden.
"""

import math

# Army Public Health Command Heat Category table (WBGT in Fahrenheit)
# (low_f, high_f, category_number, flag_color, easy_work, moderate_work, hard_work)
HEAT_CATEGORY_TABLE = [
    (78.0, 81.9, 1, "none",   "NL",     "NL",     "40/20 min"),
    (82.0, 84.9, 2, "green",  "NL",     "50/10 min", "30/30 min"),
    (85.0, 87.9, 3, "yellow", "NL",     "40/20 min", "30/30 min"),
    (88.0, 89.9, 4, "red",    "NL",     "30/30 min", "20/40 min"),
    (90.0, 999.0, 5, "black", "50/10 min", "20/40 min", "10/50 min"),
]


def fahrenheit_to_celsius(temp_f):
    return (temp_f - 32) * 5.0 / 9.0


def celsius_to_fahrenheit(temp_c):
    return temp_c * 9.0 / 5.0 + 32


def estimate_wbgt_f(temp_f, relative_humidity_pct):
    """
    Simplified WBGT approximation (no solar radiation term).
    Formula: WBGT(C) = 0.567*Ta + 0.393*e + 3.94
      where Ta = air temp (C), e = vapor pressure (hPa)
      e = (RH/100) * 6.105 * exp(17.27*Ta / (237.7+Ta))
    """
    ta = fahrenheit_to_celsius(temp_f)
    rh = max(0, min(100, relative_humidity_pct))
    e = (rh / 100.0) * 6.105 * math.exp((17.27 * ta) / (237.7 + ta))
    wbgt_c = 0.567 * ta + 0.393 * e + 3.94
    return celsius_to_fahrenheit(wbgt_c)


def heat_category(temp_f, relative_humidity_pct):
    """
    Returns a dict with category info, or None if WBGT is below
    Category 1 (i.e. heat isn't a factor).
    """
    wbgt_f = estimate_wbgt_f(temp_f, relative_humidity_pct)

    for low, high, cat_num, color, easy, moderate, hard in HEAT_CATEGORY_TABLE:
        if low <= wbgt_f <= high:
            return {
                "wbgt_f": round(wbgt_f, 1),
                "category": cat_num,
                "flag": color,
                "work_rest_hard": hard,
            }
    if wbgt_f > 90:
        # anything above the table's top bound is still Category 5
        top = HEAT_CATEGORY_TABLE[-1]
        return {
            "wbgt_f": round(wbgt_f, 1),
            "category": top[2],
            "flag": top[3],
            "work_rest_hard": top[6],
        }
    return None  # below 78F WBGT -- heat category not a factor
