import type { Lang } from './types'

const locale = (lang: Lang) => (lang === 'hi' ? 'hi-IN' : 'en-IN')

export function num(n: number, lang: Lang, digits = 0): string {
  return new Intl.NumberFormat(locale(lang), { maximumFractionDigits: digits, minimumFractionDigits: 0 }).format(n)
}

// Dates arrive as YYYY-MM-DD; parse as local dates so they never shift a day.
export function parseDate(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function dayMonth(iso: string, lang: Lang): string {
  return new Intl.DateTimeFormat(locale(lang), { day: 'numeric', month: 'short' }).format(parseDate(iso))
}

export function weekday(iso: string, lang: Lang): string {
  return new Intl.DateTimeFormat(locale(lang), { weekday: 'short' }).format(parseDate(iso))
}

export function fullDate(iso: string, lang: Lang): string {
  return new Intl.DateTimeFormat(locale(lang), { weekday: 'long', day: 'numeric', month: 'long' }).format(parseDate(iso))
}

// 1 mm over 1 acre = 4.05 m3 (spec 6.7)
export const LITRES_PER_MM_ACRE = 4047
