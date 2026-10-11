#!/usr/bin/env python3
"""Build realistic mock data for the Boond dashboard from REAL 2021-22 weather.

Run:  python3 -I scripts/make_mocks.py      (stdlib only; works offline once cached)

What it does
------------
1. Loads daily weather for Ludhiana (30.90 N, 75.85 E), 2021-10-25 .. 2022-04-30, from
   the Open-Meteo Historical Weather API (ERA5 reanalysis). The raw response is cached
   in scripts/cache/ so reruns are offline. If the download fails we stop: no invented weather.
2. Runs a simplified FAO-56 wheat water balance (Boond Live Build Specification s.6)
   for a field sown 2021-11-10, plus a fixed-calendar baseline farmer (PAU timetable).
3. Writes FieldResponse snapshots
   (field-demo/irrigate/skip/wait/heat/waiting.json) picked from real days of this season.
   public/mock/replay.json comes from the real engine instead: scripts/make_replay.py.

Forecast honesty
----------------
There is no archived forecast here. The engine's "forecast" for day d is the ACTUAL
observed weather of the following days (a perfect forecast). Outlook rain_prob_pct is a
proxy derived from the observed rain amount (see rain_prob_proxy), not a forecast product.
Spec 13.1 suggests Open-Meteo's Historical Forecast archive for the real replay; these
mocks use observed weather in its place and say so in weather_source.
"""
import datetime as dt
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.dirname(HERE)
CACHE = os.path.join(HERE, 'cache', 'openmeteo_ludhiana_2021-22.json')
OUT = os.path.join(FRONTEND, 'public', 'mock')

LAT, LON = 30.90, 75.85
URL = ('https://archive-api.open-meteo.com/v1/archive?latitude=30.90&longitude=75.85'
       '&start_date=2021-10-25&end_date=2022-04-30'
       '&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration'
       '&timezone=Asia%2FKolkata')

# ---------------------------------------------------------------- field profile
SOWING = dt.date(2021, 11, 10)
AREA_ACRES = 1
LIFT_M = 30
PUMP_EFF = 0.4
SOIL = 'LOAM'
THETA_FC, THETA_WP = 0.25, 0.12          # spec 6.3, loam
PLACE = 'Ludhiana, Punjab'

# ---------------------------------------------------------------- crop (spec 6.2)
# Spec stage lengths are FAO-56 Table 11's 15/25/50/30 = 120 days. PAU's Package of
# Practices (Rabi 2025-26) lists timely-sown Punjab varieties maturing in ~145-158 days
# (e.g. PBW 725 ~154, HD 3086 ~155, PBW 826 ~148). A 120-day crop sown 10 Nov would be
# "mature" on 10 Mar and miss the whole March grain-filling period, so we keep the spec's
# 15/25/50/30 SHAPE but stretch it x1.25 to a 150-day season (FAO-56 Ch.6 says stage
# lengths should be adapted to local conditions). Set STAGE_LEN = (15, 25, 50, 30) for
# the strict spec values.
STAGE_LEN = (19, 31, 62, 38)            # initial, development, mid, late = 150 days
SEASON_DAYS = sum(STAGE_LEN)            # harvest at DAS 150 = 2022-04-09
KC_INI, KC_MID, KC_END = 0.3, 1.15, 0.3
ZR_MIN, ZR_MAX = 0.3, 1.0               # root depth grows over the development stage
P_TABLE = 0.55

