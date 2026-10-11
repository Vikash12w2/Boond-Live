from engine.data import get_setting
from engine.water_balance import calculate_ks, effective_rainfall


def predict_depletion(current_depletion, daily_etc_values, daily_rain_values):
    """
    Legacy/simple forecast helper.

    current_depletion is the depletion at the end of today.
    The first forecast value represents tomorrow.

    This function is retained for compatibility with existing tests.
    The production advisor should use forecast_water_balance().
    """
    if len(daily_etc_values) != len(daily_rain_values):
        raise ValueError("daily_etc_values and daily_rain_values must have equal lengths")

    depletion = current_depletion
    predictions = []

    for etc, rain in zip(daily_etc_values, daily_rain_values):
        depletion = depletion + etc - rain
        predictions.append(depletion)

    return predictions


def find_raw_crossing_day(current_depletion, raw, daily_etc_values):
    """
    Legacy/simple RAW crossing helper.

    current_depletion is the depletion at the end of today.
    daily_etc_values[0] represents tomorrow.
    """
    depletion = current_depletion

    for i, etc in enumerate(daily_etc_values):
        depletion = depletion + etc

        if depletion >= raw:
            return i + 1

    return None


def find_raw_crossing_day_from_forecast(forecast_balances):
    """
    Find the first forecast day on which depletion reaches
    or exceeds that day's RAW.

    forecast_balances must be the output of
    forecast_water_balance().
    """

    for index, balance in enumerate(forecast_balances, start=1):
        if balance["depletion_mm"] >= balance["raw_mm"]:
            return index

    return None


def normalise_probabilities(rain_probability, days):
    """
    Accept one probability for every day, a per-day list
    (the Open-Meteo format) or None, and return a list
    with one value per forecast day.
    """
    if rain_probability is None or isinstance(rain_probability, (int, float)):
        return [rain_probability] * days

    probabilities = list(rain_probability)

    if len(probabilities) != days:
        raise ValueError(
            "rain_probability must have one value per forecast day"
        )

    return probabilities


def is_confident(probability, threshold):
    """
    Rain is trusted only when its probability reaches the
    threshold. A missing (None) probability is not trusted.
    """
    return probability is not None and probability >= threshold


def confident_rain_total(future_rain, rain_probability, threshold):
    probabilities = normalise_probabilities(rain_probability, len(future_rain))

    return sum(
        rain
        for rain, probability in zip(future_rain, probabilities)
        if is_confident(probability, threshold)
    )


def _step_depletion(depletion, potential_etc, rain, taw, p):
    """
    One forecast day of the root-zone balance for a single
    rain scenario. Ks is recomputed from this scenario's own
    depletion, and depletion stays within [0, TAW].
    """
    if taw is None or p is None:
        ks = 1.0
    else:
        ks = calculate_ks(depletion, taw, p)

    depletion = max(0.0, depletion + potential_etc * ks - rain)

    if taw is not None:
        depletion = min(taw, depletion)

    return depletion


def _find_crossings(forecast_balances, future_rain, probabilities, threshold):
    """
    Simulate two scenarios over the forecast:
        1. No rain occurs.
        2. Only rain at or above the probability threshold occurs,
           multiplied by config rain.forecast_rain_discount.

    Return the first day each scenario reaches RAW.
    """
    discount = get_setting("rain", "forecast_rain_discount")

    depletion_without_rain = forecast_balances[0]["previous_depletion_mm"]
    depletion_with_trusted_rain = depletion_without_rain

    crossing_without_rain = None
    crossing_with_trusted_rain = None

    for day, (balance, rainfall, probability) in enumerate(
        zip(forecast_balances, future_rain, probabilities),
        start=1
    ):
        # Rows from forecast_water_balance() carry potential ETc,
        # TAW, p and ET0. Simple rows carry only actual_etc_mm.
        potential_etc = balance.get("potential_etc_mm", balance["actual_etc_mm"])
        taw = balance.get("taw_mm")
        p = balance.get("p")
        et0 = balance.get("et0_mm")

        trusted_rain = rainfall * discount if is_confident(probability, threshold) else 0.0

        if et0 is not None:
            trusted_rain = effective_rainfall(trusted_rain, et0)

        depletion_without_rain = _step_depletion(
            depletion_without_rain, potential_etc, 0.0, taw, p
        )
        depletion_with_trusted_rain = _step_depletion(
            depletion_with_trusted_rain, potential_etc, trusted_rain, taw, p
        )

        raw = balance["raw_mm"]

        if crossing_without_rain is None and depletion_without_rain >= raw:
            crossing_without_rain = day

        if crossing_with_trusted_rain is None and depletion_with_trusted_rain >= raw:
            crossing_with_trusted_rain = day

    return crossing_without_rain, crossing_with_trusted_rain


