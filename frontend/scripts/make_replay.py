#!/usr/bin/env python3
"""Build public/mock/replay.json (ReplayResponse) from the real engine.

Run from any directory (paths are relative to this file):

    python3 -I frontend/scripts/make_replay.py

It runs engine.replay.replay() on the cached 2021-22 Ludhiana weather, the same
run as `python replay/replay.py --weather replay/cache/ludhiana_actual_2021_22.json
--crop wheat --sow 2021-11-05 --soil loam`, and reshapes the result for the
dashboard's replay page. Per-day RAW and TAW, stages and heat thresholds are
computed with the engine's own functions, so every number on the page comes
from the engine. The script stops if its totals disagree with the engine's.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.data import get_setting, load_json, select_profile  # noqa: E402
from engine.heat_rules import get_heat_windows_for_day  # noqa: E402
from engine.kc import get_stage  # noqa: E402
from engine.replay import replay  # noqa: E402
from engine.resources import gross_depth_mm, irrigation_volume_litres  # noqa: E402
from engine.water_balance import (  # noqa: E402
    calculate_kc_etc,
    calculate_p,
    calculate_raw,
    calculate_taw,
    get_root_depth,
)

WEATHER = ROOT / 'replay' / 'cache' / 'ludhiana_actual_2021_22.json'
OUT = ROOT / 'frontend' / 'public' / 'mock' / 'replay.json'
PLACE = 'Ludhiana'  # the cached weather is Open-Meteo's grid point for Ludhiana
SOW = date(2021, 11, 5)
SOIL = 'loam'
AREA_ACRES = 1.0  # engine.simulate.simulate_season defaults
LIFT_M = 30.0

# Engine growth stages -> the dashboard's wheat stages (same mapping as src/live.ts).
FAO_TO_STAGE = {'initial': 'INITIAL', 'development': 'TILLERING', 'mid': 'JOINTING'}
HEAT_TO_STAGE = {'flowering': 'FLOWERING', 'grain_filling': 'GRAIN_FILLING'}


def stage(day, crop):
    windows = get_heat_windows_for_day(day, crop)
    if windows:
        return HEAT_TO_STAGE[windows[0]['name']]
    return FAO_TO_STAGE.get(get_stage(day, crop), 'MATURITY')


def heat_threshold(day, crop):
    windows = get_heat_windows_for_day(day, crop)
    return windows[0]['tmax_threshold_c'] if windows else None


def raw_taw(day, et0, crop):
    """RAW and TAW exactly as engine.water_balance.calculate_daily_balance computes them."""
    taw = calculate_taw(SOIL, get_root_depth(day, crop))
    _, etc = calculate_kc_etc(day, et0, crop)
    return calculate_raw(taw, calculate_p(etc, crop=crop, day_after_sowing=day)), taw


def totals(summary, days):
    litres = irrigation_volume_litres(gross_depth_mm(summary['irrigation_mm']), AREA_ACRES)
    out = {
        'litres': round(litres),
        'kwh': summary['pump_kwh'],
        'co2e_kg': summary['co2_kg'],
        'irrigations': summary['irrigation_events'],
        'stress_days': summary['stress_days'],
        'water_mm': summary['irrigation_mm'],
    }
    # The page recomputes these from days[]; they must agree with the engine.
    depths = [d['irrigation_mm'] for d in days]
    assert abs(sum(depths) - out['water_mm']) < 0.05, ('water', sum(depths), out['water_mm'])
    assert sum(1 for x in depths if x > 0) == out['irrigations'], 'irrigation count'
    assert sum(1 for d in days if d['ks'] < 1) == out['stress_days'], 'stress days'
    return out


def heat_events(rows, boond_days, crop, window_days):
    """
    First day of each run of days at or above a heat threshold, with the day Boond
    first raised a heat alert (reason HEAT_RISK*) in the window_days before it.
    Hot spells Boond did not warn about are left out of heat_events (the page
    labels each event "Boond warned on ..."); they still show on the chart,
    which plots Tmax against the threshold every day. They are printed below.
    """
    reason = {d['date']: d['reason_code'] for d in boond_days}
    events, missed = [], []
    hot_before = False
    for r in rows:
        threshold = r['heat_threshold_c']
        hot = threshold is not None and r['tmax_c'] is not None and r['tmax_c'] >= threshold
        if hot and not hot_before:
            when = date.fromisoformat(r['date'])
            warned = next(
                (d for k in range(window_days, -1, -1)
                 if reason.get(d := (when - timedelta(days=k)).isoformat(), '').startswith('HEAT_RISK')),
                None,
            )
            event = {'date': r['date'], 'tmax_c': r['tmax_c'], 'stage': r['stage']}
            if warned:
                events.append({**event, 'warned_on': warned})
            else:
                missed.append({**event, 'boond_reason_that_day': reason.get(r['date'])})
        hot_before = hot
    return events, missed


def main():
    weather = json.loads(WEATHER.read_text())
    crop = select_profile('wheat', SOW)
    result = replay(weather, crop, SOW, SOIL)
    daily = weather['daily']
    index = {d: i for i, d in enumerate(daily['date'])}

    rows = []
    for b, f in zip(result['boond_days'], result['baseline_days']):
        assert b['date'] == f['date']
        i = index[b['date']]
        day = b['day']
        raw, taw = raw_taw(day, daily['et0_mm'][i], crop)
        assert (b['irrigation_mm'] > 0) == (b['action'] in ('IRRIGATE', 'HEAT_PROTECTION')), b
        rows.append({
            'date': b['date'],
            'day_after_sowing': day,
            'stage': stage(day, crop),
            'tmax_c': daily['tmax_c'][i],
            'rain_mm': daily['rain_mm'][i],
            'et0_mm': daily['et0_mm'][i],
            'raw_mm': round(raw, 2),
            'taw_mm': round(taw, 2),
            'heat_threshold_c': heat_threshold(day, crop),
            'boond': {'depletion_mm': b['depletion_mm'], 'action': b['action'],
                      'depth_mm': b['irrigation_mm'], 'ks': b['ks']},
            'baseline': {'depletion_mm': f['depletion_mm'], 'depth_mm': f['irrigation_mm'], 'ks': f['ks']},
        })

    events, missed = heat_events(rows, result['boond_days'], crop, get_setting('heat', 'forecast_window_days'))
    plan = load_json('baseline.json')['wheat']
    weeks = plan['later_irrigations_weeks_after_previous']['sown_up_to_nov_21']
    rain_rule = plan['rain_rule']
    out = {
        'is_simulation': True,
        'place': PLACE,
        'lat': round(weather['latitude'], 2),
        'lon': round(weather['longitude'], 2),
        'season': {'start': rows[0]['date'], 'end': rows[-1]['date']},
        'sowing_date': SOW.isoformat(),
        'soil': SOIL.upper(),
        'area_acres': AREA_ACRES,
        'lift_m': LIFT_M,
        'pump_eff': get_setting('energy', 'default_pump_efficiency'),
        'weather_source': (
            f"{weather['source']} (ERA5 reanalysis): observed daily weather for 2021-22. Boond was "
            "given the following days' observed weather as its forecast (perfect foresight) and did "
            "not trust forecast rain, because the archive has no rain probability."
        ),
        'baseline': {
            'name': 'PAU calendar',
            'source': result['baseline_source'],
            'description': (
                f"PAU schedule for wheat sown by 21 Nov: a first irrigation of "
                f"{plan['first_irrigation']['depth_mm']} mm on day {plan['first_irrigation']['day_if_sown_later']}, "
                f"then {plan['later_depth_mm']} mm irrigations {weeks[0]}, {weeks[1]} and {weeks[2]} weeks apart "
                f"(mid-points of PAU's ranges). Each interval is extended by "
                f"{rain_rule['delay_days_per_cm_rain_until_jan_31']} days per cm of rain until 31 January and "
                f"{rain_rule['delay_days_per_cm_rain_after_jan_31']} days after, crediting at most "
                f"{rain_rule['max_rain_credit_mm_per_interval']} mm of rain per interval. No irrigation after "
                f"{plan['stop_irrigation']['timely_sown']} (MM-DD). Litres and kWh count the pumped water "
                f"(net depth / {get_setting('irrigation', 'application_efficiency')} application efficiency)."
            ),
        },
        'days': rows,
        'heat_events': events,
        'totals': {
            'boond': totals(result['boond'], result['boond_days']),
            'baseline': totals(result['baseline'], result['baseline_days']),
        },
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

    print(f'wrote {OUT.relative_to(ROOT)} ({crop}, sown {SOW}, {SOIL})')
    for side in ('boond', 'baseline'):
        print(f'{side:9}', out['totals'][side])
    print('heat events (warned):', events)
    for m in missed:
        print('NOTE: hot spell with no Boond warning:', m)


if __name__ == '__main__':
    main()