# Phenology calendar used for stage labels and heat windows (days after sowing).
# ASSUMPTION, anchored on: PAU PoP Rabi 2025-26 (https://pau.edu/content/ccil/pf/pp_rabi.pdf):
# crown-root initiation ~3-4 weeks after sowing (first irrigation timing), varieties maturing
# in ~150 days, and "irrigate the timely sown crop up to the end of March to avoid ...
# unusual rise in temperature at grain filling"; PAU sowing-date trials at Ludhiana
# (Dhaliwal et al., Indian J. Agronomy) place grain filling of 10-Nov wheat in March.
# For a 10-Nov sowing this gives flowering ~13-28 Feb and grain filling ~1-30 Mar.
# Not a verified per-variety calendar: replace with GDD-based dates when available.
PHENO = [  # (stage, first DAS, last DAS)
    ('INITIAL', 0, 20),
    ('TILLERING', 21, 45),
    ('JOINTING', 46, 94),
    ('FLOWERING', 95, 110),
    ('GRAIN_FILLING', 111, 140),
    ('MATURITY', 141, 10_000),
]
# Heat thresholds, spec 6.5 (IMD MAUSAM paper cited in the concept doc): ~31 C at
# flowering, ~35 C during grain filling.
HEAT_WINDOWS = {'FLOWERING': 31.0, 'GRAIN_FILLING': 35.0}
HEAT_LOOKAHEAD = 3                      # warn if threshold reached in the next 3 days
LAST_IRRIGATION_DAS = 140               # PAU: irrigate timely sown crop up to end of March

# ---------------------------------------------------------------- decision config
LIGHT_MM = 25                           # heat-protection light irrigation (assumption)
MAX_DEPTH_MM = 75                       # practical max = PAU's 7.5 cm per irrigation
MEANINGFUL_RAIN_MM = 5                  # rain in next 3 days that cancels heat protection
HEAT_COOLDOWN_DAYS = 2                  # don't repeat heat protection on consecutive days
# Skip-for-rain (spec 6.6 + safety rule "never skip if D would cross RAW before the rain")
SKIP_LOOKAHEAD = 3                      # days (today included) the rain must arrive within
SKIP_MIN_RAIN_MM = 5                    # one day with at least this much rain ...
SKIP_MIN_PROB = 70                      # ... at at least this probability (proxy, see below)
SKIP_MIN_COVER = 0.5                    # effective rain refills >= half the deficit
SKIP_HOLD_DAYS = 3                      # and keeps D above RAW for 3 more days

# ---------------------------------------------------------------- water / energy / carbon
L_PER_MM_ACRE = 4047                    # 1 mm over 1 acre (4046.86 m2)

# ---------------------------------------------------------------- baseline farmer
# PAU Package of Practices for Crops of Punjab, Rabi 2025-26, Wheat > Irrigation:
# "The first irrigation should be relatively light and given after three weeks to October-
# sown crop and after four weeks to the crop sown later." Time-table (sandy loam or heavier,
# sown up to Nov 21), weeks after previous irrigation: 2nd 5-6, 3rd 5-6, 4th 4; 7.5 cm each.
# We take the mid-points (38 days) and apply them as a fixed calendar. PAU's own note to
# delay by 5 days per cm of rain (2 days after January) is NOT applied: this models a
# farmer who follows the calendar.
BASELINE_DAS = [28, 28 + 38, 28 + 38 + 38, 28 + 38 + 38 + 28]   # 28, 66, 104, 132
BASELINE_DEPTH_MM = 75

# Farmer check-in conversions (spec 5) - assumptions for the mocks only.
WATERED_MM = {'Light': 30, 'Normal': 55, 'Heavy': 75}   # PAU trials ~55-75 mm regular
RAIN_MM = {'Little': 5, 'Moderate': 15, 'Heavy': 30}


# ================================================================= weather
def load_weather():
    if not os.path.exists(CACHE):
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        try:
            with urllib.request.urlopen(URL, timeout=60) as r:
                raw = r.read()
            json.loads(raw)
        except Exception as e:  # noqa: BLE001
            sys.exit(f'Weather download failed ({e}). Not inventing weather; aborting.')
        with open(CACHE, 'wb') as f:
            f.write(raw)
    with open(CACHE, encoding='utf-8') as f:
        d = json.load(f)['daily']
    days = {}
    for i, t in enumerate(d['time']):
        vals = (d['temperature_2m_max'][i], d['temperature_2m_min'][i],
                d['precipitation_sum'][i], d['et0_fao_evapotranspiration'][i])
        if any(v is None for v in vals):
            sys.exit(f'Missing weather value on {t}; aborting.')
        days[dt.date.fromisoformat(t)] = {
            'tmax': vals[0], 'tmin': vals[1], 'rain': vals[2], 'et0': vals[3]}
    return days


