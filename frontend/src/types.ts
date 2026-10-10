// Data contract between the dashboard and the backend read API.
// Shapes follow the Boond Live Build Specification (sections 6.8, 9, 10.2).
// GET /field/{token} -> FieldResponse, GET /replay -> ReplayResponse.

export type Action = 'IRRIGATE' | 'SKIP' | 'WAIT' | 'HEAT_PROTECTION'
// UNKNOWN: inside a heat-sensitive stage with no forecast Tmax (engine/heat_rules.py).
// MEDIUM is produced only by scripts/make_mocks.py; the engine never emits it.
export type HeatRisk = 'LOW' | 'MEDIUM' | 'HIGH' | 'UNKNOWN'
export type Stage = 'INITIAL' | 'TILLERING' | 'JOINTING' | 'FLOWERING' | 'GRAIN_FILLING' | 'MATURITY'
export type Soil = 'SANDY' | 'LOAM' | 'CLAY'
export type Lang = 'hi' | 'en'

export interface FieldProfile {
  id: string
  label: string // e.g. "Test field 1, Ludhiana"
  is_test: boolean // seeded/test fields must be labelled as such
  status: 'ACTIVE' | 'WAITING'
  crop: 'WHEAT'
  sowing_date: string // YYYY-MM-DD
  soil: Soil
  area_acres: number
  lift_m: number
  pump_eff: number // 0..1
  lat: number // rounded to 2 decimals
  lon: number
  place: string // village / district name for display
}

// Engine output for one day (spec 6.8) plus delivery fields.
export interface EngineDay {
  date: string
  action: Action
  depth_mm: number // 0 unless IRRIGATE / HEAT_PROTECTION
  stage: Stage
  day_after_sowing: number
  heat_risk: HeatRisk
  rain_next_3d_mm: number
  depletion_mm: number
  raw_mm: number
  taw_mm: number
  root_depth_m: number
  water_wallet_pct: number // 0..100, share of TAW still available
  reason_code: string // e.g. CROSSES_RAW_IN_2D, RAIN_COVERS, HEALTHY, HEAT_FLOWERING
  days_to_next_irrigation: number | null // for WAIT
  litres: number
  kwh: number
}

export interface Today extends EngineDay {
  advice_text: Record<Lang, string> // Bedrock-rewritten or template text
  audio_url: Record<Lang, string | null> // Polly MP3, null if unavailable
  generated_at: string | null // ISO timestamp; null when the backend did not record it
  weather_stale: boolean // true if a cached forecast was used
}

export interface OutlookDay {
  date: string
  tmax_c: number | null // null when the backend reports no daily temperature
  tmin_c: number | null
  rain_mm: number
  rain_prob_pct: number
  et0_mm: number
  etc_mm: number
  depletion_mm: number // projected, assuming no irrigation
  raw_mm: number
  taw_mm: number
  heat_threshold_c: number | null // set only inside a sensitive stage window
}

export type ReportType = 'WATERED' | 'RAIN' | 'NOT_TODAY'

export interface FarmerReport {
  type: ReportType
  choice: string // verbatim choice, e.g. "Normal", "Little"
  mm_assumed: number
  at: string // ISO timestamp
}

export interface HistoryDay {
  date: string
  action: Action
  depth_mm: number
  advice_text: Record<Lang, string>
  delivery_status: 'DELIVERED' | 'FAILED' | 'PENDING'
  water_wallet_pct: number
  reports: FarmerReport[]
}

export interface SeasonTotals {
  litres: number
  kwh: number
  co2e_kg: number
  irrigations: number
  stress_days: number
  water_mm: number
}

export interface FieldResponse {
  field: FieldProfile
  today: Today | null // null while status is WAITING (not sown yet)
  outlook: OutlookDay[] // 16 days starting tomorrow (empty while WAITING)
  history: HistoryDay[] // newest first
}

export interface ReplayDay {
  date: string
  day_after_sowing: number
  stage: Stage
  tmax_c: number
  rain_mm: number
  et0_mm: number
  raw_mm: number
  taw_mm: number
  heat_threshold_c: number | null
  boond: { depletion_mm: number; action: Action; depth_mm: number; ks: number }
  baseline: { depletion_mm: number; depth_mm: number; ks: number }
}

export interface HeatEvent {
  date: string // first day at or above threshold
  warned_on: string // day Boond raised the warning
  tmax_c: number
  stage: Stage
}

export interface ReplayResponse {
  is_simulation: true
  place: string
  lat: number
  lon: number
  season: { start: string; end: string }
  sowing_date: string
  soil: Soil
  area_acres: number
  lift_m: number
  pump_eff: number
  weather_source: string // e.g. "Open-Meteo archive (ERA5)"
  baseline: { name: string; source: string; description: string }
  days: ReplayDay[]
  heat_events: HeatEvent[]
  totals: { boond: SeasonTotals; baseline: SeasonTotals }
}
