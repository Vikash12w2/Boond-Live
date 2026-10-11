"""
Convert farmer check-ins into millimetres (DATA_GUIDE 4.5).

    WATERED light / normal / heavy  -> crops[profile].irrigation.checkin_depth_mm
                                       (fallback config.checkin.watered_mm_default)
    RAIN    little / moderate / heavy -> config.checkin.rain_mm

Store the farmer's words and the assumed mm on the EVENT item.
"""

from engine.data import get_crop, get_setting


def watered_mm(level, crop="wheat"):
    level = level.lower()
    depths = get_crop(crop).get("irrigation", {}).get("checkin_depth_mm")

    if not depths:
        depths = get_setting("checkin", "watered_mm_default")

    if level not in depths:
        raise ValueError(f"Unknown watering level: {level}")

    return float(depths[level])


def rain_mm(level):
    level = level.lower()
    amounts = get_setting("checkin", "rain_mm")

    if level not in amounts:
        raise ValueError(f"Unknown rain level: {level}")

    return float(amounts[level])


def make_event(event_type, level, on_date, crop="wheat"):
    """
    The EVENT item to store for a check-in (spec 10.1): the farmer's
    choice verbatim plus the millimetres assumed at that time, so a
    later change to config.json does not rewrite history.
    """
    event_type = event_type.upper()

    if event_type == "WATERED":
        mm = watered_mm(level, crop)
    elif event_type == "RAIN":
        mm = rain_mm(level)
    else:
        raise ValueError(f"Unknown check-in type: {event_type}")

    return {
        "date": str(on_date),
        "type": event_type,
        "choice": level,
        "level": level.lower(),
        "mm_assumed": mm
    }


def _event_mm(event, crop):
    if event.get("mm_assumed") is not None:
        return float(event["mm_assumed"])

    if event["type"].upper() == "RAIN":
        return rain_mm(event["level"])

    return watered_mm(event["level"], crop)


def apply_checkins(gridded_rain_mm, events, crop="wheat"):
    """
    Return (rain_mm, irrigation_mm) for one day.

    events is a list of {"type": "WATERED" | "RAIN", "level": ...,
    "mm_assumed": optional} for that day; a stored mm_assumed wins
    over the level. A RAIN check-in replaces the gridded rain
    rather than adding to it, so the same rain is not counted
    twice. If there are several RAIN check-ins, the largest wins.
    WATERED check-ins add up.
    """
    rain = gridded_rain_mm
    reported_rain = [
        _event_mm(event, crop)
        for event in events
        if event["type"].upper() == "RAIN"
    ]

    if reported_rain:
        rain = max(reported_rain)

    irrigation = sum(
        _event_mm(event, crop)
        for event in events
        if event["type"].upper() == "WATERED"
    )

    return rain, irrigation