# ================================================================= crop model
def stage_of(das):
    for name, a, b in PHENO:
        if a <= das <= b:
            return name
    return 'MATURITY'


def heat_threshold(das):
    return HEAT_WINDOWS.get(stage_of(das))


def kc_of(das):
    ini, dev, mid, late = STAGE_LEN
    if das < ini:
        return KC_INI
    if das < ini + dev:
        return KC_INI + (KC_MID - KC_INI) * (das - ini) / dev
    if das < ini + dev + mid:
        return KC_MID
    if das < SEASON_DAYS:
        return KC_MID + (KC_END - KC_MID) * (das - ini - dev - mid) / late
    return KC_END


def zr_of(das):
    ini, dev = STAGE_LEN[0], STAGE_LEN[1]
    if das <= ini:
        return ZR_MIN
    if das >= ini + dev:
        return ZR_MAX
    return ZR_MIN + (ZR_MAX - ZR_MIN) * (das - ini) / dev


def params(das, et0):
    """Daily crop/soil parameters: Kc, Zr, TAW, p, RAW, potential ETc."""
    kc = kc_of(das)
    zr = zr_of(das)
    taw = 1000 * (THETA_FC - THETA_WP) * zr
    etc = kc * et0
    p = min(0.8, max(0.1, P_TABLE + 0.04 * (5 - etc)))
    return {'kc': kc, 'zr': zr, 'taw': taw, 'p': p, 'raw': p * taw, 'etc': etc}


def step(D, das, w, irr):
    """One FAO-56 daily update from D (start of day). Returns (D_end, ks, etc_adj, peff)."""
    pr = params(das, w['et0'])
    peff = w['rain'] if w['rain'] >= 0.2 * w['et0'] else 0.0
    if D > pr['raw']:
        ks = max(0.0, min(1.0, (pr['taw'] - D) / ((1 - pr['p']) * pr['taw'])))
    else:
        ks = 1.0
    etc_adj = ks * pr['etc']
    D_end = min(pr['taw'], max(0.0, D - peff - irr + etc_adj))
    return D_end, ks, etc_adj, peff


def project(D, start, n, W, rain=True):
    """End-of-day depletion for days start..start+n-1 with no irrigation."""
    out = []
    for k in range(n):
        day = start + dt.timedelta(days=k)
        w = dict(W[day])
        if not rain:
            w['rain'] = 0.0
        D, ks, etc_adj, peff = step(D, (day - SOWING).days, w, 0)
        pr = params((day - SOWING).days, w['et0'])
        out.append({'date': day, 'D': D, 'raw': pr['raw'], 'taw': pr['taw'],
                    'etc': etc_adj, 'peff': peff, 'w': W[day]})
    return out


def round5(x):
    return int(5 * round(x / 5))


def rain_next3(d, W):
    return sum(W[d + dt.timedelta(days=k)]['rain'] for k in range(3))


def heat_warning(d, W):
    """Days within the next HEAT_LOOKAHEAD days where Tmax reaches the window threshold."""
    hits = []
    for k in range(1, HEAT_LOOKAHEAD + 1):
        day = d + dt.timedelta(days=k)
        thr = heat_threshold((day - SOWING).days)
        if thr is not None and day in W and W[day]['tmax'] >= thr:
            hits.append(day)
    return hits


def heat_risk(d, W, hits):
    if hits:
        return 'HIGH'
    for k in range(1, HEAT_LOOKAHEAD + 1):
        day = d + dt.timedelta(days=k)
        thr = heat_threshold((day - SOWING).days)
        if thr is not None and W[day]['tmax'] >= thr - 2:
            return 'MEDIUM'
    return 'LOW'


