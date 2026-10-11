import { useState, type ReactNode } from 'react'
import type { FieldProfile, Lang, Today } from '../../types'
import { fill, useLang, useStrings } from '../../i18n'
import { fullDate, num, parseDate } from '../../format'
import { strings, type TodayStrings } from './strings'
import { CloudOffIcon } from './icons'
import { ACTION_CLASS, actionKicker, actionWord } from '../../actions'
import ActionIcon from '../../components/ActionIcon'
import ListenButton from './ListenButton'
import SoilColumn, { type WalletLabel } from './SoilColumn'
import './TodaySection.css'

export default function TodaySection({ field, today }: { field: FieldProfile; today: Today | null }) {
  const t = useStrings(strings)
  const { lang } = useLang()
  if (field.status === 'SEASON_OVER') return <SeasonOver field={field} t={t} lang={lang} />
  if (!today) return <Waiting field={field} t={t} lang={lang} />

  const action = today.action
  const kicker = actionKicker(action, lang)
  const reason = reasonFor(today, t, lang)
  const advice = today.advice_text[lang]
  const pumping = action === 'IRRIGATE' || action === 'HEAT_PROTECTION'

  const stressPct = today.taw_mm > 0 ? clampPct(((today.taw_mm - today.raw_mm) / today.taw_mm) * 100) : null
  const pct = clampPct(today.water_wallet_pct)
  const afterPct = pumping && today.taw_mm > 0 ? clampPct(pct + (today.depth_mm / today.taw_mm) * 100) : null

  const labels: WalletLabel[] = [
    {
      key: 'level',
      pct,
      height: 56,
      className: 'wallet__label--level',
      content: (
        <>
          <span className="wallet__pct">{num(pct, lang)}%</span>
          <span>{t.wallet_left}</span>
        </>
      ),
    },
  ]
  if (stressPct !== null)
    labels.push({
      key: 'stress',
      pct: stressPct,
      height: 50,
      className: 'wallet__label--stress',
      content: (
        <>
          <span className="wallet__label-strong">{t.wallet_stress}</span>
          <span>{t.wallet_stress_note}</span>
        </>
      ),
    })
  if (afterPct !== null && afterPct - pct >= 4)
    labels.push({
      key: 'after',
      pct: afterPct,
      height: 44,
      className: 'wallet__label--after',
      content: (
        <>
          <span className="wallet__label-strong">
            +{num(today.depth_mm, lang)} {t.mm}
          </span>
          <span>{t.wallet_after}</span>
        </>
      ),
    })
  labels.push({
    key: 'root',
    pct: 'root',
    height: 24,
    className: 'wallet__label--root',
    content: fill(t.wallet_roots, { m: num(today.root_depth_m, lang, 2) }),
  })

  const ariaLabel = `${fill(t.wallet_aria, {
    m: num(today.root_depth_m, lang, 2),
    pct: num(pct, lang),
    stress: stressPct === null ? '?' : num(Math.round(stressPct), lang),
  })} ${t[`wallet_aria_${action}`]}`

  return (
    <section className={`today today--${ACTION_CLASS[action]}`} aria-labelledby="today-h">
      <Identity field={field} t={t} lang={lang} generatedAt={today.generated_at ?? undefined} />

      {today.weather_stale && (
        <p className="today__stale">
          <CloudOffIcon />
          <span>{t.stale}</span>
        </p>
      )}

      <div className="today__grid">
        <div className="today__decision">
          <h1 id="today-h" className="today__action">
            <span className="today__icon">
              <ActionIcon action={action} size={30} />
            </span>
            <span className="today__word">
              {kicker && <span className="today__qualifier">{kicker} </span>}
              {actionWord(action, lang, 'hero')}
            </span>
          </h1>

          <Amount today={today} t={t} lang={lang} />

          {reason && <p className="today__reason">{reason}</p>}
          <p className="today__advice">{advice}</p>
          {today.notes?.[lang].map((note) => (
            <p key={note} className="today__note">
              {note}
            </p>
          ))}

          <ListenButton key={`${lang}|${today.audio_url[lang] ?? ''}|${advice}`} url={today.audio_url[lang]} text={advice} lang={lang} t={t} />
        </div>

        <div className="today__wallet">
          <h2 className="today__wallet-h">{t.wallet_title}</h2>
          <SoilColumn
            rootDepthM={today.root_depth_m}
            pct={pct}
            stressPct={stressPct}
            afterPct={afterPct}
            stage={today.stage}
            labels={labels}
            ariaLabel={ariaLabel}
          />
        </div>

        <Facts field={field} today={today} t={t} lang={lang} pumping={pumping} />
      </div>
    </section>
  )
}

