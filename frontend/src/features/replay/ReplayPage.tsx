import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchReplay } from '../../api'
import { useAsync } from '../../useAsync'
import { LoadError, Loading } from '../../components/LoadState'
import { fill, useLang, useStrings } from '../../i18n'
import { num } from '../../format'
import type { Lang, ReplayResponse } from '../../types'
import ReplayChart, { type ChartGeometry } from './ReplayChart'
import { actionWord } from '../../actions'
import ActionIcon from '../../components/ActionIcon'
import { cumulative, dateWithYear, stressPct, waterPct, type Totals } from './model'
import { strings, type ReplayStrings } from './strings'
import './ReplayPage.css'

export default function ReplayPage() {
  const state = useAsync(fetchReplay)
  if (state.status === 'loading') return <Loading />
  if (state.status === 'error') return <LoadError error={state.error} />
  if (state.data.days.length === 0) return <LoadError error={new Error('replay has no days')} />
  return <Replay data={state.data} />
}

const reducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

function Replay({ data }: { data: ReplayResponse }) {
  const t = useStrings(strings)
  const { lang } = useLang()
  const days = data.days
  const last = days.length - 1

  const firstEvent = data.heat_events[0]
  const warnIndex = firstEvent ? days.findIndex((d) => d.date === firstEvent.warned_on) : -1

  // Autoplay once from sowing day; with reduced motion, open still on the warning day.
  const [still] = useState(reducedMotion)
  const [index, setIndex] = useState(() => (still ? (warnIndex >= 0 ? warnIndex : last) : 0))
  const [playing, setPlaying] = useState(!still)
  const [geo, setGeo] = useState<ChartGeometry | null>(null)

  useEffect(() => {
    if (!playing || index >= last) return
    const step = Math.max(40, Math.min(90, 9000 / days.length))
    // Hold on the warning day so the viewer sees it.
    const delay = index === 0 ? 700 : index === warnIndex ? 2200 : step
    const id = window.setTimeout(() => {
      const next = Math.min(last, index + 1)
      setIndex(next)
      if (next >= last) setPlaying(false)
    }, delay)
    return () => window.clearTimeout(id)
  }, [playing, index, last, warnIndex, days.length])

  const scrub = useCallback((i: number) => {
    setPlaying(false)
    setIndex(i)
  }, [])
  const togglePlay = () => {
    if (playing) return setPlaying(false)
    if (index >= last) setIndex(0)
    setPlaying(true)
  }

  const cum = useMemo(() => cumulative(data), [data])
  const day = days[index]

  return (
    <div className="rp">
      <header className="rp-head">
        <p className="rp-sim">{t.sim}</p>
        <h1 className="rp-title">{t.title}</h1>
        <p className="rp-intro">
          {fill(t.intro, { place: data.place, sowing: dateWithYear(data.sowing_date, lang) })}
        </p>
        <dl className="rp-meta">
          <div>
            <dt>{t.weatherLabel}</dt>
            <dd>
              <Linked text={data.weather_source} />
            </dd>
          </div>
          <div>
            <dt>{t.baselineLabel}</dt>
            <dd>
              {data.baseline.name}, <Linked text={data.baseline.source} />
              {data.baseline.description && <span className="rp-meta__desc">{data.baseline.description}</span>}
            </dd>
          </div>
        </dl>
      </header>

      <section className="rp-stage" aria-labelledby="rp-chart-h">
        <div className="rp-stage__top">
          <h2 id="rp-chart-h" className="rp-h2">
            {t.chartTitle}
          </h2>
          <ul className="rp-legend">
            <li>
              <span className="rp-key rp-key--boond" aria-hidden="true" />
              {t.boond}
            </li>
            <li>
              <span className="rp-key rp-key--base" aria-hidden="true" />
              {t.baseline}
            </li>
            <li>
              <span className="rp-key rp-key--band" aria-hidden="true" />
              {t.stressLine}
            </li>
            {days.some((d) => d.heat_threshold_c != null) && (
              <li>
                <span className="rp-key rp-key--limit" aria-hidden="true" />
                {t.heatLimit}
              </li>
            )}
          </ul>
        </div>

        <ReplayChart data={data} index={index} lang={lang} t={t} onScrub={scrub} onGeometry={setGeo} />

        <div className="rp-controls">
          <div
            className="rp-range"
            style={geo ? { marginLeft: geo.left - 14, width: geo.plotW + 28 } : undefined}
          >
            <input
              type="range"
              min={0}
              max={last}
              step={1}
              value={index}
              aria-label={t.slider}
              aria-valuetext={`${dateWithYear(day.date, lang)}, ${actionWord(day.boond.action, lang)}`}
              onChange={(e) => scrub(Number(e.target.value))}
            />
          </div>
          <div className="rp-buttons">
            <button type="button" className="rp-btn rp-btn--play" onClick={togglePlay} aria-pressed={playing}>
              {playing ? (
                <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                  <rect x="3.5" y="3" width="3.5" height="12" rx="1" fill="currentColor" />
                  <rect x="11" y="3" width="3.5" height="12" rx="1" fill="currentColor" />
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                  <path d="M5 3.2v11.6a.6.6 0 0 0 .9.5l9.3-5.8a.6.6 0 0 0 0-1L5.9 2.7a.6.6 0 0 0-.9.5z" fill="currentColor" />
                </svg>
              )}
              {playing ? t.pause : t.play}
            </button>
            <button
              type="button"
              className="rp-btn rp-btn--icon"
              onClick={() => scrub(Math.max(0, index - 1))}
              disabled={index === 0}
              aria-label={t.back}
              title={t.back}
            >
              <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                <path d="M11 4L6 9l5 5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <button
              type="button"
              className="rp-btn rp-btn--icon"
              onClick={() => scrub(Math.min(last, index + 1))}
              disabled={index === last}
              aria-label={t.forward}
              title={t.forward}
            >
              <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                <path d="M7 4l5 5-5 5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            {warnIndex >= 0 && (
              <button
                type="button"
                className="rp-btn rp-btn--heat"
                onClick={() => scrub(warnIndex)}
                aria-current={index === warnIndex ? 'true' : undefined}
              >
                <ActionIcon action="HEAT_PROTECTION" size={18} />
                {t.jumpHeat}
              </button>
            )}
          </div>
        </div>
      </section>

      <div className="rp-below">
        <DayPanel data={data} index={index} t={t} lang={lang} />
        <TotalsPanel boond={cum.boond[index]} base={cum.baseline[index]} date={day.date} t={t} lang={lang} />
      </div>

      <footer className="rp-notes">
        <p>{t.howTo}</p>
        <p>{t.limits}</p>
      </footer>
    </div>
  )
}

