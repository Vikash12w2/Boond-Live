#!/usr/bin/env python3
"""Validate public/mock/*.json against src/types.ts (manual checks) plus sanity rules.

Run:  python3 -I scripts/validate_mocks.py      exits 1 on any failure.
"""
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK = os.path.join(os.path.dirname(HERE), 'public', 'mock')

ACTIONS = {'IRRIGATE', 'SKIP', 'WAIT', 'HEAT_PROTECTION'}
RISKS = {'LOW', 'MEDIUM', 'HIGH', 'UNKNOWN'}
STAGES = {'INITIAL', 'TILLERING', 'JOINTING', 'FLOWERING', 'GRAIN_FILLING', 'MATURITY'}
SOILS = {'SANDY', 'LOAM', 'CLAY'}
REPORT_TYPES = {'WATERED', 'RAIN', 'NOT_TODAY'}
DELIVERY = {'DELIVERED', 'FAILED', 'PENDING'}

errors = []


def err(where, msg):
    errors.append(f'{where}: {msg}')


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def is_date(v):
    try:
        dt.date.fromisoformat(v)
        return True
    except (TypeError, ValueError):
        return False


def is_ts(v):
    try:
        dt.datetime.fromisoformat(v)
        return True
    except (TypeError, ValueError):
        return False


# spec: {key: checker}. checker is a type tag, a set (enum), or a callable.
def check(obj, spec, where):
    if not isinstance(obj, dict):
        err(where, f'expected object, got {type(obj).__name__}')
        return
    for k in obj:
        if k not in spec:
            err(where, f'unexpected key {k!r}')
    for k, c in spec.items():
        if k not in obj:
            err(where, f'missing key {k!r}')
            continue
        v = obj[k]
        ok = True
        if c == 'num':
            ok = is_num(v)
        elif c == 'num?':
            ok = v is None or is_num(v)
        elif c == 'int':
            ok = isinstance(v, int) and not isinstance(v, bool)
        elif c == 'str':
            ok = isinstance(v, str) and v != ''
        elif c == 'str?':
            ok = v is None or isinstance(v, str)
        elif c == 'bool':
            ok = isinstance(v, bool)
        elif c == 'date':
            ok = is_date(v)
        elif c == 'ts':
            ok = is_ts(v)
        elif c == 'true':
            ok = v is True
        elif isinstance(c, set):
            ok = v in c
        elif callable(c):
            c(v, f'{where}.{k}')
            continue
        if not ok:
            err(where, f'{k}={v!r} fails {c if not isinstance(c, set) else sorted(c)}')


def lang(kind):
    def f(v, where):
        check(v, {'hi': kind, 'en': kind}, where)
    return f


def arr(item_fn):
    def f(v, where):
        if not isinstance(v, list):
            err(where, 'expected array')
            return
        for i, x in enumerate(v):
            item_fn(x, f'{where}[{i}]')
    return f


def obj(spec):
    return lambda v, where: check(v, spec, where)


FIELD = {'id': 'str', 'label': 'str', 'is_test': 'bool', 'status': {'ACTIVE', 'WAITING', 'SEASON_OVER'},
         'crop': {'WHEAT'}, 'sowing_date': 'date', 'soil': SOILS, 'area_acres': 'num',
         'lift_m': 'num', 'pump_eff': 'num', 'lat': 'num', 'lon': 'num', 'place': 'str'}
ENGINE_DAY = {'date': 'date', 'action': ACTIONS, 'depth_mm': 'num', 'stage': STAGES,
              'day_after_sowing': 'int', 'heat_risk': RISKS, 'rain_next_3d_mm': 'num',
              'depletion_mm': 'num', 'raw_mm': 'num', 'taw_mm': 'num', 'root_depth_m': 'num',
              'water_wallet_pct': 'num', 'reason_code': 'str', 'days_to_next_irrigation': 'num?',
              'litres': 'num', 'kwh': 'num'}
TODAY = {**ENGINE_DAY, 'advice_text': lang('str'), 'audio_url': lang('str?'),
         'generated_at': 'ts', 'weather_stale': 'bool'}
