"""
uniform_chart.py

Maps conditions to a PT/formation uniform call and cold-injury risk
level. The base uniform is always ACUs. On a day where heat category is
a factor (day high >= 76F), the heat-category ladder below governs the
uniform call. Otherwise, the uniform call is driven by cold-weather
layers added for a cold 0630 morning low.

Cold layer thresholds are based on the Army PT/cold weather guidance and
cold-injury inspection thresholds (25F and below: inspect cold weather
clothing, 0F and below: inspect for cold injuries).

Heat-category uniform ladder (as specified for this unit):
    Cat 1 (green)  - no modification
    Cat 2 (yellow) - sleeves rolled once
    Cat 3 (red)    - sleeves rolled twice, boots unbloused
    Cat 4 (black)  - de-bloused
    Cat 5 (black)  - de-bloused, mandatory water breaks
"""

# (low_f, high_f, layer_note)
COLD_LAYER_BANDS = [
    (40, 59, "jacket"),
    (25, 39, "fleece jacket, gloves"),
    (0, 24, "ECWCS parka, gloves, fleece cap"),
    (-999, -1, "ECWCS parka & bibs, arctic mittens, balaclava"),
]

HEAT_CATEGORY_UNIFORM = {
    1: "ACUs",
    2: "ACUs, sleeves rolled once",
    3: "ACUs, sleeves rolled twice, boots unbloused",
    4: "ACUs, de-bloused",
    5: "ACUs, de-bloused, mandatory water breaks",
}


def cold_layer_uniform(temp_f):
    """
    Returns the ACU-based uniform call driven purely by the morning low
    (the 0630 PT/formation temperature) -- "ACUs" alone above 59F, or
    "ACUs + <layer note>" for colder mornings.
    """
    for low, high, layer_note in COLD_LAYER_BANDS:
        if low <= temp_f <= high:
            return f"ACUs + {layer_note}"
    return "ACUs"  # 60F and above -- no extra layer needed


def heat_modifier_uniform(heat):
    """
    Returns the heat-category-driven uniform call, or None if heat isn't
    a factor that day (heat is None -- day high was below 76F).
    """
    if not heat:
        return None
    return HEAT_CATEGORY_UNIFORM.get(heat["category"], "ACUs")


def cold_risk(temp_f):
    """
    Returns a (risk_level, note) tuple.
    Thresholds from Army cold injury prevention guidance:
      - 0F and below: "high" cold injury risk -- leaders inspect personnel
        for cold injuries
      - 25F and below: "elevated" cold injury risk -- leaders inspect for
        proper cold weather clothing
      - above 25F: "normal" -- not a factor
    """
    if temp_f <= 0:
        return ("high", "inspect for cold injuries")
    elif temp_f <= 25:
        return ("elevated", "inspect cold weather clothing")
    else:
        return ("normal", None)