def skip_for_rain(D0, d, W, wet, dry):
    """Spec 6.6 skip rule, with the safety rule: never skip if D would cross RAW before
    the rain arrives. SKIP only if ALL hold:
      - without rain, D would cross RAW within SKIP_LOOKAHEAD days (otherwise it is a WAIT);
      - one forecast day in that window has rain >= SKIP_MIN_RAIN_MM at >= SKIP_MIN_PROB;
      - that rain falls no later than the day D would cross RAW, and the projection with
        rain stays above the stress line on every day before it;
      - the effective rain of that spell (that day and the SKIP_HOLD_DAYS after it) refills
        at least SKIP_MIN_COVER of the deficit just before it;
      - after the rain, the projection stays above the stress line for SKIP_HOLD_DAYS more days.
    """
    cross = next((k for k, x in enumerate(dry[:SKIP_LOOKAHEAD]) if x['D'] > x['raw']), None)
    if cross is None:
        return False
    for k in range(cross + 1):              # the rain must fall on or before the crossing day
        w = W[d + dt.timedelta(days=k)]
        if w['rain'] < SKIP_MIN_RAIN_MM or rain_prob_proxy(w['rain']) < SKIP_MIN_PROB:
            continue
        if any(x['D'] > x['raw'] for x in wet[:k]):
            return False                    # with the earlier rain, D still crosses first
        deficit = wet[k - 1]['D'] if k > 0 else D0
        peff = sum(x['peff'] for x in wet[k:k + 1 + SKIP_HOLD_DAYS])
        if peff >= SKIP_MIN_COVER * deficit and not any(
                x['D'] > x['raw'] for x in wet[:k + 1 + SKIP_HOLD_DAYS]):
            return True
    return False


def decide(d, D0, W, last_heat_day):
    """Spec 6.6 decision rules, in order. D0 = depletion at 06:00 (end of yesterday)."""
    das = (d - SOWING).days
    rain3 = rain_next3(d, W)
    hits = heat_warning(d, W)
    risk = heat_risk(d, W, hits)
    wet = project(D0, d, 17, W, rain=True)
    dry = project(D0, d, 3, W, rain=False)
    crosses_2d = any(x['D'] > x['raw'] for x in wet[:2])
    full_depth = min(MAX_DEPTH_MM, max(5, round5(wet[0]['D'])))
    res = {'action': 'WAIT', 'depth': 0, 'reason': 'HEALTHY', 'days_to_next': None,
           'rain3': rain3, 'risk': risk, 'heat_days': hits}

    if das > LAST_IRRIGATION_DAS:
        res['reason'] = 'CROP_MATURING'
        return res

    # 1. heat protection: light irrigation the evening before, only if no meaningful rain
    if hits and rain3 < MEANINGFUL_RAIN_MM and not (
            last_heat_day and (d - last_heat_day).days <= HEAT_COOLDOWN_DAYS):
        heat_stage = stage_of((hits[0] - SOWING).days)
        if crosses_2d:          # a full irrigation also protects against heat
            depth = full_depth
        else:
            depth = min(LIGHT_MM, round5(wet[0]['D']))
        if depth >= 10:
            res.update(action='HEAT_PROTECTION', depth=depth, reason=f'HEAT_{heat_stage}')
            return res
        res['reason'] = 'HEAT_SOIL_MOIST'   # soil already wet; fall through
    # 2. skip: dry soil would cross RAW within 3 days, but enough likely rain arrives first
    if skip_for_rain(D0, d, W, wet, dry):
        res.update(action='SKIP', reason='RAIN_COVERS')
        return res
    # 3. irrigate: D will cross RAW within 2 days
    if crosses_2d:
        res.update(action='IRRIGATE', depth=full_depth,
                   reason='BELOW_RAW' if D0 > params(das, W[d]['et0'])['raw'] else 'CROSSES_RAW_IN_2D')
        return res
    # 4. wait: days until the next likely irrigation
    for k, x in enumerate(wet):
        if x['D'] > x['raw']:
            res['days_to_next'] = max(1, k - 1)
            break
    return res