OUTLOOK = {'date': 'date', 'tmax_c': 'num', 'tmin_c': 'num', 'rain_mm': 'num',
           'rain_prob_pct': 'num', 'et0_mm': 'num', 'etc_mm': 'num', 'depletion_mm': 'num',
           'raw_mm': 'num', 'taw_mm': 'num', 'heat_threshold_c': 'num?'}
REPORT = {'type': REPORT_TYPES, 'choice': 'str', 'mm_assumed': 'num', 'at': 'ts'}
HISTORY = {'date': 'date', 'action': ACTIONS, 'depth_mm': 'num', 'advice_text': lang('str'),
           'delivery_status': DELIVERY, 'water_wallet_pct': 'num', 'reports': arr(obj(REPORT))}
TOTALS = {'litres': 'num', 'kwh': 'num', 'co2e_kg': 'num', 'irrigations': 'int',
          'stress_days': 'int', 'water_mm': 'num'}
REPLAY_DAY = {'date': 'date', 'day_after_sowing': 'int', 'stage': STAGES, 'tmax_c': 'num',
              'rain_mm': 'num', 'et0_mm': 'num', 'raw_mm': 'num', 'taw_mm': 'num',
              'heat_threshold_c': 'num?',
              'boond': obj({'depletion_mm': 'num', 'action': ACTIONS, 'depth_mm': 'num', 'ks': 'num'}),
              'baseline': obj({'depletion_mm': 'num', 'depth_mm': 'num', 'ks': 'num'})}
HEAT_EVENT = {'date': 'date', 'warned_on': 'date', 'tmax_c': 'num', 'stage': STAGES}
REPLAY = {'is_simulation': 'true', 'place': 'str', 'lat': 'num', 'lon': 'num',
          'season': obj({'start': 'date', 'end': 'date'}), 'sowing_date': 'date', 'soil': SOILS,
          'area_acres': 'num', 'lift_m': 'num', 'pump_eff': 'num', 'weather_source': 'str',
          'baseline': obj({'name': 'str', 'source': 'str', 'description': 'str'}),
          'days': arr(obj(REPLAY_DAY)), 'heat_events': arr(obj(HEAT_EVENT)),
          'totals': obj({'boond': obj(TOTALS), 'baseline': obj(TOTALS)})}

NUM_RE = re.compile(r'\d+(?:\.\d+)?')


def numbers_in(text):
    return [float(x) for x in NUM_RE.findall(text)]


def text_numbers_ok(texts, allowed, where):
    allowed = {round(float(a), 2) for a in allowed if is_num(a)}
    for lg, t in texts.items():
        for n in numbers_in(t):
            if round(n, 2) not in allowed:
                err(where, f'advice_text.{lg} number {n} not in JSON {sorted(allowed)}')


def wallet_ok(taw, dep, pct, where):
    if not 0 <= dep <= taw:
        err(where, f'depletion {dep} outside 0..taw {taw}')
    want = round(100 * (taw - dep) / taw)
    if pct != want:
        err(where, f'water_wallet_pct {pct} != {want}')


def kwh_of(litres, lift, eff):
    return litres / 1000 * 9.81 * lift / (3600 * eff)


