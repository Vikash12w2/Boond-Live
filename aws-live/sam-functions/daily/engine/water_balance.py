from engine.data import get_crop, get_setting, get_soil
from engine.kc import get_kc, get_stage


# FAO-56 Table 22 note: the adjusted p stays within these limits.
P_MIN = 0.1
P_MAX = 0.8


def get_root_depth(day_after_sowing, crop="wheat"):
    """
    Calculate root depth.

    Root depth grows linearly from initial_m on day 1
    to maximum_m on full_depth_day, then stays at maximum_m.

    For wheat, maximum_m is 1.0 m: Punjab wheat is spring
    wheat (FAO-56 Table 22: 1.0-1.5 m) and the model uses
    the lower end pending local calibration.
    """

    root_depth = get_crop(crop)["root_depth"]

    initial_depth = root_depth["initial_m"]
    maximum_depth = root_depth["maximum_m"]
    full_depth_day = root_depth["full_depth_day"]

    if day_after_sowing <= 1:
        return initial_depth

    if day_after_sowing >= full_depth_day:
        return maximum_depth

    growth_fraction = (day_after_sowing - 1) / (full_depth_day - 1)

    return initial_depth + growth_fraction * (
        maximum_depth - initial_depth
    )


def get_soil_parameters(soil):
    """
    Return field capacity and wilting point
    for the selected soil.
    """

    return get_soil(soil)


def calculate_taw(soil, root_depth_m):
    params = get_soil_parameters(soil)

    theta_fc = params["theta_fc"]
    theta_wp = params["theta_wp"]

    return 1000 * (theta_fc - theta_wp) * root_depth_m


def get_p_table(crop="wheat", day_after_sowing=None):
    """
    The crop's depletion fraction (FAO-56 Table 22), or its
    stage-specific value from depletion_fraction_by_stage.
    """
    crop_data = get_crop(crop)
    by_stage = crop_data.get("depletion_fraction_by_stage") or {}

    if day_after_sowing is not None:
        stage = get_stage(day_after_sowing, crop)

        if stage in by_stage:
            return by_stage[stage]

    return crop_data["depletion_fraction"]


def calculate_p(etc, p_table=None, crop="wheat", day_after_sowing=None):
    """
    Calculate depletion fraction p.

    p = p_table + 0.04 * (5 - ETc)

    The result is limited to [0.1, 0.8] (FAO-56 Table 22).
    """

    if p_table is None:
        p_table = get_p_table(crop, day_after_sowing)

    p = p_table + 0.04 * (5 - etc)

    return max(P_MIN, min(P_MAX, p))


def calculate_raw(taw, p):
    """
    Calculate Readily Available Water (RAW).
    """

    return p * taw

def calculate_ks(depletion, taw, p):
    """
    Calculate the water-stress coefficient Ks.

    If depletion is within RAW:
        Ks = 1

    If depletion is greater than RAW:
        Ks decreases as the soil becomes drier.

    Ks is limited between 0 and 1.
    """
    raw = calculate_raw(taw, p)

    if depletion <= raw:
        return 1.0

    denominator = (1 - p) * taw

    if denominator <= 0:
        return 0.0

    ks = (taw - depletion) / denominator

    return max(0.0, min(1.0, ks))

def calculate_actual_etc(etc, ks):
    """
    Calculate stress-adjusted crop evapotranspiration.
    """
    return ks * etc

def calculate_kc_etc(day_after_sowing, et0, crop="wheat"):
    """
    Calculate Kc and crop evapotranspiration ETc.
    """

    kc = get_kc(day_after_sowing, crop)

    etc = kc * et0

    return kc, etc


def effective_rainfall(rain, et0, threshold_ratio=None):
    """
    Determine the rainfall amount used by the daily
    root-zone water balance.

    FAO-56 notes that daily precipitation below about
    0.2 * ET0 can normally be ignored because it is
    generally evaporated. The ratio is read from
    config.json (rain.effective_threshold_ratio).

    This is therefore a practical FAO-56 simplification,
    not a universal physical threshold.
    """

    if rain < 0:
        raise ValueError("rain cannot be negative")

    if threshold_ratio is None:
        threshold_ratio = get_setting("rain", "effective_threshold_ratio")

    threshold = threshold_ratio * et0

    if rain < threshold:
        return 0.0

    return rain