# ================================================================= numbers / text
def num(x, nd=1):
    """Round, and return an int when the value is whole (so JSON and text agree)."""
    r = round(x, nd)
    return int(r) if r == int(r) else r


def fmt(x):
    return str(num(x))


def wallet_pct(taw, dep):
    return round(100 * (taw - dep) / taw)


def litres_of(depth_mm):
    return int(round(depth_mm * L_PER_MM_ACRE * AREA_ACRES))


def kwh_of(litres):
    return litres / 1000 * 9.81 * LIFT_M / (3600 * PUMP_EFF)


STAGE_HI = {'FLOWERING': 'फसल में फूल आ रहे हैं', 'GRAIN_FILLING': 'फसल में दाना भर रहा है'}
STAGE_EN = {'FLOWERING': 'the crop is flowering', 'GRAIN_FILLING': 'the grain is filling'}


def advice(action, depth, rain3, pct, days_to_next, reason):
    """Template advice (spec 8). Digits in the text are only JSON numbers."""
    r = fmt(rain3)
    if action == 'IRRIGATE':
        if num(rain3) < 1:
            return {'hi': f'आज रात खेत में लगभग {depth} मिमी पानी दें। अगले तीन दिन बारिश की उम्मीद नहीं है।',
                    'en': f'Irrigate about {depth} mm tonight. No rain is expected in the next three days.'}
        return {'hi': f'आज रात खेत में लगभग {depth} मिमी पानी दें। अगले तीन दिन में सिर्फ़ {r} मिमी बारिश होगी, वह काफ़ी नहीं है।',
                'en': f'Irrigate about {depth} mm tonight. Only {r} mm of rain is expected in the next three days, which is not enough.'}
    if action == 'SKIP':
        return {'hi': f'आज पानी न दें। अगले तीन दिन में लगभग {r} मिमी बारिश होने वाली है, तब तक खेत में पानी काफ़ी है।',
                'en': f'Do not irrigate today. About {r} mm of rain is expected in the next three days, and the field has enough water until then.'}
    if action == 'HEAT_PROTECTION':
        st = reason.replace('HEAT_', '')
        light_hi = 'हल्का पानी' if depth <= LIGHT_MM else 'पानी'
        light_en = 'a light irrigation' if depth <= LIGHT_MM else 'an irrigation'
        return {'hi': f'अगले तीन दिन में तेज़ गर्मी आने वाली है और {STAGE_HI[st]}। आज शाम लगभग {depth} मिमी {light_hi} दें।',
                'en': f'Strong heat is due in the next three days while {STAGE_EN[st]}. Give {light_en} of about {depth} mm this evening.'}
    # WAIT
    if reason == 'CROP_MATURING':
        return {'hi': 'फसल पक रही है, अब पानी देने की ज़रूरत नहीं है।',
                'en': 'The crop is ripening; no more irrigation is needed.'}
    if reason == 'HEAT_SOIL_MOIST':
        return {'hi': f'आगे तेज़ गर्मी आने वाली है, पर खेत में अभी {pct}% पानी बचा है। आज पानी की ज़रूरत नहीं है।',
                'en': f'Strong heat is coming, but the field still holds {pct}% of its water. No irrigation is needed today.'}
    if days_to_next is None:
        return {'hi': f'आज पानी की ज़रूरत नहीं है। खेत में अभी {pct}% पानी बचा है, आने वाले दो हफ़्ते पानी की ज़रूरत नहीं दिखती।',
                'en': f'No irrigation needed today. The field still holds {pct}% of its water; none looks necessary for the next two weeks.'}
    unit = 'day' if days_to_next == 1 else 'days'
    return {'hi': f'आज पानी की ज़रूरत नहीं है। खेत में अभी {pct}% पानी बचा है, अगला पानी लगभग {days_to_next} दिन बाद देना होगा।',
            'en': f'No irrigation needed today. The field still holds {pct}% of its water; the next irrigation is likely in about {days_to_next} {unit}.'}