// Millimetres: one decimal for small amounts so 3.6 mm never reads as 4 mm.
function mm(n: number, lang: Lang) {
  return num(n, lang, n < 10 ? 1 : 0)
}

function clampPct(n: number) {
  return Math.max(0, Math.min(100, n))
}

// One plain line from the engine's reason code. Unknown codes return null and
// the advice text (shown right below) carries the reason on its own.
function reasonFor(today: Today, t: TodayStrings, lang: Lang): string | null {
  const code = today.reason_code
  const crosses = /^CROSSES_RAW_IN_(\d+)D$/.exec(code)
  if (crosses) {
    const n = Number(crosses[1])
    if (n <= 0) return t.reason_CROSSES_RAW_TODAY
    if (n === 1) return t.reason_CROSSES_RAW_TOMORROW
    return fill(t.reason_CROSSES_RAW_IN, { n: num(n, lang) })
  }
  switch (code) {
    case 'CROSSES_RAW_TODAY':
      return t.reason_CROSSES_RAW_TODAY
    case 'BELOW_RAW':
      return t.reason_BELOW_RAW
    case 'RAIN_COVERS':
      return fill(t.reason_RAIN_COVERS, { mm: mm(today.rain_next_3d_mm, lang) })
    case 'HEALTHY':
      return t.reason_HEALTHY
    case 'HEAT_FLOWERING':
      return t.reason_HEAT_FLOWERING
    case 'HEAT_GRAIN_FILLING':
      return t.reason_HEAT_GRAIN_FILLING
  }
  if (code.startsWith('HEAT')) return t.reason_HEAT
  return null
}

function Amount({ today, t, lang }: { today: Today; t: TodayStrings; lang: Lang }) {
  let pre: string | null = null
  let big: ReactNode
  let post: string | null = null
  switch (today.action) {
    case 'IRRIGATE':
    case 'HEAT_PROTECTION':
      big = (
        <>
          {num(today.depth_mm, lang)} <span className="today__unit">{t.mm}</span>
        </>
      )
      break
    case 'SKIP':
      big = (
        <>
          {mm(today.rain_next_3d_mm, lang)} <span className="today__unit">{t.mm}</span>
        </>
      )
      post = t.amount_rain_post
      break
    case 'WAIT': {
      const n = today.days_to_next_irrigation
      if (n === null) return <p className="today__amount today__amount--note">{t.no_pump_today}</p>
      pre = t.amount_wait_pre
      big = fill(n === 1 ? t.amount_wait_day : t.amount_wait_days, { n: num(n, lang) })
      break
    }
  }
  return (
    <p className="today__amount">
      {pre && <span className="today__amount-small">{pre} </span>}
      <span className="today__amount-big">{big}</span>
      {post && <span className="today__amount-small"> {post}</span>}
    </p>
  )
}

function Identity({ field, t, lang, generatedAt }: { field: FieldProfile; t: TodayStrings; lang: Lang; generatedAt?: string }) {
  let generated: string | null = null
  if (generatedAt) {
    const d = new Date(generatedAt)
    if (!Number.isNaN(d.getTime())) {
      const loc = lang === 'hi' ? 'hi-IN' : 'en-IN'
      const date = new Intl.DateTimeFormat(loc, { day: 'numeric', month: 'short', timeZone: 'Asia/Kolkata' }).format(d)
      const time = new Intl.DateTimeFormat(loc, {
        hour: 'numeric',
        minute: '2-digit',
        timeZone: 'Asia/Kolkata',
        ...(lang === 'hi' ? { dayPeriod: 'long' as const } : {}),
      }).format(d)
      generated = fill(t.generated, { date, time })
    }
  }
  return (
    <div className="today__id">
      <p className="today__field">
        <span className="today__field-name">
          {field.label ||
            fill(t.my_field, {
              crop: t[`crop_${field.crop.toLowerCase()}` as 'crop_wheat' | 'crop_paddy' | 'crop_cotton' | 'crop_sugarcane'],
              area: num(field.area_acres, lang, 1),
            })}
        </span>
        {field.is_test && <span className="today__badge">{t.test_field}</span>}
      </p>
      <p className="today__meta">
        {field.place}
        {generated && (
          <>
            <br />
            <time dateTime={generatedAt}>{generated}</time>
          </>
        )}
      </p>
    </div>
  )
}

