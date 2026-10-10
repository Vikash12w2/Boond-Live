// Adapter from the live backend (API Gateway, GET /fields/{token}) to the
// dashboard's FieldResponse. The response is the stored field profile plus
// `state` and `latest_advice`, which is the engine's advice dict
// (engine/field_runner.py on branch Boond_1). latest_advice is null until the
// daily job has run for the field.

import soils from '../../engine/soils.json'
import type { Action, FieldResponse, HeatRisk, Lang, OutlookDay, Soil, Stage, Today } from './types'

export interface LiveOutlookRow {
  date: string | null
  day_after_sowing?: number
  et0_mm: number
  rain_mm: number
  rain_prob: number | null // 0..1
  projected_depletion_mm?: number
  raw_mm?: number
  taw_mm?: number
}

export interface LiveAdvice {
  status?: 'WAITING' | 'ACTIVE' | 'SEASON_OVER'
  date?: string
  day_after_sowing?: number
  stage?: string // initial | development | mid | late | post_harvest
  heat_stage?: string | null // flowering | grain_filling | ...
  heat_risk?: string // LOW | HIGH | UNKNOWN
  max_forecast_tmax_c?: number | null
  action?: Action
  depth_mm?: number
  reason_code?: string
  depletion_mm?: number
  raw_mm?: number
  taw_mm?: number
  water_wallet_pct?: number
  crossing_day?: number | null
  outlook?: LiveOutlookRow[]
  litres?: number
  kwh?: number
  // Text the daily job may store next to the engine output (names not fixed yet).
  text?: string
  message?: string
  advice_text?: string | Partial<Record<Lang, string>>
  text_hi?: string
  text_en?: string
  audio_url?: string | null
  generated_at?: string
}

export interface LiveField {
  field_token: string
  crop: string
  crop_name?: string
  language: string
  sowing_date: string
  soil: string
  area_acres: number
  lift_m?: number
  pump_eff?: number
  pump_type?: string
  latitude: number
  longitude: number
  state?: { depletion_mm?: number; last_processed_date?: string }
  latest_advice: LiveAdvice | null
}

export interface RegisterBody {
  language: Lang
  latitude: number
  longitude: number
  crop: 'wheat'
  sowing_date: string
  soil: 'sandy' | 'loam' | 'clay'
  area_acres: number
  pump_type: 'electric'
  lift_m: number
}

const SOIL: Record<string, Soil> = { sandy: 'SANDY', loam: 'LOAM', clay: 'CLAY' }

// Engine growth stage + heat stage -> the dashboard's wheat stages.
function toStage(a: LiveAdvice): Stage {
  if (a.heat_stage === 'flowering') return 'FLOWERING'
  if (a.heat_stage === 'grain_filling') return 'GRAIN_FILLING'
  switch (a.stage) {
    case 'initial':
      return 'INITIAL'
    case 'development':
      return 'TILLERING'
    case 'mid':
      return 'JOINTING'
    default:
      return 'MATURITY' // late, post_harvest
  }
}

// Engine reason codes (engine/messages.json) -> the codes the Today hero explains.
// Unknown codes pass through; the hero then relies on the advice text.
function toReason(a: LiveAdvice): string {
  const code = a.reason_code ?? ''
  if (code === 'ALREADY_PAST_RAW') return 'BELOW_RAW'
  if (code === 'RAINFALL_EXPECTED') return 'RAIN_COVERS'
  if (code === 'HEALTHY_WATER_BALANCE' || code === 'CROSSES_RAW_LATER') return 'HEALTHY'
  if (code.startsWith('HEAT_RISK')) {
    if (a.heat_stage === 'flowering') return 'HEAT_FLOWERING'
    if (a.heat_stage === 'grain_filling') return 'HEAT_GRAIN_FILLING'
    return 'HEAT'
  }
  if (code === 'CROSSES_RAW_IN_2D') {
    // The engine's crossing_day counts today as day 1 (its forecast starts today);
    // the hero's CROSSES_RAW_IN_<n>D counts days from now (0 = today). Without a
    // crossing day the hero shows no reason line and the advice text carries it.
    return a.crossing_day == null ? '' : `CROSSES_RAW_IN_${Math.max(0, a.crossing_day - 1)}D`
  }
  return code
}

function toHeatRisk(a: LiveAdvice): HeatRisk {
  if (a.heat_risk === 'HIGH') return 'HIGH'
  // engine/heat_rules.py returns UNKNOWN only for an empty Tmax list. Forecast rows
  // with no Tmax come back as LOW with max_forecast_tmax_c null; inside a heat
  // window (heat_stage set) that means no data, not low risk.
  if (a.heat_risk === 'UNKNOWN' || (a.heat_stage && a.max_forecast_tmax_c == null)) return 'UNKNOWN'
  return 'LOW'
}

// Root depth behind the engine's TAW: TAW = 1000 (theta_fc - theta_wp) Zr
// (engine/water_balance.py), read back with the same soils.json the engine uses.
function rootDepthM(soil: string, tawMm: number): number {
  const s = (soils as unknown as Record<string, { theta_fc: number; theta_wp: number }>)[soil]
  return tawMm / (1000 * (s.theta_fc - s.theta_wp))
}