def _decide(
    current_depletion,
    current_raw,
    forecast_balances,
    future_rain,
    rain_probability,
    rain_probability_threshold,
    irrigate_within_days,
    rain_skip_window_days
):
    if rain_probability_threshold is None:
        rain_probability_threshold = get_setting("rain", "skip_probability_threshold")

    if irrigate_within_days is None:
        irrigate_within_days = get_setting("advisor", "irrigate_within_days")

    if rain_skip_window_days is None:
        rain_skip_window_days = get_setting("advisor", "rain_skip_window_days")

    # Safety rule: once the root zone is already past RAW,
    # the crop is stressed today. Forecast rain cannot undo
    # that, so never skip or wait.
    if current_raw is not None and current_depletion >= current_raw:
        return {
            "action": "IRRIGATE",
            "crossing_day": 0,
            "reason_code": "ALREADY_PAST_RAW"
        }

    probabilities = normalise_probabilities(rain_probability, len(forecast_balances))

    crossing_without_rain, crossing_with_trusted_rain = _find_crossings(
        forecast_balances,
        future_rain,
        probabilities,
        rain_probability_threshold
    )

    # Irrigate if trusted rain does not prevent RAW being
    # reached within the next irrigate_within_days days.
    if (
        crossing_with_trusted_rain is not None
        and crossing_with_trusted_rain <= irrigate_within_days
    ):
        return {
            "action": "IRRIGATE",
            "crossing_day": crossing_with_trusted_rain,
            "reason_code": "CROSSES_RAW_IN_2D"
        }

    # Skip when irrigation would be needed inside the rain
    # window without rain, but trusted rain keeps the field
    # within RAW for the whole window. Later days in a long
    # forecast are reassessed on following days.
    if (
        crossing_without_rain is not None
        and crossing_without_rain <= rain_skip_window_days
        and (
            crossing_with_trusted_rain is None
            or crossing_with_trusted_rain > rain_skip_window_days
        )
    ):
        return {
            "action": "SKIP",
            "crossing_day": crossing_without_rain,
            "reason_code": "RAINFALL_EXPECTED"
        }

    # If the threshold is reached later, reassess on the next day.
    if crossing_with_trusted_rain is not None:
        return {
            "action": "WAIT",
            "crossing_day": crossing_with_trusted_rain,
            "reason_code": "CROSSES_RAW_LATER"
        }

    # No crossing: this is a healthy balance, not a reason
    # to skip irrigation because of rainfall.
    return {
        "action": "WAIT",
        "crossing_day": None,
        "reason_code": "HEALTHY_WATER_BALANCE"
    }


