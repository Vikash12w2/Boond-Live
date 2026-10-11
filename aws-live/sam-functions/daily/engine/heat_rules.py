from engine.data import get_crop, get_setting


def get_heat_windows(crop="wheat"):
    return get_crop(crop).get("heat_windows", [])


def get_heat_threshold(stage, crop="wheat"):
    return get_crop(crop).get("heat_thresholds", {}).get(stage)


def get_heat_windows_for_day(day_after_sowing, crop="wheat"):
    """
    Return every heat-sensitive window that contains this crop
    day. Windows may overlap (e.g. late flowering and early
    grain filling), so a day can be in more than one.
    """
    return [
        window
        for window in get_heat_windows(crop)
        if window["day_start"] <= day_after_sowing <= window["day_end"]
    ]


def consecutive_hot_days_required(crop="wheat"):
    """
    Hot forecast days in a row needed for HIGH heat risk: crops.json
    heat_consecutive_days, else config heat.consecutive_days_required.
    """
    return get_crop(crop).get(
        "heat_consecutive_days",
        get_setting("heat", "consecutive_days_required")
    )


def get_heat_stage(day_after_sowing, crop="wheat"):
    windows = get_heat_windows_for_day(day_after_sowing, crop)
    return windows[0]["name"] if windows else None


def check_heat_risk(stage, forecast_tmax, crop="wheat"):
    """
    Check whether forecast Tmax exceeds the configured
    heat threshold for a sensitive stage.

    Kept for callers that already know the stage.
    assess_heat_risk() derives the stage from the crop day.
    """

    threshold = get_heat_threshold(stage, crop)

    if threshold is None:
        return {
            "heat_risk": "LOW",
            "stage": stage,
            "threshold_c": None,
            "max_forecast_tmax_c": (
                max(forecast_tmax)
                if forecast_tmax
                else None
            ),
            "reason_code": "STAGE_NOT_HEAT_SENSITIVE"
        }

    if not forecast_tmax:
        return {
            "heat_risk": "UNKNOWN",
            "stage": stage,
            "threshold_c": threshold,
            "max_forecast_tmax_c": None,
            "reason_code": "NO_FORECAST_DATA"
        }

    maximum_temperature = max(forecast_tmax)

    if maximum_temperature >= threshold:
        return {
            "heat_risk": "HIGH",
            "stage": stage,
            "threshold_c": threshold,
            "max_forecast_tmax_c": maximum_temperature,
            "reason_code": "HEAT_THRESHOLD_EXCEEDED"
        }

    return {
        "heat_risk": "LOW",
        "stage": stage,
        "threshold_c": threshold,
        "max_forecast_tmax_c": maximum_temperature,
        "reason_code": "HEAT_THRESHOLD_NOT_EXCEEDED"
    }


def assess_heat_risk(
    first_day_after_sowing,
    forecast_tmax,
    crop="wheat",
    window_days=None,
    consecutive_days_required=None
):
    """
    Check each forecast day against the heat windows for
    that day's own crop day (DATA_GUIDE 4.3).

    forecast_tmax[0] is the forecast for crop day
    first_day_after_sowing. Only the first window_days
    values are used (config heat.forecast_window_days).

    Risk is HIGH when at least consecutive_days_required
    consecutive days reach a threshold of a window they are in:
    the crop's own heat_consecutive_days if crops.json gives one
    (cotton and sugarcane: 2), otherwise config
    heat.consecutive_days_required.
    """

    if window_days is None:
        window_days = get_setting("heat", "forecast_window_days")

    if consecutive_days_required is None:
        consecutive_days_required = consecutive_hot_days_required(crop)

    tmax_window = list(forecast_tmax)[:window_days]

    if not tmax_window:
        return {
            "heat_risk": "UNKNOWN",
            "stage": get_heat_stage(first_day_after_sowing, crop),
            "threshold_c": None,
            "max_forecast_tmax_c": None,
            "hot_days": [],
            "reason_code": "NO_FORECAST_DATA"
        }

    first_sensitive_window = None
    first_hot_window = None
    hot_days = []
    run_length = 0
    longest_run = 0

    for offset, tmax in enumerate(tmax_window):
        day = first_day_after_sowing + offset
        windows = get_heat_windows_for_day(day, crop)

        if windows and first_sensitive_window is None:
            first_sensitive_window = windows[0]

        exceeded = [
            window
            for window in windows
            if tmax is not None and tmax >= window["tmax_threshold_c"]
        ]

        if exceeded:
            hot_days.append(day)
            first_hot_window = first_hot_window or exceeded[0]
            run_length += 1
            longest_run = max(longest_run, run_length)
        else:
            run_length = 0

    known_tmax = [tmax for tmax in tmax_window if tmax is not None]
    maximum_temperature = max(known_tmax) if known_tmax else None

    if first_sensitive_window is None:
        return {
            "heat_risk": "LOW",
            "stage": None,
            "threshold_c": None,
            "max_forecast_tmax_c": maximum_temperature,
            "hot_days": [],
            "reason_code": "STAGE_NOT_HEAT_SENSITIVE"
        }

    reported_window = first_hot_window or first_sensitive_window

    if longest_run >= consecutive_days_required:
        heat_risk = "HIGH"
        reason_code = "HEAT_THRESHOLD_EXCEEDED"
    else:
        heat_risk = "LOW"
        reason_code = "HEAT_THRESHOLD_NOT_EXCEEDED"

    return {
        "heat_risk": heat_risk,
        "stage": reported_window["name"],
        "threshold_c": reported_window["tmax_threshold_c"],
        "max_forecast_tmax_c": maximum_temperature,
        "hot_days": hot_days,
        "reason_code": reason_code
    }