def validate_replay(r):
    check(r, REPLAY, 'replay')
    days = r['days']
    for i, d in enumerate(days):
        w = f'replay.days[{i}]'
        for side in ('boond', 'baseline'):
            dep = d[side]['depletion_mm']
            if not 0 <= dep <= d['taw_mm']:
                err(w, f'{side} depletion {dep} outside 0..{d["taw_mm"]}')
            if not 0 <= d[side]['ks'] <= 1:
                err(w, f'{side} ks out of range')
        if d['raw_mm'] > d['taw_mm']:
            err(w, 'raw > taw')
        if (d['boond']['depth_mm'] > 0) != (d['boond']['action'] in ('IRRIGATE', 'HEAT_PROTECTION')):
            err(w, 'depth/action mismatch')
        if i and dt.date.fromisoformat(d['date']) - dt.date.fromisoformat(days[i - 1]['date']) != dt.timedelta(days=1):
            err(w, 'dates not consecutive')
    for side in ('boond', 'baseline'):
        t = r['totals'][side]
        depths = [d[side]['depth_mm'] for d in days]
        if abs(t['water_mm'] - sum(depths)) > 0.05:
            err(f'totals.{side}', 'water_mm != sum of depths')
        if t['irrigations'] != sum(1 for x in depths if x > 0):
            err(f'totals.{side}', 'irrigations count mismatch')
        if t['stress_days'] != sum(1 for d in days if d[side]['ks'] < 1):
            err(f'totals.{side}', 'stress_days != count(ks < 1)')
        if abs(t['kwh'] - kwh_of(t['litres'], r['lift_m'], r['pump_eff'])) > 0.06:
            err(f'totals.{side}', 'kwh inconsistent with litres')
    for e in r['heat_events']:
        if not e['warned_on'] <= e['date']:
            err('heat_events', f'warned after event {e}')
    return {d['date']: d for d in days}


def skip_is_safe(t, out, w):
    """Safety rule: never skip if D would cross RAW before the rain arrives, and the
    rain must be real (>= 5 mm at >= 70%) and refill a good share of the deficit."""
    rain = next((i for i, o in enumerate(out[:3]) if o['rain_mm'] >= 5 and o['rain_prob_pct'] >= 70), None)
    if rain is None and t['rain_next_3d_mm'] < 5:
        err(w, 'SKIP without >= 5 mm of likely rain in the next 3 days')
        return
    if t['depletion_mm'] > t['raw_mm']:
        err(w, 'SKIP while already below the stress line')
    stop = rain if rain is not None else 0
    for i, o in enumerate(out[:stop]):
        if o['depletion_mm'] > o['raw_mm']:
            err(f'{w}.outlook[{i}]', 'SKIP but D crosses RAW before the rain arrives')
    for i, o in enumerate(out[:7]):
        if o['depletion_mm'] > o['raw_mm']:
            err(f'{w}.outlook[{i}]', 'SKIP but D crosses RAW within a week')
    spell = sum(o['rain_mm'] for o in out[:7])
    if spell < 0.5 * t['depletion_mm']:
        err(w, f'SKIP but the week\'s rain {spell:.1f} mm covers < half the deficit')


