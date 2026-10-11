"""
Download daily weather from Open-Meteo once and save it for the
season simulator (engine/simulate.py).

    python tools/fetch_weather.py --lat 30.90 --lon 75.85 \
        --start 2021-11-01 --end 2022-04-30 --out replay/cache/ludhiana_actual_2021_22.json

--source archive             ERA5 reanalysis (what actually happened)
--source historical-forecast archived forecasts (what the advisor would have seen);
                             also saves rain_prob (0-1) when Open-Meteo has it

For an honest replay, fetch BOTH and run
    python -m engine.replay --weather archive.json --forecast forecast.json ...

Missing ET0 values stop the download (a missing day would otherwise
look like a day with no crop water use). Missing rain is saved as 0
with a warning; missing Tmax stays null (heat rules skip it).
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path


URLS = {
    "archive": "https://archive-api.open-meteo.com/v1/archive",
    "historical-forecast": "https://historical-forecast-api.open-meteo.com/v1/forecast",
}

DAILY_FIELDS = {
    "et0_mm": "et0_fao_evapotranspiration",
    "rain_mm": "precipitation_sum",
    "tmax_c": "temperature_2m_max",
}


def _missing_dates(dates, values):
    return [day for day, value in zip(dates, values) if value is None]


def fetch(lat, lon, start, end, source="archive"):
    fields = dict(DAILY_FIELDS)

    if source == "historical-forecast":
        fields["rain_prob"] = "precipitation_probability_max"

    query = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": ",".join(fields.values()),
        "timezone": "Asia/Kolkata",
    })

    with urllib.request.urlopen(f"{URLS[source]}?{query}", timeout=60) as response:
        payload = json.load(response)

    daily = payload["daily"]
    dates = daily["time"]

    missing_et0 = _missing_dates(dates, daily[fields["et0_mm"]])

    if missing_et0:
        raise ValueError(
            f"ET0 missing on {len(missing_et0)} days "
            f"({missing_et0[0]} .. {missing_et0[-1]}); choose other dates or source"
        )

    missing_rain = _missing_dates(dates, daily[fields["rain_mm"]])

    if missing_rain:
        print(
            f"WARNING: rain missing on {len(missing_rain)} days, saved as 0 mm "
            f"(first {missing_rain[0]})",
            file=sys.stderr
        )

    result = {
        "date": dates,
        "et0_mm": daily[fields["et0_mm"]],
        "rain_mm": [0.0 if value is None else value for value in daily[fields["rain_mm"]]],
        "tmax_c": daily[fields["tmax_c"]],
    }

    if "rain_prob" in fields and fields["rain_prob"] in daily:
        # Open-Meteo gives %, the engine uses 0-1. None stays None (= not trusted).
        result["rain_prob"] = [
            None if value is None else value / 100.0
            for value in daily[fields["rain_prob"]]
        ]

    return {
        "latitude": payload["latitude"],
        "longitude": payload["longitude"],
        "source": f"Open-Meteo {source}",
        "missing_rain_dates": missing_rain,
        "daily": result,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--source", choices=URLS, default="archive")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    weather = fetch(args.lat, args.lon, args.start, args.end, args.source)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(weather, indent=2))

    print(f"Saved {len(weather['daily']['date'])} days to {out}")


if __name__ == "__main__":
    main()