def rain_prob_proxy(rain):
    """NOT a forecast: a probability-like proxy derived from the observed rain amount."""
    if rain >= 5:
        return 90
    if rain >= 1:
        return 70
    if rain > 0:
        return 30
    return 5


# ================================================================= season simulation
def simulate(W, d_start=0.0):
    """d_start: depletion at sowing; 0 = root zone full after a pre-sowing irrigation."""
    days = [SOWING + dt.timedelta(days=k) for k in range(SEASON_DAYS + 1)]
    Db = Dbase = d_start
    last_heat = None
    rows = []
    for d in days:
        das = (d - SOWING).days
        w = W[d]
        pr = params(das, w['et0'])
        dec = decide(d, Db, W, last_heat)
        if dec['action'] == 'HEAT_PROTECTION':
            last_heat = d
        D_morning = Db
        Db, ks_b, _, _ = step(Db, das, w, dec['depth'])
        base_depth = BASELINE_DEPTH_MM if das in BASELINE_DAS else 0
        Dbase, ks_base, _, _ = step(Dbase, das, w, base_depth)
        rows.append({'date': d, 'das': das, 'w': w, 'pr': pr, 'dec': dec,
                     'D_morning': D_morning, 'D_end': Db, 'ks': ks_b,
                     'base_D': Dbase, 'base_depth': base_depth, 'base_ks': ks_base})
    return rows


# ================================================================= snapshots
FIELD_ACTIVE = {
    'id': 'F-test-1', 'label': 'Test field 1, Ludhiana (2021–22 weather)', 'is_test': True,
    'status': 'ACTIVE', 'crop': 'WHEAT', 'sowing_date': SOWING.isoformat(), 'soil': SOIL,
    'area_acres': AREA_ACRES, 'lift_m': LIFT_M, 'pump_eff': PUMP_EFF,
    'lat': LAT, 'lon': LON, 'place': PLACE,
}


def nearest(table, mm):
    return min(table, key=lambda k: abs(table[k] - mm))


def rain_choice(mm):
    return 'Little' if mm < 10 else 'Moderate' if mm < 25 else 'Heavy'


def engine_day(r):
    dec = r['dec']
    taw, dep = num(r['pr']['taw']), num(r['D_morning'])
    lit = litres_of(dec['depth'])
    return {
        'date': r['date'].isoformat(), 'action': dec['action'], 'depth_mm': dec['depth'],
        'stage': stage_of(r['das']), 'day_after_sowing': r['das'], 'heat_risk': dec['risk'],
        'rain_next_3d_mm': num(dec['rain3']), 'depletion_mm': dep, 'raw_mm': num(r['pr']['raw']),
        'taw_mm': taw, 'root_depth_m': num(r['pr']['zr'], 2),
        'water_wallet_pct': wallet_pct(taw, dep), 'reason_code': dec['reason'],
        'days_to_next_irrigation': dec['days_to_next'] if dec['action'] == 'WAIT' else None,
        'litres': lit, 'kwh': num(kwh_of(lit)),
    }