// Source strings from the backend may carry a URL; make it a real link.
function Linked({ text }: { text: string }) {
  const parts = text.split(/(https?:\/\/[^\s)]+)/)
  return (
    <>
      {parts.map((p, i) =>
        i % 2 ? (
          <a key={i} href={p} target="_blank" rel="noreferrer">
            {p.replace(/^https?:\/\//, '')}
          </a>
        ) : (
          p
        ),
      )}
    </>
  )
}

function DayPanel({ data, index, t, lang }: { data: ReplayResponse; index: number; t: ReplayStrings; lang: Lang }) {
  const d = data.days[index]
  const hot = d.heat_threshold_c != null && d.tmax_c >= d.heat_threshold_c
  const stress = stressPct(d)
  const fields = [
    { key: 'boond', label: t.boond, pct: waterPct(d.taw_mm, d.boond.depletion_mm), left: d.taw_mm - d.boond.depletion_mm },
    { key: 'base', label: t.baseline, pct: waterPct(d.taw_mm, d.baseline.depletion_mm), left: d.taw_mm - d.baseline.depletion_mm },
  ]
  const action = d.boond.action

  return (
    <section className="rp-day" aria-labelledby="rp-day-h">
      <h2 id="rp-day-h" className="rp-day__date">
        {dateWithYear(d.date, lang)}
      </h2>
      <p className="rp-day__sub">{fill(t.sinceSowing, { n: num(d.day_after_sowing, lang) })}</p>

      <dl className="rp-facts">
        <div>
          <dt>{t.stage}</dt>
          <dd>{t[d.stage]}</dd>
        </div>
        <div>
          <dt>{t.tmax}</dt>
          <dd>
            {num(d.tmax_c, lang, 1)}°C
            {hot && (
              <span className="rp-hot">
                <ActionIcon action="HEAT_PROTECTION" size={14} />
                {t.heatDay}
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt>{t.rainToday}</dt>
          <dd>{d.rain_mm > 0 ? fill(t.mm, { v: num(d.rain_mm, lang, 1) }) : t.noRain}</dd>
        </div>
      </dl>

      <div className={`rp-said rp-said--${action.toLowerCase()}`}>
        <span className="rp-said__label">{t.boondSaid}</span>
        <span className="rp-said__action">
          <ActionIcon action={action} size={26} />
          {actionWord(action, lang)}
          {d.boond.depth_mm > 0 && <span className="rp-said__depth">{fill(t.mm, { v: num(d.boond.depth_mm, lang) })}</span>}
        </span>
      </div>
      <p className="rp-farmer">
        <span className="rp-key rp-key--base" aria-hidden="true" />
        {t.baseline}:{' '}
        {d.baseline.depth_mm > 0 ? fill(t.watered, { mm: num(d.baseline.depth_mm, lang) }) : t.notWatered}
      </p>

      <h3 className="rp-h3">{t.waterLeft}</h3>
      <ul className="rp-meters">
        {fields.map((f) => {
          const thirsty = f.pct < stress - 0.01
          return (
            <li key={f.key} className={`rp-meter rp-meter--${f.key}`}>
              <span className="rp-meter__name">{f.label}</span>
              <span className="rp-meter__value">
                {num(f.pct, lang)}%
                <span className="rp-meter__mm">
                  {' '}
                  ({fill(t.mm, { v: num(Math.max(0, f.left), lang) })})
                </span>
                {thirsty && <span className="rp-meter__flag">{t.thirstyNow}</span>}
              </span>
              <span className="rp-meter__track" aria-hidden="true">
                <span className="rp-meter__fill" style={{ width: `${f.pct}%` }} />
                <span className="rp-meter__stress" style={{ left: `${stress}%` }} />
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

function TotalsPanel({
  boond,
  base,
  date,
  t,
  lang,
}: {
  boond: Totals
  base: Totals
  date: string
  t: ReplayStrings
  lang: Lang
}) {
  let verdict: string
  if (boond.water_mm === 0 && base.water_mm === 0) verdict = t.none
  else if (base.water_mm === 0) verdict = t.onlyBoond
  else if (Math.abs(boond.water_mm - base.water_mm) < 0.5) verdict = t.same
  else {
    const p = Math.round((Math.abs(base.water_mm - boond.water_mm) / base.water_mm) * 100)
    verdict = fill(boond.water_mm < base.water_mm ? t.less : t.more, { p: num(p, lang) })
  }

  const rows: { label: string; b: number; f: number; fmt: (v: number) => string; sub?: (v: number) => string }[] = [
    {
      label: t.water,
      b: boond.water_mm,
      f: base.water_mm,
      fmt: (v) => fill(t.mm, { v: num(v, lang) }),
      sub: (v) => fill(t.litres, { v: num(Math.round(v / 100) * 100, lang) }),
    },
    { label: t.irrigations, b: boond.irrigations, f: base.irrigations, fmt: (v) => fill(t.times, { v: num(v, lang) }) },
    { label: t.power, b: boond.kwh, f: base.kwh, fmt: (v) => fill(t.kwh, { v: num(v, lang) }) },
    { label: t.co2, b: boond.co2e_kg, f: base.co2e_kg, fmt: (v) => fill(t.kg, { v: num(v, lang) }) },
    { label: t.stressDays, b: boond.stress_days, f: base.stress_days, fmt: (v) => fill(t.days, { v: num(v, lang) }) },
  ]

  return (
    <section className="rp-totals" aria-labelledby="rp-totals-h">
      <div className="rp-totals__head">
        <h2 id="rp-totals-h" className="rp-h2">
          {fill(t.totalsTitle, { date: dateWithYear(date, lang) })}
        </h2>
        <span className="rp-est">{t.estimate}</span>
      </div>
      <p className="rp-verdict">{verdict}</p>
      <table className="rp-table">
        <caption className="visually-hidden">{t.tableNote}</caption>
        <tbody>
          {rows.map((r) => {
            const max = Math.max(r.b, r.f) || 1
            return (
              <tr key={r.label}>
                <th scope="row">{r.label}</th>
                <td>
                  <div className="rp-pair">
                    <span className="rp-pair__who">
                      <span className="rp-key rp-key--boond" aria-hidden="true" />
                      <span className="visually-hidden">{t.boond}: </span>
                    </span>
                    <span className="rp-pair__bar" aria-hidden="true">
                      <span className="rp-pair__fill rp-pair__fill--boond" style={{ width: `${(r.b / max) * 100}%` }} />
                    </span>
                    <span className="rp-pair__val">
                      {r.fmt(r.b)}
                      {r.sub && <span className="rp-pair__sub">{r.sub(boond.litres)}</span>}
                    </span>
                  </div>
                  <div className="rp-pair">
                    <span className="rp-pair__who">
                      <span className="rp-key rp-key--base" aria-hidden="true" />
                      <span className="visually-hidden">{t.baseline}: </span>
                    </span>
                    <span className="rp-pair__bar" aria-hidden="true">
                      <span className="rp-pair__fill rp-pair__fill--base" style={{ width: `${(r.f / max) * 100}%` }} />
                    </span>
                    <span className="rp-pair__val">
                      {r.fmt(r.f)}
                      {r.sub && <span className="rp-pair__sub">{r.sub(base.litres)}</span>}
                    </span>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}