def update_depletion(
    previous_depletion,
    effective_rain,
    irrigation,
    actual_etc,
    taw
):
    """
    Update daily soil-water depletion.

    D(i) = D(i-1) - P_eff - I + actual_ETc

    Depletion is constrained to [0, TAW].

    If the incoming water exceeds the amount that
    can be stored in the root zone, the excess is
    treated as deep percolation.
    """

    raw_depletion = (
        previous_depletion
        - effective_rain
        - irrigation
        + actual_etc
    )

    if raw_depletion < 0:
        deep_percolation = -raw_depletion
        depletion = 0.0

    else:
        deep_percolation = 0.0
        depletion = min(taw, raw_depletion)

    return depletion, deep_percolation

def calculate_daily_balance(
    day_after_sowing,
    soil,
    et0,
    rain,
    irrigation,
    previous_depletion,
    crop="wheat"
):
    """
    Calculate the complete daily soil-water balance.

    Returns all important intermediate values so that
    the advisor can later use them for irrigation decisions.
    """

    # -------------------------
    # Crop calculations
    # -------------------------

    root_depth = get_root_depth(day_after_sowing, crop)

    kc, potential_etc = calculate_kc_etc(
        day_after_sowing,
        et0,
        crop
    )

    # -------------------------
    # Soil water capacity
    # -------------------------

    taw = calculate_taw(
        soil,
        root_depth
    )

    # A carried-over depletion can never exceed
    # what today's root zone is able to hold.
    previous_depletion = min(previous_depletion, taw)

    # -------------------------
    # Allowable depletion
    # -------------------------

    p = calculate_p(
        potential_etc,
        crop=crop,
        day_after_sowing=day_after_sowing
    )

    raw = calculate_raw(
        taw,
        p
    )

    # -------------------------
    # Water stress
    # -------------------------

    ks = calculate_ks(
        previous_depletion,
        taw,
        p
    )

    actual_etc = calculate_actual_etc(
        potential_etc,
        ks
    )

    # -------------------------
    # Rainfall
    # -------------------------

    effective_rain = effective_rainfall(
        rain,
        et0
    )

    # -------------------------
    # New depletion
    # -------------------------

    new_depletion, deep_percolation = update_depletion(
        previous_depletion,
        effective_rain,
        irrigation,
        actual_etc,
        taw
    )

    return {
        "day_after_sowing": day_after_sowing,
        "crop": crop,
        "soil": soil,
        "root_depth_m": root_depth,
        "kc": kc,
        "et0_mm": et0,
        "potential_etc_mm": potential_etc,
        "taw_mm": taw,
        "p": p,
        "raw_mm": raw,
        "previous_depletion_mm": previous_depletion,
        "ks": ks,
        "actual_etc_mm": actual_etc,
        "rain_mm": rain,
        "effective_rain_mm": effective_rain,
        "irrigation_mm": irrigation,
        "depletion_mm": new_depletion,
        "deep_percolation_mm": deep_percolation
    }

def forecast_water_balance(
    start_day_after_sowing,
    soil,
    future_et0,
    future_rain,
    initial_depletion,
    crop="wheat"
):
    """
    Simulate future soil-water balance day by day.

    The initial_depletion is the depletion at the end of today.
    future_et0[0] and future_rain[0] represent tomorrow.

    Each forecast day independently recalculates:
        - root depth
        - Kc
        - potential ETc
        - TAW
        - p
        - RAW
        - Ks
        - actual ETc
        - effective rainfall
        - new depletion

    No irrigation is assumed during the forecast.
    This represents the conservative "what happens if we
    do not irrigate?" scenario used to detect RAW crossing.
    """

    if len(future_et0) != len(future_rain):
        raise ValueError("future_et0 and future_rain must have equal lengths")

    depletion = initial_depletion
    predictions = []

    for index, (et0, rain) in enumerate(zip(future_et0, future_rain), start=1):

        day = start_day_after_sowing + index

        balance = calculate_daily_balance(
            day_after_sowing=day,
            soil=soil,
            et0=et0,
            rain=rain,
            irrigation=0.0,
            previous_depletion=depletion,
            crop=crop
        )

        depletion = balance["depletion_mm"]

        predictions.append(balance)

    return predictions