def snapshot(rows, idx, W, failed_offset=6):
    r = rows[idx]
    e = engine_day(r)
    e['advice_text'] = advice(e['action'], e['depth_mm'], e['rain_next_3d_mm'],
                              e['water_wallet_pct'], e['days_to_next_irrigation'], e['reason_code'])
    e['audio_url'] = {'hi': None, 'en': None}
    e['generated_at'] = f"{e['date']}T06:00:{11 + idx % 40:02d}+05:30"
    e['weather_stale'] = False

    # Outlook: 16 days from tomorrow, projected from this morning with NO irrigation.
    proj = project(r['D_morning'], r['date'], 17, W)[1:]
    outlook = []
    for x in proj:
        das = (x['date'] - SOWING).days
        outlook.append({
            'date': x['date'].isoformat(), 'tmax_c': num(x['w']['tmax']), 'tmin_c': num(x['w']['tmin']),
            'rain_mm': num(x['w']['rain']), 'rain_prob_pct': rain_prob_proxy(x['w']['rain']),
            'et0_mm': num(x['w']['et0'], 2), 'etc_mm': num(x['etc'], 2),
            'depletion_mm': num(x['D']), 'raw_mm': num(x['raw']), 'taw_mm': num(x['taw']),
            'heat_threshold_c': heat_threshold(das),
        })

    # History: previous 14 days, newest first, with farmer check-ins consistent with the sim.
    history, n_reports = [], 0
    for k in range(1, 15):
        h = rows[idx - k]
        he = engine_day(h)
        reports = []
        if he['depth_mm'] > 0 and n_reports < 4:
            ch = nearest(WATERED_MM, he['depth_mm'])
            reports.append({'type': 'WATERED', 'choice': ch, 'mm_assumed': WATERED_MM[ch],
                            'at': f"{he['date']}T{19 + k % 3}:{(17 * k) % 60:02d}:00+05:30"})
            n_reports += 1
        if h['w']['rain'] >= 2 and n_reports < 4:
            ch = rain_choice(h['w']['rain'])
            reports.append({'type': 'RAIN', 'choice': ch, 'mm_assumed': RAIN_MM[ch],
                            'at': f"{he['date']}T{16 + k % 3}:{(23 * k) % 60:02d}:00+05:30"})
            n_reports += 1
        history.append({
            'date': he['date'], 'action': he['action'], 'depth_mm': he['depth_mm'],
            'advice_text': advice(he['action'], he['depth_mm'], he['rain_next_3d_mm'],
                                  he['water_wallet_pct'], he['days_to_next_irrigation'],
                                  he['reason_code']),
            'delivery_status': 'DELIVERED', 'water_wallet_pct': he['water_wallet_pct'],
            'reports': reports,
        })
    # one failed delivery, on a quiet day without check-ins
    quiet = [i for i, h in enumerate(history) if not h['reports'] and h['action'] == 'WAIT']
    if quiet:
        history[quiet[min(failed_offset, len(quiet) - 1)]]['delivery_status'] = 'FAILED'
    return {'field': dict(FIELD_ACTIVE), 'today': e, 'outlook': outlook, 'history': history}


# Test field 3: same engine, same real 2021-22 weather, but sown 5 Nov on residual moisture
# after paddy (no pre-sowing irrigation), so 30% of the seedling root zone's water is already
# used at sowing. Its trajectory reaches the stress line just before the 5-8 Jan 2022 rains
# (24.3 + 8.2 + 59.6 mm), which gives a SKIP that passes the full safety rule. Only the field
# differs from test field 1; no weather is altered.
SKIP_FIELD_SOWING = dt.date(2021, 11, 5)
SKIP_FIELD_START_FRAC = 0.3
FIELD_SKIP = {**FIELD_ACTIVE, 'id': 'F-test-3',
              'label': 'Test field 3, Ludhiana (2021–22 weather, sown without palewa)',
              'sowing_date': SKIP_FIELD_SOWING.isoformat()}


def skip_field_snapshot(W):
    global SOWING
    main_sowing = SOWING
    SOWING = SKIP_FIELD_SOWING
    try:
        rows = simulate(W, d_start=SKIP_FIELD_START_FRAC * params(0, 1)['taw'])
        i = pick(rows, lambda r: r['dec']['action'] == 'SKIP')
        if i is None:
            sys.exit('No SKIP day for test field 3 either; not inventing one.')
        snap = snapshot(rows, i, W)
    finally:
        SOWING = main_sowing
    snap['field'] = dict(FIELD_SKIP)
    return snap, rows[i]


def waiting_snapshot():
    return {
        'field': {**FIELD_ACTIVE, 'id': 'F-test-2', 'label': 'Test field 2, Ludhiana',
                  'status': 'WAITING', 'sowing_date': '2026-11-08'},
        'today': None, 'outlook': [], 'history': [],
    }


