import type { Lang, ReplayDay, ReplayResponse } from '../../types'
import { LITRES_PER_MM_ACRE, parseDate } from '../../format'

// Pure derivations for the replay page. Everything the page shows is computed
// from days[] so the totals move with the slider; the per-mm factors are taken
// from the backend's season totals so the last day matches them exactly.

export interface Totals {
  water_mm: number
  litres: number
  kwh: number
  co2e_kg: number
  irrigations: number
  stress_days: number
}

export interface Cumulative {
  boond: Totals[]
  baseline: Totals[]
}

// Fallback grid factor, only used if the backend reports zero energy for both runs.
const FALLBACK_CO2_PER_KWH = 0.71

function factors(r: ReplayResponse) {
  const t = r.totals.boond.water_mm > 0 ? r.totals.boond : r.totals.baseline
  const litresPerMm = t.water_mm > 0 ? t.litres / t.water_mm : LITRES_PER_MM_ACRE * r.area_acres
  const kwhPerMm =
    t.water_mm > 0 && t.kwh > 0
      ? t.kwh / t.water_mm
      : ((litresPerMm / 1000) * 9.81 * r.lift_m) / (3600 * r.pump_eff)
  const co2PerKwh = t.kwh > 0 ? t.co2e_kg / t.kwh : FALLBACK_CO2_PER_KWH
  return { litresPerMm, kwhPerMm, co2PerKwh }
}

// Ks below 1 means the crop is water stressed that day.
const STRESSED = 0.999

export function cumulative(r: ReplayResponse): Cumulative {
  const f = factors(r)
  const run = (pick: (d: ReplayDay) => { depth_mm: number; ks: number }) => {
    let mm = 0
    let n = 0
    let stress = 0
    return r.days.map((d) => {
      const s = pick(d)
      if (s.depth_mm > 0) {
        mm += s.depth_mm
        n += 1
      }
      if (s.ks < STRESSED) stress += 1
      const kwh = mm * f.kwhPerMm
      return {
        water_mm: mm,
        litres: mm * f.litresPerMm,
        kwh,
        co2e_kg: kwh * f.co2PerKwh,
        irrigations: n,
        stress_days: stress,
      }
    })
  }
  return { boond: run((d) => d.boond), baseline: run((d) => d.baseline) }
}

// Share of the root zone's available water still in the soil, 0..100.
export function waterPct(taw: number, depletion: number): number {
  if (taw <= 0) return 0
  return Math.max(0, Math.min(100, ((taw - depletion) / taw) * 100))
}

// Below this share the crop is thirsty (depletion beyond RAW).
export function stressPct(d: ReplayDay): number {
  if (d.taw_mm <= 0) return 0
  return Math.max(0, Math.min(100, ((d.taw_mm - d.raw_mm) / d.taw_mm) * 100))
}

export function daysBetween(fromIso: string, toIso: string): number {
  return Math.round((parseDate(toIso).getTime() - parseDate(fromIso).getTime()) / 86_400_000)
}

const locale = (lang: Lang) => (lang === 'hi' ? 'hi-IN' : 'en-IN')

export function dateWithYear(iso: string, lang: Lang): string {
  return new Intl.DateTimeFormat(locale(lang), { day: 'numeric', month: 'long', year: 'numeric' }).format(parseDate(iso))
}

export function dayMonthLong(iso: string, lang: Lang): string {
  return new Intl.DateTimeFormat(locale(lang), { day: 'numeric', month: 'long' }).format(parseDate(iso))
}

export function monthShort(iso: string, lang: Lang): string {
  return new Intl.DateTimeFormat(locale(lang), { month: 'short' }).format(parseDate(iso))
}