def validate_field(name, f, replay_by_date, replay_sowing):
    w = name
    # Cross-check actions and heat windows only for the replayed field; other test fields
    # share the weather but not the crop calendar or soil state.
    same_field = f['field']['sowing_date'] == replay_sowing
    check(f, {'field': obj(FIELD), 'today': lambda v, x: None, 'outlook': lambda v, x: None,
              'history': lambda v, x: None}, w)
    if not f['field'].get('is_test'):
        err(w, 'mock fields must be is_test')
    if f['field']['status'] == 'WAITING':
        if f['today'] is not None or f['outlook'] or f['history']:
            err(w, 'WAITING field must have today null and empty outlook/history')
        if f['field']['sowing_date'] <= dt.date.today().isoformat():
            err(w, 'WAITING field sowing_date should be in the future')
        return
    t = f['today']
    check(t, TODAY, f'{w}.today')
    wallet_ok(t['taw_mm'], t['depletion_mm'], t['water_wallet_pct'], f'{w}.today')
    if t['raw_mm'] > t['taw_mm']:
        err(w, 'raw > taw')
    if (t['depth_mm'] > 0) != (t['action'] in ('IRRIGATE', 'HEAT_PROTECTION')):
        err(w, 'today depth/action mismatch')
    if t['action'] != 'WAIT' and t['days_to_next_irrigation'] is not None:
        err(w, 'days_to_next_irrigation should be null unless WAIT')
    if abs(t['litres'] - t['depth_mm'] * 4047 * f['field']['area_acres']) > 1:
        err(w, 'litres != depth * 4047 * area')
    if abs(t['kwh'] - kwh_of(t['litres'], f['field']['lift_m'], f['field']['pump_eff'])) > 0.06:
        err(w, 'kwh inconsistent')
    text_numbers_ok(t['advice_text'], [v for v in t.values() if is_num(v)], f'{w}.today')
    rd = replay_by_date.get(t['date'])
    if same_field and rd and rd['boond']['action'] != t['action']:
        err(w, f'today action {t["action"]} != replay {rd["boond"]["action"]}')

    out = f['outlook']
    if t['action'] == 'SKIP':
        skip_is_safe(t, out, w)
    arr(obj(OUTLOOK))(out, f'{w}.outlook')
    if len(out) != 16:
        err(w, f'outlook has {len(out)} days, want 16')
    day0 = dt.date.fromisoformat(t['date'])
    for i, o in enumerate(out):
        if o['date'] != (day0 + dt.timedelta(days=i + 1)).isoformat():
            err(f'{w}.outlook[{i}]', 'dates must start tomorrow and be consecutive')
        if not 0 <= o['depletion_mm'] <= o['taw_mm']:
            err(f'{w}.outlook[{i}]', 'depletion outside 0..taw')
        if not 0 <= o['rain_prob_pct'] <= 100:
            err(f'{w}.outlook[{i}]', 'rain_prob_pct out of range')
        rd = replay_by_date.get(o['date'])
        if same_field and rd and rd['heat_threshold_c'] != o['heat_threshold_c']:
            err(f'{w}.outlook[{i}]', 'heat_threshold_c disagrees with replay')

    hist = f['history']
    arr(obj(HISTORY))(hist, f'{w}.history')
    if len(hist) != 14:
        err(w, f'history has {len(hist)} days, want 14')
    for i, h in enumerate(hist):
        hw = f'{w}.history[{i}]'
        if h['date'] != (day0 - dt.timedelta(days=i + 1)).isoformat():
            err(hw, 'history must be the previous days, newest first')
        if not 0 <= h['water_wallet_pct'] <= 100:
            err(hw, 'wallet pct out of range')
        rd = replay_by_date.get(h['date'])
        allowed = [h['depth_mm'], h['water_wallet_pct']]
        if rd:
            if same_field and (rd['boond']['action'] != h['action'] or rd['boond']['depth_mm'] != h['depth_mm']):
                err(hw, 'history disagrees with replay')
            i0 = list(replay_by_date).index(h['date'])
            nxt = list(replay_by_date.values())[i0:i0 + 3]
            allowed.append(round(sum(x['rain_mm'] for x in nxt), 1))
            # days-to-next is not in HistoryDay; accept 1..16 for WAIT text
            if h['action'] == 'WAIT':
                allowed += list(range(1, 17))
        text_numbers_ok(h['advice_text'], allowed, hw)
        for rep in h.get('reports') or []:
            if rep['type'] == 'WATERED' and h['depth_mm'] == 0:
                err(hw, 'WATERED report on a day the sim did not irrigate')
            if rep['type'] == 'RAIN' and rd and rd['rain_mm'] < 1:
                err(hw, 'RAIN report on a dry day')
    if sum(1 for h in hist if h['delivery_status'] == 'FAILED') > 1:
        err(w, 'more than one FAILED delivery')
    return sum(len(h.get('reports') or []) for h in hist)


def main():
    with open(os.path.join(MOCK, 'replay.json'), encoding='utf-8') as fh:
        replay = json.load(fh)
    by_date = validate_replay(replay)
    summary = []
    for fn in sorted(os.listdir(MOCK)):
        if not (fn.startswith('field-') and fn.endswith('.json')):
            continue
        with open(os.path.join(MOCK, fn), encoding='utf-8') as fh:
            f = json.load(fh)
        n = validate_field(fn, f, by_date, replay['sowing_date'])
        t = f['today']
        summary.append(f'{fn}: ' + (f"{t['date']} {t['action']} {t['depth_mm']} mm, "
                                    f"wallet {t['water_wallet_pct']}%, {n} reports"
                                    if t else 'WAITING'))
    print('\n'.join(summary))
    if errors:
        print(f'\n{len(errors)} problem(s):')
        print('\n'.join(errors))
        sys.exit(1)
    print('\nAll mocks valid.')


if __name__ == '__main__':
    main()