def pick(rows, pred, prefer=None):
    cands = [i for i, r in enumerate(rows) if 14 <= i and pred(r)]
    if not cands:
        return None
    if prefer:
        cands.sort(key=prefer)
    return cands[0]


def main():
    W = load_weather()
    rows = simulate(W)
    os.makedirs(OUT, exist_ok=True)

    def write(name, obj):
        with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
            f.write('\n')

    act = lambda a: (lambda r: r['dec']['action'] == a)  # noqa: E731
    notes = []

    def n_reports(i):
        return sum(len(h['reports']) for h in snapshot(rows, i, W)['history'])

    heat_idx = [i for i, r in enumerate(rows) if r['dec']['action'] == 'HEAT_PROTECTION'
                and r['date'].month == 3]
    irr_idx = pick(rows, act('IRRIGATE'), prefer=lambda i: abs(rows[i]['das'] - 75))
    if heat_idx:
        # demo: the March heat-protection day whose history has the most check-ins
        demo_idx = max(heat_idx, key=lambda i: (n_reports(i), -i))
        others = [i for i in heat_idx if i != demo_idx]
        heat2 = others[0] if others else demo_idx
    else:
        notes.append('No HEAT_PROTECTION day in March; field-demo.json is an IRRIGATE day.')
        demo_idx = heat2 = irr_idx
    skip_idx = pick(rows, act('SKIP'))
    # wait: a healthy jointing-stage day, preferring one whose last two weeks had rain check-ins
    wait_c = [i for i, r in enumerate(rows) if i >= 14 and r['dec']['action'] == 'WAIT'
              and r['dec']['reason'] == 'HEALTHY' and stage_of(r['das']) == 'JOINTING']
    wait_idx = max(wait_c, key=lambda i: (min(n_reports(i), 4), -i))
    picks = {'demo': demo_idx, 'irrigate': irr_idx, 'wait': wait_idx, 'heat': heat2}
    if skip_idx is not None:
        picks['skip'] = skip_idx
    for name, i in picks.items():
        write(f'field-{name}.json', snapshot(rows, i, W))
    if skip_idx is None:
        # Test field 1 never meets the skip rule in 2021-22: its only near-RAW spell (late
        # Feb) gets 3.6 and 8.3 mm, too little and too late. Test field 3 runs the same
        # engine on the same real weather, sown on residual moisture; it has a real SKIP day.
        snap, r = skip_field_snapshot(W)
        write('field-skip.json', snap)
        notes.append(f"field-skip.json is TEST FIELD 3 (sown {SKIP_FIELD_SOWING}, "
                     f"{SKIP_FIELD_START_FRAC:.0%} of TAW used at sowing): {r['date']} DAS {r['das']} "
                     f"{r['dec']['action']} {r['dec']['reason']} D {r['D_morning']:.1f} "
                     f"RAW {r['pr']['raw']:.1f} rain3 {r['dec']['rain3']:.1f}")
    write('field-waiting.json', waiting_snapshot())

    # ---- report
    counts = {}
    for r in rows:
        counts[r['dec']['action']] = counts.get(r['dec']['action'], 0) + 1
    print('actions:', counts)
    for name, i in picks.items():
        r = rows[i]
        print(f"field-{name}: {r['date']} DAS {r['das']} {r['dec']['action']} "
              f"{r['dec']['depth']} mm {r['dec']['reason']}")
    for r in rows:
        if r['dec']['action'] != 'WAIT' or r['base_depth']:
            print('  ', r['date'], r['das'], r['dec']['action'], r['dec']['depth'], r['dec']['reason'],
                  'D', round(r['D_morning'], 1), 'RAW', round(r['pr']['raw'], 1),
                  'base', r['base_depth'])
    for n in notes:
        print('NOTE:', n)


if __name__ == '__main__':
    main()
