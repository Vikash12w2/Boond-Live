# Boond engine: how the backend uses it

The engine is pure Python with no network calls, and the same inputs always give the same output. The replay and the live daily job run **the same functions**, so the 2021-22 replay validates exactly the code that runs in production. `engine/tests/test_field_runner.py::test_daily_live_runs_match_the_replay_exactly` checks this day by day.

## The one call the daily job makes

```python
from engine.data import select_profile
from engine.field_runner import start_state, advance_field, MissingWeather
from engine.checkins import make_event
from engine.field_runner import sowing_warnings
from engine.messages import render, render_warnings

# At registration (POST /fields)
field = {
    "crop": select_profile("wheat", "2026-11-12"),   # store the profile key, not just "wheat"
    "soil": "loam", "sowing_date": "2026-11-12",
    "area_acres": 1.5, "lift_m": 30, "pump_eff": 0.4,
}
state = start_state(field)                           # store as the STATE item
notes = render_warnings({"warnings": sowing_warnings(field)}, field_lang)   # show on the confirmation screen

# Farmer check-in (POST /fields/{token}/events)
event = make_event("WATERED", "normal", "2026-12-14", field["crop"])   # store as an EVENT item

# Every morning at 06:00 IST
result = advance_field(field, state, observed, forecast, events, today)
state  = result["state"]       # write back (conditional write on last_processed_date)
advice = result["advice"]      # write as the DAY#today item
text   = render(advice, field_lang)   # template text; Bedrock may rewrite it, then
                                      # check numbers_in(text) <= allowed_numbers(advice)
notes  = render_warnings(advice, field_lang)   # e.g. sown after the recommended window
```

`select_profile(crop, date, variety=None, ratoon=False)` chooses the profile from the date the farmer gives:

| Crop | Date | Profile |
|---|---|---|
| Wheat | up to 21 Nov | `wheat` (145 d) |
| Wheat | 22 Nov – 31 Dec | `wheat_late` (133 d) |
| Wheat | 1 Jan – 30 Jun | `wheat_january` (114 d, PBW 757) |
| Paddy | transplanting date | `paddy`, or `paddy_short` for PR 126 |
| Sugarcane | January – July | `sugarcane` (spring, 360 d) |
| Sugarcane | August – December | `sugarcane_autumn` (420 d) |
| Sugarcane | ratoon (date = last harvest) | `sugarcane_ratoon` (280 d) |
| Cotton | sowing date | `cotton` |

### Inputs (the same layout as `replay/cache/*.json`)
- **`observed`**: `{"date": [...], "et0_mm": [...], "rain_mm": [...], "tmax_c": [...]}`. It covers every day from `state["last_processed_date"] + 1` up to yesterday. Use the forecast API's `past_days` for recent days, and the archive API when a field has missed more than ~5 days.
- **`forecast`**: the same layout, **starting today**, plus `rain_prob` (0–1, which is Open-Meteo % ÷ 100), for 16 days.
- **`events`**: every check-in since the last processed date. A stored `mm_assumed` takes priority over the current config.

### Output (`advice`)
- `status`: `WAITING` (not sown yet), `ACTIVE`, or `SEASON_OVER`.
- `action`, `depth_mm` and `reason_code`, rendered into a message by `messages.render`.
- `stage`, `heat_stage`, `heat_risk`, `max_forecast_tmax_c`, `critical_stage`.
- `last_irrigation_date` and `last_irrigation_day`: the last day on which irrigation may be advised. After it the advice is `WAIT` / `IRRIGATION_STOPPED`, heat irrigation included.
- `warnings`: a list, empty when all is well. Today it can hold one entry, `SOWN_AFTER_WINDOW` or `SOWN_BEFORE_WINDOW`, with `kind` (sowing, transplanting, planting), `days_outside`, `window_start` and `window_end`. Render it with `messages.render_warnings`. The warning does not change the advice.
- `depletion_mm`, `raw_mm`, `taw_mm` and `water_wallet_pct`, for the water wallet bar.
- `outlook`: 16 rows of date, ET0, rain, rain probability and projected depletion, for the outlook chart.
- `litres`, `gross_depth_mm`, `kwh`, `cost_inr`, `co2_kg`.
- Paddy also returns `pond_mm` and `dry_days`.

### Failure behaviour
| Situation | Engine behaviour |
|---|---|
| Observed day missing | Raises `MissingWeather`; the state is unchanged. Retry with archive data, or send "advice unavailable today" |
| No forecast | Still advises IRRIGATE if the field is past RAW or due its CRI irrigation; otherwise `NO_FORECAST_DATA` |
| Forecast has a gap in ET0 | Uses the days before the gap (`forecast_days` says how many) |
| Rain probability missing | That rain counts as not confident, so no SKIP is based on it |
| Before sowing / after harvest | `WAITING` / `SEASON_OVER`, with depth 0 (both have a message) |
| After the last irrigation date | `WAIT` / `IRRIGATION_STOPPED`, with the balance still reported |

### Timing convention
Each morning, `advance_field` applies every unprocessed day up to **yesterday** using observed weather plus check-ins, then decides **today's** advice from the forecast that starts today. When a farmer follows the advice, the water reaches the balance through their `WATERED` check-in. If they don't check in, Boond assumes no irrigation happened, which errs on the safe side.

## Other entry points
- `python -m engine.replay --weather replay/cache/ludhiana_actual_2021_22.json --crop wheat --sow 2021-11-05 --soil loam` runs the validation replay against the PAU baseline.
- `python -m engine.simulate ...` runs one policy over a season.
- `python -m engine.check_data` checks the data files and prints the Kc and TAW tables (run in CI).
- `engine.daily_engine.generate_daily_decision(...)` is the original one-day call (apply yesterday, decide today). It now wraps the same functions; use it for one-off checks, not for the job. Without a `sowing_date` it applies only the crop-day rules (no sowing-window warning, no calendar stop date).

## Known limits (state them in the writeup)
- There is no measured soil moisture. The balance is modelled (FAO-56) and corrected only by check-ins.
- The FAO-56 Kc climate adjustment is **not** implemented (`config.kc_climate_adjustment.enabled` must stay false).
- Heat-stage windows and paddy, cotton and sugarcane stage lengths are partly derived assumptions (see `docs/DATA_GUIDE.md`).
- In the replay, observed weather stood in for the forecast, and forecast rain was not trusted.