// Today's date in India, whatever timezone the phone is set to.
function istToday(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date())
}

const PLAIN: Record<Lang, Record<Action, (mm: number) => string>> = {
  hi: {
    IRRIGATE: (mm) => `आज लगभग ${mm} मिमी पानी दें।`,
    HEAT_PROTECTION: (mm) => `गर्मी से बचाव के लिए शाम को लगभग ${mm} मिमी हल्का पानी दें।`,
    SKIP: () => 'आज पानी न दें, बारिश की उम्मीद है।',
    WAIT: () => 'आज पानी की ज़रूरत नहीं है।',
  },
  en: {
    IRRIGATE: (mm) => `Irrigate about ${mm} mm today.`,
    HEAT_PROTECTION: (mm) => `Give about ${mm} mm of light irrigation this evening to protect against heat.`,
    SKIP: () => 'Do not irrigate today, rain is expected.',
    WAIT: () => 'No irrigation needed today.',
  },
}

function adviceText(a: LiveAdvice, lang: Lang): string {
  const at = a.advice_text
  const stored =
    (typeof at === 'object' && at ? at[lang] : undefined) ??
    (lang === 'hi' ? a.text_hi : a.text_en) ??
    (typeof at === 'string' ? at : undefined) ??
    a.text ??
    a.message
  if (stored) return stored
  const action = a.action ?? 'WAIT'
  return PLAIN[lang][action](Math.round(a.depth_mm ?? 0))
}

function sum3(rows: LiveOutlookRow[]): number {
  return rows.slice(0, 3).reduce((s, r) => s + (r.rain_mm || 0), 0)
}

function addDays(iso: string, n: number): string {
  const [y, m, d] = iso.split('-').map(Number)
  const t = new Date(Date.UTC(y, m - 1, d + n))
  return t.toISOString().slice(0, 10)
}

function toOutlook(a: LiveAdvice, today: string): OutlookDay[] {
  const rows = a.outlook ?? []
  // The engine's outlook starts today; the dashboard's starts tomorrow.
  return rows.slice(1).map((r, i) => ({
    date: r.date ?? addDays(today, i + 1),
    tmax_c: null, // the engine reports only the forecast maximum, not daily values
    tmin_c: null,
    rain_mm: r.rain_mm ?? 0,
    rain_prob_pct: Math.round((r.rain_prob ?? 0) * 100),
    et0_mm: r.et0_mm ?? 0,
    etc_mm: 0,
    depletion_mm: r.projected_depletion_mm ?? 0,
    raw_mm: r.raw_mm ?? a.raw_mm ?? 0,
    taw_mm: r.taw_mm ?? a.taw_mm ?? 1,
    heat_threshold_c: null,
  }))
}

export function toFieldResponse(raw: LiveField): FieldResponse {
  const a = raw.latest_advice
  const waiting = !a || a.status === 'WAITING' || !a.action
  const soilKey = SOIL[raw.soil] ? raw.soil : 'loam'
  const field = {
    id: raw.field_token,
    label: '',
    is_test: false,
    status: waiting ? ('WAITING' as const) : ('ACTIVE' as const),
    crop: 'WHEAT' as const,
    sowing_date: raw.sowing_date,
    soil: SOIL[raw.soil] ?? 'LOAM',
    area_acres: raw.area_acres,
    lift_m: raw.lift_m ?? 30,
    pump_eff: raw.pump_eff ?? 0.4,
    lat: raw.latitude,
    lon: raw.longitude,
    place: `${raw.latitude.toFixed(2)}°N, ${raw.longitude.toFixed(2)}°E`,
  }
  if (waiting || !a) return { field, today: null, outlook: [], history: [] }
  // The engine reports TAW for every active upland field; the wallet cannot be
  // drawn without it, so a response that lacks it is treated as broken.
  if (a.taw_mm == null) throw new Error('advice has no taw_mm')

  const date = a.date ?? istToday()
  const rows = a.outlook ?? []
  const today: Today = {
    date,
    action: a.action ?? 'WAIT',
    depth_mm: a.depth_mm ?? 0,
    stage: toStage(a),
    day_after_sowing: a.day_after_sowing ?? 0,
    heat_risk: toHeatRisk(a),
    rain_next_3d_mm: sum3(rows),
    depletion_mm: a.depletion_mm ?? 0,
    raw_mm: a.raw_mm ?? 0,
    taw_mm: a.taw_mm,
    root_depth_m: rootDepthM(soilKey, a.taw_mm),
    water_wallet_pct: Math.round(a.water_wallet_pct ?? 0),
    reason_code: toReason(a),
    days_to_next_irrigation: a.crossing_day ?? null,
    litres: a.litres ?? 0,
    kwh: a.kwh ?? 0,
    advice_text: { hi: adviceText(a, 'hi'), en: adviceText(a, 'en') },
    audio_url: { hi: a.audio_url ?? null, en: null },
    generated_at: a.generated_at ?? null,
    weather_stale: false,
  }
  return { field, today, outlook: toOutlook(a, date), history: [] }
}