function Facts({ field, today, t, lang, pumping }: { field: FieldProfile; today: Today; t: TodayStrings; lang: Lang; pumping: boolean }) {
  const area = fill(field.area_acres === 1 ? t.for_area_one : t.for_area, { n: num(field.area_acres, lang, 2) })
  const litres = today.litres >= 10000 ? Math.round(today.litres / 1000) * 1000 : Math.round(today.litres / 10) * 10
  return (
    <dl className="today__facts" aria-label={t.facts_label}>
      <div className="fact">
        <dt>{t.rain_3d}</dt>
        <dd>
          {mm(today.rain_next_3d_mm, lang)} {t.mm}
        </dd>
      </div>
      <div className={`fact fact--heat-${today.heat_risk.toLowerCase()}`}>
        <dt>{t.heat_risk}</dt>
        <dd>{t[`heat_${today.heat_risk}`]}</dd>
      </div>
      <div className="fact fact--wide">
        <dt>{t.crop}</dt>
        <dd>
          {fill(t.crop_value, {
            stage: t[`stage_${today.stage}`],
            n: num(today.day_after_sowing, lang),
          })}
          {' · '}
          {t[`crop_${field.crop.toLowerCase()}` as 'crop_wheat' | 'crop_paddy' | 'crop_cotton' | 'crop_sugarcane']}
        </dd>
      </div>
      {pumping && (
        <>
          <div className="fact fact--est">
            <dt>
              {t.water_est}
              <span className="fact__area">{area}</span>
            </dt>
            <dd>{fill(t.litres, { n: num(litres, lang) })}</dd>
          </div>
          <div className="fact fact--est">
            <dt>
              {t.pump_est}
              <span className="fact__area">{area}</span>
            </dt>
            <dd>{fill(t.units, { n: num(today.kwh, lang, today.kwh < 10 ? 1 : 0) })}</dd>
          </div>
          {today.co2_kg !== undefined && (
            <div className="fact fact--est">
              <dt>
                {t.co2_est}
                <span className="fact__area">{area}</span>
              </dt>
              <dd>{fill(t.co2, { n: num(today.co2_kg, lang, today.co2_kg < 10 ? 1 : 0) })}</dd>
            </div>
          )}
          {today.cost_inr !== undefined && (
            <div className="fact fact--est fact--wide">
              <dt>{t.cost_est}</dt>
              <dd>{fill(t.cost, { n: num(Math.round(today.cost_inr), lang) })}</dd>
            </div>
          )}
        </>
      )}
    </dl>
  )
}

export function Unavailable({ field, date, text }: { field: FieldProfile; date: string; text: Record<Lang, string> }) {
  const t = useStrings(strings)
  const { lang } = useLang()
  return (
    <section className="today today--waiting" aria-labelledby="today-h">
      <Identity field={field} t={t} lang={lang} />
      <h1 id="today-h" className="today__waiting-title">
        {t.unavailable_title}
      </h1>
      <p className="today__reason">
        <time dateTime={date}>{fullDate(date, lang)}</time>
      </p>
      <p className="today__advice">{text[lang]}</p>
    </section>
  )
}

function SeasonOver({ field, t, lang }: { field: FieldProfile; t: TodayStrings; lang: Lang }) {
  return (
    <section className="today today--waiting" aria-labelledby="today-h">
      <Identity field={field} t={t} lang={lang} />
      <h1 id="today-h" className="today__waiting-title">
        {t.over_title}
      </h1>
      <p className="today__reason">{t.over_body}</p>
    </section>
  )
}

function Waiting({ field, t, lang }: { field: FieldProfile; t: TodayStrings; lang: Lang }) {
  // Read the clock once per mount, not on every render.
  const [now] = useState(() => new Date())
  const today0 = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const days = Math.round((parseDate(field.sowing_date).getTime() - today0.getTime()) / 86400000)
  const labels: WalletLabel[] = [
    {
      key: 'level',
      pct: 100,
      height: 56,
      className: 'wallet__label--level',
      content: (
        <>
          <span className="wallet__label-strong">{t.waiting_full}</span>
          <span>{t.waiting_full_note}</span>
        </>
      ),
    },
  ]
  return (
    <section className="today today--waiting" aria-labelledby="today-h">
      <Identity field={field} t={t} lang={lang} />
      <div className="today__grid">
        <div className="today__decision">
          <h1 id="today-h" className="today__waiting-title">
            {days < 0 ? t.waiting_first_title : fill(t.waiting_title, { date: fullDate(field.sowing_date, lang) })}
          </h1>
          <p className="today__reason">
            {days < 0 ? fill(t.waiting_first_body, { date: fullDate(field.sowing_date, lang) }) : t.waiting_body}
          </p>
          {days >= 0 && (
            <p className="today__countdown">
              <span>{days === 0 ? t.waiting_today : fill(t.waiting_days, { n: num(days, lang) })}</span>
            </p>
          )}
        </div>
        <div className="today__wallet">
          <h2 className="today__wallet-h">{t.wallet_title}</h2>
          <SoilColumn rootDepthM={1.25} pct={100} stressPct={null} afterPct={null} stage="SEED" labels={labels} ariaLabel={t.waiting_aria} dim />
        </div>
      </div>
    </section>
  )
}
