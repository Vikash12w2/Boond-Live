from engine.data import get_crop


STAGES = ("initial", "development", "mid", "late")


def get_stage_boundaries(crop="wheat"):
    """
    Return (stage, days_before_stage, stage_length) for each
    FAO-56 growth stage, in order.
    """
    stages = get_crop(crop)["stages"]

    boundaries = []
    days_before_stage = 0

    for stage in STAGES:
        stage_length = stages[stage]["days"]
        boundaries.append((stage, days_before_stage, stage_length))
        days_before_stage += stage_length

    return boundaries


def get_season_length(crop="wheat"):
    _, days_before_stage, stage_length = get_stage_boundaries(crop)[-1]
    return days_before_stage + stage_length


def get_stage(day_after_sowing, crop="wheat"):
    if day_after_sowing < 1:
        raise ValueError("day_after_sowing must be >= 1")

    for stage, days_before_stage, stage_length in get_stage_boundaries(crop):
        if day_after_sowing <= days_before_stage + stage_length:
            return stage

    return "post_harvest"


def get_wheat_stage(day_after_sowing):
    return get_stage(day_after_sowing, "wheat")


def linear_interpolation(start, end, fraction):
    return start + (end - start) * fraction


def get_kc(day_after_sowing, crop="wheat"):
    """
    Daily Kc using FAO-56 Eq. 66 inside each stage:

        Kc_i = kc_start + [(i - sum(L_prev)) / L_stage] * (kc_end - kc_start)

    Day i is counted from 1 at sowing, so the first
    development day already moves away from Kc ini and
    the last day of the stage reaches kc_end. Initial and
    mid stages have kc_start == kc_end, so Kc is constant.
    """
    stage = get_stage(day_after_sowing, crop)

    if stage == "post_harvest":
        return 0.0

    for name, days_before_stage, stage_length in get_stage_boundaries(crop):
        if name == stage:
            break

    stage_kc = get_crop(crop)["stages"][stage]

    # The day lies inside this stage, so stage_length >= 1.
    fraction = (day_after_sowing - days_before_stage) / stage_length

    return linear_interpolation(
        stage_kc["kc_start"],
        stage_kc["kc_end"],
        fraction
    )
