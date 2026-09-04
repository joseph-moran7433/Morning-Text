"""
heat_category.py

Maps the day's high temperature (air temp, within the 0500-2330 window)
to a heat category, using this unit's specified thresholds:

    Cat 1 (green)  - below 80F
    Cat 2 (yellow) - 80-85.9F
    Cat 3 (red)    - 86-94.9F
    Cat 4 (black)  - 95-99.9F
    Cat 5 (black)  - 100F and above

Only called when the day's high is >= 76F (see advisory.py) -- heat
isn't tracked as a factor below that.
"""

# (low_f, high_f, category_number, flag_color)
HEAT_CATEGORY_TABLE = [
    (-999.0, 79.9, 1, "green"),
    (80.0, 85.9, 2, "yellow"),
    (86.0, 94.9, 3, "red"),
    (95.0, 99.9, 4, "black"),
    (100.0, 999.0, 5, "black"),
]


def heat_category(temp_f):
    for low, high, cat_num, color in HEAT_CATEGORY_TABLE:
        if low <= temp_f <= high:
            return {"category": cat_num, "flag": color}
    return None  # unreachable -- table covers the full range
