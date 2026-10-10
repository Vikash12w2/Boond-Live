"""
Growth-stage irrigations that a soil-water balance cannot trigger.

Wheat crown root initiation (CRI): PAU asks for a light first
irrigation 3 weeks after sowing (October sowing) or 4 weeks (later
sowing). With the root zone full after the pre-sowing irrigation, the
FAO-56 balance alone would wait until RAW is reached, which in a dry
winter can be months later (2021-22 Ludhiana replay: day 115).

The rule lives in crops.json under "critical_irrigation"; crops
without that block are not affected.
"""

from datetime import date

from engine.data import get_crop


def critical_irrigation_due(crop, day_after_sowing, water_since_sowing_mm, sowing_date=None):
    """
    Return the critical irrigation that is due on this crop day, or None.

    water_since_sowing_mm is the effective rain plus irrigation that has
    reached the field since sowing (not counting the pre-sowing
    irrigation). If it is None the caller does not track it, and the
    rule is skipped.

    Returns {"name", "needed_mm", "depth_mm", "last_day"}.
    """
    spec = get_crop(crop).get("critical_irrigation")

    if not spec or water_since_sowing_mm is None:
        return None

    if isinstance(sowing_date, str):
        sowing_date = date.fromisoformat(sowing_date)

    if sowing_date is not None and sowing_date.month == 10:
        first_day = spec["day_if_sown_in_october"]
    else:
        first_day = spec["day_if_sown_later"]

    last_day = first_day + spec["window_days"] - 1

    if not first_day <= day_after_sowing <= last_day:
        return None

    threshold = spec["skip_if_water_since_sowing_mm"]

    if water_since_sowing_mm >= threshold:
        return None

    return {
        "name": spec["name"],
        "needed_mm": threshold - water_since_sowing_mm,
        "depth_mm": spec["depth_mm"],
        "last_day": last_day
    }