def decide_irrigation(
    current_depletion,
    raw,
    future_etc,
    future_rain,
    rain_probability,
    rain_probability_threshold=None,
    forecast_balances=None
):
    """
    Decide whether irrigation is required.

    If forecast_balances is supplied, it is the preferred
    source for future depletion and RAW crossing.

    Otherwise the simple future_etc path is used, with one
    RAW for every day. It is retained for backward
    compatibility with existing tests.
    """

    if forecast_balances is not None:
        return decide_irrigation_from_forecast(
            forecast_balances=forecast_balances,
            future_rain=future_rain,
            rain_probability=rain_probability,
            rain_probability_threshold=rain_probability_threshold,
            current_raw=raw
        )

    if len(future_etc) != len(future_rain):
        raise ValueError("future_etc and future_rain must have equal lengths")

    simple_balances = [
        {
            "previous_depletion_mm": current_depletion,
            "actual_etc_mm": etc,
            "raw_mm": raw
        }
        for etc in future_etc
    ]

    if not simple_balances:
        if current_depletion >= raw:
            return {
                "action": "IRRIGATE",
                "crossing_day": 0,
                "reason_code": "ALREADY_PAST_RAW"
            }

        return {
            "action": "WAIT",
            "crossing_day": None,
            "reason_code": "NO_FORECAST_DATA"
        }

    return _decide(
        current_depletion=current_depletion,
        current_raw=raw,
        forecast_balances=simple_balances,
        future_rain=future_rain,
        rain_probability=rain_probability,
        rain_probability_threshold=rain_probability_threshold,
        irrigate_within_days=None,
        rain_skip_window_days=None
    )


def decide_irrigation_from_forecast(
    forecast_balances,
    future_rain,
    rain_probability,
    rain_probability_threshold=None,
    current_raw=None,
    irrigate_within_days=None,
    rain_skip_window_days=None
):
    """
    Decide irrigation using forecast balances and per-day
    rain probabilities.

    Forecast balances must contain:
        previous_depletion_mm
        actual_etc_mm
        raw_mm

    Rows from forecast_water_balance() also contain
    potential_etc_mm, taw_mm, p and et0_mm, which are used
    to recompute Ks for each rain scenario, apply the
    0.2 * ET0 rule and keep depletion within [0, TAW].

    current_raw is today's RAW. If it is not given, the
    first forecast day's RAW is used for the safety rule.

    Rain is trusted only when its probability reaches the threshold.
    """

    if len(forecast_balances) != len(future_rain):
        raise ValueError(
            "forecast_balances and future_rain must have equal lengths"
        )

    if not forecast_balances:
        return {
            "action": "WAIT",
            "crossing_day": None,
            "reason_code": "NO_FORECAST_DATA"
        }

    if current_raw is None:
        current_raw = forecast_balances[0]["raw_mm"]

    return _decide(
        current_depletion=forecast_balances[0]["previous_depletion_mm"],
        current_raw=current_raw,
        forecast_balances=forecast_balances,
        future_rain=future_rain,
        rain_probability=rain_probability,
        rain_probability_threshold=rain_probability_threshold,
        irrigate_within_days=irrigate_within_days,
        rain_skip_window_days=rain_skip_window_days
    )


def calculate_irrigation_depth(current_depletion, maximum_depth=None, minimum_depth=None):
    """
    Calculate the net irrigation depth.

    Refill approximately the current depletion, capped at
    the practical maximum and rounded up to the smallest depth
    that can be spread by flood irrigation
    (config irrigation.minimum_advised_depth_mm).
    """
    if maximum_depth is None:
        maximum_depth = get_setting("irrigation", "maximum_depth_mm")

    if minimum_depth is None:
        minimum_depth = get_setting("irrigation", "minimum_advised_depth_mm")

    if current_depletion <= 0:
        return 0.0

    depth = min(current_depletion, maximum_depth)

    return max(depth, min(minimum_depth, maximum_depth))


