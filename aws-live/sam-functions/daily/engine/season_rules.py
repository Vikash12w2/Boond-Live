"""
Calendar rules that a soil-water balance cannot see.

- Recommended sowing / transplanting / planting window
  (crops.json sowing_window, transplant_window or planting_window).
  A date outside it gives a warning; the advice itself is unchanged.
- The last irrigation before harvest (crops.json stop_irrigation for
  upland crops, paddy_water.stop_irrigation_day for paddy). After it,
  decide_today returns WAIT with reason IRRIGATION_STOPPED, and no
  heat irrigation is advised either.

All windows are "MM-DD" strings. A window whose end comes before its
start in the calendar (e.g. 12-15 to 01-10) runs over the new year.
"""

from datetime import date, timedelta

from engine.data import get_crop, is_paddy


WINDOW_KEYS = (
    ("sowing_window", "sowing"),
    ("transplant_window", "transplanting"),
    ("planting_window", "planting"),
)


def _as_date(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


def month_day(text):
    """'03-31' -> (3, 31). Raises ValueError for an impossible date."""
    month, day = (int(part) for part in text.split("-"))
    date(2001, month, day)  # validates; 02-29 is not allowed
    return month, day


def on_or_after(start, text):
    """The first date on or after `start` that falls on MM-DD `text`."""
    month, day = month_day(text)
    candidate = date(start.year, month, day)

    return candidate if candidate >= start else date(start.year + 1, month, day)


def on_or_before(end, text):
    """The last date on or before `end` that falls on MM-DD `text`."""
    month, day = month_day(text)
    candidate = date(end.year, month, day)

    return candidate if candidate <= end else date(end.year - 1, month, day)


# ---------------------------------------------------------------------------
# Sowing window
# ---------------------------------------------------------------------------

def recommended_window(crop):
    """(kind, {"start", "end"}) for the crop, or (None, None)."""
    profile = get_crop(crop)

    for key, kind in WINDOW_KEYS:
        if profile.get(key):
            return kind, profile[key]

    return None, None


def window_position(on_date, start, end):
    """
    Where `on_date` falls relative to the MM-DD window start..end.

    Returns (position, days_outside, window_start, window_end) with
    position INSIDE, EARLY or LATE and the window instance (dates)
    nearest to on_date.
    """
    on_date = _as_date(on_date)
    start_md, end_md = month_day(start), month_day(end)
    best = None

    for year in (on_date.year - 1, on_date.year, on_date.year + 1):
        first = date(year, *start_md)
        last = date(year if end_md >= start_md else year + 1, *end_md)

        if first <= on_date <= last:
            return "INSIDE", 0, first, last

        if on_date < first:
            candidate = ((first - on_date).days, "EARLY", first, last)
        else:
            candidate = ((on_date - last).days, "LATE", first, last)

        if best is None or candidate[0] < best[0]:
            best = candidate

    days, position, first, last = best
    return position, days, first, last


def check_sowing_window(crop, sowing_date):
    """
    Compare the sowing (transplanting, planting) date with the crop's
    recommended window. Returns None if the profile has no window,
    otherwise {"kind", "position", "days_outside", "window_start",
    "window_end", "warning"}; warning is None inside the window and
    SOWN_BEFORE_WINDOW or SOWN_AFTER_WINDOW outside it.
    """
    kind, window = recommended_window(crop)

    if window is None:
        return None

    position, days, first, last = window_position(sowing_date, window["start"], window["end"])

    warning = {
        "INSIDE": None,
        "EARLY": "SOWN_BEFORE_WINDOW",
        "LATE": "SOWN_AFTER_WINDOW",
    }[position]

    return {
        "kind": kind,
        "position": position,
        "days_outside": days,
        "window_start": first.isoformat(),
        "window_end": last.isoformat(),
        "warning": warning
    }


# ---------------------------------------------------------------------------
# Last irrigation before harvest
# ---------------------------------------------------------------------------

def last_irrigation(crop, sowing_date, calendar_dates=True):
    """
    The last day on which Boond may advise irrigation, or None if
    the crop has no stop rule.

    Returns {"date", "day_after_sowing", "rule"}; irrigation is
    stopped on every later day. When a profile has both a calendar
    date and days_before_harvest, the earlier one applies.

    calendar_dates=False ignores the calendar-date rules (for callers
    that only know the crop day, not the real sowing date).
    """
    profile = get_crop(crop)
    sowing = _as_date(sowing_date)
    candidates = []

    if is_paddy(crop):
        stop_day = profile["paddy_water"]["stop_irrigation_day"]
        candidates.append((sowing + timedelta(days=stop_day - 1), "paddy_water.stop_irrigation_day"))

    rule = profile.get("stop_irrigation") or {}

    if calendar_dates and "last_irrigation_date" in rule:
        last = on_or_after(sowing, rule["last_irrigation_date"])
        later = rule.get("if_sown_after")
        label = "last_irrigation_date"

        # Sown after the cut-off date of the same season: a later
        # last irrigation (PAU wheat: sown after 5 Dec -> 10 April).
        if later and sowing > on_or_before(last, later["date"]):
            last = on_or_after(sowing, later["last_irrigation_date"])
            label = "if_sown_after"

        candidates.append((last, label))

    if "days_before_harvest" in rule:
        last_day = profile["total_days"] - rule["days_before_harvest"]
        candidates.append((sowing + timedelta(days=last_day - 1), "days_before_harvest"))

    if not candidates:
        return None

    last, label = min(candidates)

    return {
        "date": last.isoformat(),
        "day_after_sowing": (last - sowing).days + 1,
        "rule": label
    }


def irrigation_stopped(crop, sowing_date, day_after_sowing):
    """True when day_after_sowing is after the crop's last irrigation day."""
    last = last_irrigation(crop, sowing_date)
    return last is not None and day_after_sowing > last["day_after_sowing"]
