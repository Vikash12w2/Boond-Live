import json
from datetime import date
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def load_json(filename):
    """
    Load a JSON data file from the engine directory.

    Results are cached, so callers must not modify
    the returned dictionaries.
    """
    with open(BASE_DIR / filename, "r") as file:
        return json.load(file)


def entries(data):
    """
    Return the real entries of a data file. Keys starting
    with "_" hold documentation and are ignored.
    """
    return {key: value for key, value in data.items() if not key.startswith("_")}


def load_config():
    return load_json("config.json")


def get_setting(section, key):
    """
    Return one value from config.json, e.g.
    get_setting("rain", "skip_probability_threshold").
    """
    return load_config()[section][key]


def crop_names():
    return list(entries(load_json("crops.json")))


def get_crop(crop="wheat"):
    crops = entries(load_json("crops.json"))

    if crop not in crops:
        raise ValueError(f"Unknown crop: {crop}")

    return crops[crop]


def is_paddy(crop):
    return get_crop(crop).get("crop_family") == "paddy"


def get_soil(soil):
    soils = entries(load_json("soils.json"))

    if soil not in soils:
        raise ValueError(f"Unknown soil type: {soil}")

    return soils[soil]


def farmer_soil_choices():
    """
    The soils shown in the onboarding form (Sandy / Loam / Clay).
    """
    return [
        name
        for name, soil in entries(load_json("soils.json")).items()
        if soil.get("farmer_choice")
    ]


def max_advised_depth(crop="wheat"):
    """
    Cap on an IRRIGATE advice: the crop's own cap if it has
    one, otherwise config irrigation.maximum_depth_mm.
    """
    return get_crop(crop).get("irrigation", {}).get(
        "max_advised_depth_mm",
        get_setting("irrigation", "maximum_depth_mm")
    )


def select_profile(crop, sowing_date, variety=None, ratoon=False):
    """
    Pick the crops.json profile when a field is registered
    (DATA_GUIDE 4.1). Store the result with the field so later
    edits to crops.json do not silently change running fields.

    sowing_date is the sowing date for wheat and cotton, the
    transplanting date for paddy and the planting (or last
    harvest, for a ratoon) date for sugarcane.
    """
    if isinstance(sowing_date, str):
        sowing_date = date.fromisoformat(sowing_date)

    if crop == "wheat":
        # January-June: very late sowing (PAU: PBW 757, ~114 days).
        if sowing_date.month < 7:
            return "wheat_january"

        # PAU timely-sown window ends 21 Nov (Rabi 2025-26, p.17).
        timely = (sowing_date.month, sowing_date.day) <= (11, 21)

        return "wheat" if timely else "wheat_late"

    if crop == "paddy":
        return "paddy_short" if variety and variety.upper().replace(" ", "") == "PR126" else "paddy"

    if crop == "sugarcane":
        if ratoon:
            return "sugarcane_ratoon"

        # AICRP (ICAR-IISR 2017): North-West India plants autumn cane in
        # September-October and spring cane in February-March.
        return "sugarcane_autumn" if 8 <= sowing_date.month <= 12 else "sugarcane"

    get_crop(crop)
    return crop


CROP_FAMILIES = ("wheat", "paddy", "sugarcane")


def add_profile_arguments(parser):
    """--crop / --variety / --ratoon / --exact-profile for the CLIs."""
    parser.add_argument("--crop", default="wheat",
                        help="wheat, paddy, cotton, sugarcane, or an exact crops.json profile key")
    parser.add_argument("--variety", default=None, help="paddy variety, e.g. PR126")
    parser.add_argument("--ratoon", action="store_true", help="sugarcane ratoon crop")
    parser.add_argument("--exact-profile", action="store_true",
                        help="use --crop as the crops.json key without choosing by sowing date")


def profile_from_arguments(args):
    """
    Same choice as at field registration: wheat sown after 21 Nov runs
    the wheat_late profile and wheat sown in January wheat_january,
    PR 126 runs paddy_short, cane planted from August to December
    sugarcane_autumn and a ratoon sugarcane_ratoon. --exact-profile
    keeps --crop as given.
    """
    if args.exact_profile or args.crop not in CROP_FAMILIES:
        get_crop(args.crop)
        return args.crop

    return select_profile(args.crop, args.sow, variety=args.variety, ratoon=args.ratoon)