def make_daily_decision(
    current_depletion,
    raw,
    future_etc,
    future_rain,
    rain_probability,
    heat_result,
    maximum_depth=None,
    rain_probability_threshold=None,
    forecast_balances=None,
    critical=None
):
    """
    Combine heat risk and water-balance logic.

    Decision priority:
        1. Heat protection
        2. Irrigation required (including already past RAW)
        3. Critical growth-stage irrigation (critical, from
           engine.critical.critical_irrigation_due): IRRIGATE its
           light depth, or SKIP if confident rain in the rain
           window covers what is still needed
        4. Rain-supported skip
        5. Wait

    Heat protection applies only when confident rain in the
    heat window is below heat.meaningful_rain_mm and the root
    zone can hold the light depth (depletion >= light_depth_mm).
    Its depth is the light depth, or the full refill if the
    field needs water anyway.

    If heat risk is HIGH but no heat irrigation is advised, a WAIT
    keeps a heat reason (HEAT_RISK_SOIL_MOIST or
    HEAT_RISK_RAIN_EXPECTED) so the farmer is still warned.
    """

    if maximum_depth is None:
        maximum_depth = get_setting("irrigation", "maximum_depth_mm")

    if rain_probability_threshold is None:
        rain_probability_threshold = get_setting("rain", "skip_probability_threshold")

    irrigation_result = decide_irrigation(
        current_depletion=current_depletion,
        raw=raw,
        future_etc=future_etc,
        future_rain=future_rain,
        rain_probability=rain_probability,
        rain_probability_threshold=rain_probability_threshold,
        forecast_balances=forecast_balances
    )

    if irrigation_result["action"] == "IRRIGATE":
        refill_depth = calculate_irrigation_depth(
            current_depletion,
            maximum_depth
        )
    else:
        refill_depth = 0.0

    heat_wait_reason = None

    if heat_result["heat_risk"] == "HIGH":
        heat_window_days = get_setting("heat", "forecast_window_days")
        window_rain = list(future_rain)[:heat_window_days]
        window_probability = normalise_probabilities(
            rain_probability,
            len(future_rain)
        )[:heat_window_days]

        confident_rain = confident_rain_total(
            window_rain,
            window_probability,
            rain_probability_threshold
        )

        light_depth = min(
            get_setting("irrigation", "light_depth_mm"),
            maximum_depth
        )

        # Meaningful confident rain will cool the crop, so a
        # heat irrigation is not needed. Nor is one needed while
        # the root zone has no room for the light irrigation:
        # the soil is still wet (e.g. from yesterday's heat
        # irrigation) and the water would only drain away.
        rain_coming = confident_rain >= get_setting("heat", "meaningful_rain_mm")

        if not rain_coming and (current_depletion >= light_depth or refill_depth > 0):
            return {
                "action": "HEAT_PROTECTION",
                "depth_mm": max(light_depth, refill_depth),
                "reason_code": "HEAT_RISK",
                "crossing_day": irrigation_result["crossing_day"]
            }

        heat_wait_reason = (
            "HEAT_RISK_RAIN_EXPECTED" if rain_coming else "HEAT_RISK_SOIL_MOIST"
        )

    if irrigation_result["action"] == "IRRIGATE":
        return {
            "action": "IRRIGATE",
            "depth_mm": refill_depth,
            "reason_code": irrigation_result["reason_code"],
            "crossing_day": irrigation_result["crossing_day"]
        }

    if critical is not None:
        skip_days = get_setting("advisor", "rain_skip_window_days")
        rain_for_stage = confident_rain_total(
            list(future_rain)[:skip_days],
            normalise_probabilities(rain_probability, len(future_rain))[:skip_days],
            rain_probability_threshold
        )

        if rain_for_stage >= critical["needed_mm"]:
            return {
                "action": "SKIP",
                "depth_mm": 0.0,
                "reason_code": "CRITICAL_STAGE_RAIN_EXPECTED",
                "crossing_day": irrigation_result["crossing_day"]
            }

        return {
            "action": "IRRIGATE",
            "depth_mm": min(critical["depth_mm"], maximum_depth),
            "reason_code": "CRITICAL_STAGE_IRRIGATION",
            "crossing_day": irrigation_result["crossing_day"]
        }

    if irrigation_result["action"] == "SKIP":
        return {
            "action": "SKIP",
            "depth_mm": 0.0,
            "reason_code": irrigation_result["reason_code"],
            "crossing_day": irrigation_result["crossing_day"]
        }

    return {
        "action": "WAIT",
        "depth_mm": 0.0,
        "reason_code": heat_wait_reason or irrigation_result["reason_code"],
        "crossing_day": irrigation_result["crossing_day"]
    }
