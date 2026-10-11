"""06:00 IST job: refresh and notify every active field.

Weather is fetched once per grid cell, from the earliest sowing date among the
cell's fields (the engine ignores days before each field's own sowing). One
field's failure is logged and does not stop the others.
"""
import logging
from collections import defaultdict
from datetime import date

from engine.field_runner import MissingWeather

from boond.refresh import mark_unavailable, refresh_field
from boond.util import today_ist, token_hash
from boond.weather import cell

log = logging.getLogger(__name__)


def run_all(deps, today):
    by_cell = defaultdict(list)
    for token in deps.store.active_tokens():
        profile = deps.store.get_profile(token)
        if profile is None:  # deleted after the index listed it
            continue
        by_cell[cell(profile["latitude"], profile["longitude"])].append((token, profile))
    summary = {"fields": sum(len(fields) for fields in by_cell.values()), "ok": 0, "skipped": 0, "failed": 0}
    for (lat, lon), fields in by_cell.items():
        earliest = min(date.fromisoformat(profile["sowing_date"]) for _, profile in fields)
        try:
            weather, stale = deps.weather(lat, lon, earliest, today)
        except Exception as error:  # WeatherUnavailable, or e.g. an S3 error on the cache
            log.warning("no weather for cell %s,%s: %s", lat, lon, error)
            for token, _ in fields:
                _unavailable(token, deps, today)
            summary["skipped"] += len(fields)
            continue
        for token, _ in fields:
            try:
                refresh_field(token, deps, today, weather=weather, stale=stale, notify=True)
                summary["ok"] += 1
            except MissingWeather as error:  # a day of observed weather is missing for this field
                log.warning("field %s: %s", token_hash(token), error)
                _unavailable(token, deps, today)
                summary["skipped"] += 1
            except Exception:
                log.exception("field %s failed", token_hash(token))
                summary["failed"] += 1
    log.info("daily run %s: %s", today, summary)
    return summary


def _unavailable(token, deps, today):
    try:
        mark_unavailable(token, deps, today, notify=True)
    except Exception:
        log.exception("field %s: could not record unavailable advice", token_hash(token))


def handler(event, context):
    from boond.aws import deps
    return run_all(deps(), today_ist())
