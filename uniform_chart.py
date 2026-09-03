"""
uniform_chart.py

Maps temperature to PT uniform recommendation and cold-injury risk level,
based on the Army PT Uniform Weather Chart and cold weather injury
prevention guidance (leaders inspect for cold weather clothing at 25F
and below, inspect for cold injuries at 0F and below).

These band cutoffs are a reasonable approximation for a class project --
real units often have a local SOP with slightly different numbers.
"""

# (low_f, high_f, short_label, full_description)
UNIFORM_BANDS = [
    (76, 999, "shorts+tee", "shorts + t-shirt"),
    (60, 75, "std IPFU", "standard IPFU (shorts + t-shirt, jacket optional)"),
    (40, 59, "IPFU+jacket", "IPFU pants + jacket"),
    (25, 39, "IPFU+fleece/gloves", "IPFU + fleece cap + gloves"),
    (0, 24, "+balaclava/ECWCS", "IPFU + fleece cap + gloves + balaclava, ECWCS layer"),
    (-999, -1, "full ECWCS/arctic", "full ECWCS + arctic mittens + balaclava"),
]


def uniform_for_temp(temp_f, short=True):
    for low, high, short_label, full_description in UNIFORM_BANDS:
        if low <= temp_f <= high:
            return short_label if short else full_description
    return "std IPFU"  # fallback, shouldn't hit


def cold_risk(temp_f):
    """
    Returns a (risk_level, note) tuple.
    Thresholds from Army cold injury prevention guidance:
      - 25F and below: leaders inspect for proper cold weather clothing
      - 0F and below: leaders inspect personnel for cold injuries
    """
    if temp_f <= 0:
        return ("High", "inspect for cold injuries")
    elif temp_f <= 25:
        return ("Moderate", "inspect cold weather clothing")
    else:
        return ("Low", None)
