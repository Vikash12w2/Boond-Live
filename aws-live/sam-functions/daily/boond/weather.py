"""Open-Meteo weather in the engine's layout, cached per grid cell and day in S3.

observed: sowing .. yesterday. ERA5 archive first, then the forecast API's past
          days, which win on overlap and fill the archive's few-day lag.
forecast: today .. today+15, with rain_prob as a 0-1 fraction.
Open-Meteo data is CC BY 4.0.
"""
import json
import logging
import random
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta

from botocore.exceptions import ClientError

log = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
PAST_DAYS = 7
FORECAST_DAYS = 16
DAILY = {"et0_mm": "et0_fao_evapotranspiration", "rain_mm": "precipitation_sum", "tmax_c": "temperature_2m_max"}
SERIES = ("date", "et0_mm", "rain_mm", "tmax_c")


class WeatherUnavailable(Exception):
    """No fresh weather and no cache from the day before."""


def cell(lat, lon):
    return round(lat, 2), round(lon, 2)


def http_get_json(url, params, tries=3, timeout=20):
    query = urllib.parse.urlencode(params)
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(f"{url}?{query}", timeout=timeout) as response:
                return json.load(response)
        except OSError:
            if attempt == tries:
                raise
            time.sleep(2 ** attempt + random.random())


def _rows(daily, names):
    return {day: {key: daily[name][i] for key, name in names.items() if name in daily}
            for i, day in enumerate(daily["time"])}


def fetch(lat, lon, earliest_sowing, today, get_json=http_get_json):
    base = {"latitude": lat, "longitude": lon, "timezone": "Asia/Kolkata"}
    names = dict(DAILY, rain_prob="precipitation_probability_max")
    forecast = _rows(get_json(FORECAST_URL, dict(base, daily=",".join(names.values()),
                                                  past_days=PAST_DAYS, forecast_days=FORECAST_DAYS))["daily"], names)
    observed = {}
    if earliest_sowing < today - timedelta(days=PAST_DAYS):
        archive = get_json(ARCHIVE_URL, dict(base, daily=",".join(DAILY.values()),
                                             start_date=earliest_sowing.isoformat(),
                                             end_date=(today - timedelta(days=1)).isoformat()))
        observed.update({day: row for day, row in _rows(archive["daily"], DAILY).items()
                         if row.get("et0_mm") is not None})
    observed.update({day: row for day, row in forecast.items()
                     if day < today.isoformat() and row.get("et0_mm") is not None})
    obs_days = sorted(day for day in observed if day >= earliest_sowing.isoformat())
    fc_days = sorted(day for day in forecast if day >= today.isoformat())
    return {
        "observed": {"date": obs_days,
                     "et0_mm": [observed[d]["et0_mm"] for d in obs_days],
                     "rain_mm": [observed[d].get("rain_mm") or 0.0 for d in obs_days],
                     "tmax_c": [observed[d].get("tmax_c") for d in obs_days]},
        "forecast": {"date": fc_days,
                     "et0_mm": [forecast[d]["et0_mm"] for d in fc_days],
                     "rain_mm": [forecast[d].get("rain_mm") or 0.0 for d in fc_days],
                     "tmax_c": [forecast[d].get("tmax_c") for d in fc_days],
                     "rain_prob": [None if forecast[d].get("rain_prob") is None else forecast[d]["rain_prob"] / 100
                                   for d in fc_days]},
        "fetched_for": today.isoformat(),
        "earliest_sowing": earliest_sowing.isoformat(),
    }


def _shift(weather, today):
    """Yesterday's file used today: forecast rows before today become observed."""
    fc, obs = weather["forecast"], weather["observed"]
    keep = [i for i, d in enumerate(fc["date"]) if d >= today.isoformat()]
    move = [i for i, d in enumerate(fc["date"]) if d < today.isoformat()]
    return {
        "observed": {k: obs[k] + [fc[k][i] for i in move] for k in SERIES},
        "forecast": {k: [fc[k][i] for i in keep] for k in fc},
        "fetched_for": weather["fetched_for"],
        "earliest_sowing": weather["earliest_sowing"],
    }


class WeatherCache:
    def __init__(self, s3, bucket):
        self.s3, self.bucket = s3, bucket

    def _key(self, lat, lon, day):
        return f"weather/{lat:.2f}_{lon:.2f}/{day.isoformat()}.json"

    def get(self, lat, lon, day):
        try:
            body = self.s3.get_object(Bucket=self.bucket, Key=self._key(lat, lon, day))["Body"].read()
        except ClientError as error:
            if error.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise
        return json.loads(body)

    def put(self, lat, lon, day, weather):
        self.s3.put_object(Bucket=self.bucket, Key=self._key(lat, lon, day),
                           Body=json.dumps(weather).encode(), ContentType="application/json")


def weather_for(lat, lon, earliest_sowing, today, cache, get_json=http_get_json):
    """(weather, stale). Uses today's cache, else fetches; on failure falls back to yesterday's cache."""
    lat, lon = cell(lat, lon)
    cached = cache.get(lat, lon, today)
    if cached and cached["earliest_sowing"] <= earliest_sowing.isoformat():
        return cached, False
    try:
        weather = fetch(lat, lon, earliest_sowing, today, get_json=get_json)
    except Exception as error:
        log.warning("weather fetch failed for %s,%s: %s", lat, lon, error)
        yesterday = cache.get(lat, lon, today - timedelta(days=1))
        if yesterday and yesterday["earliest_sowing"] <= earliest_sowing.isoformat():
            return _shift(yesterday, today), True
        raise WeatherUnavailable(f"no weather for {lat},{lon} on {today}") from error
    cache.put(lat, lon, today, weather)
    return weather, False
