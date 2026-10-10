import { useId, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import type { Lang, OutlookDay, Today } from '../../types'
import { fill, useLang, useStrings, type Strings } from '../../i18n'
import { dayMonth, fullDate, num, parseDate, weekday } from '../../format'
import './outlook.css'

// Rain that counts as "arriving": enough to refill some of the root zone and likely.
const RAIN_MIN_MM = 5
const RAIN_MIN_PROB = 70 // same thresholds as the engine's skip rule (scripts/make_mocks.py)

const strings: Strings<{
  heading: string
  sub: string
  under: string
  underDetail: string
  rainFirst: string
  rainFirstDetail: string
  rainFirstThen: string
  cross: string
  crossDetail: string
  crossDetail1: string
  noRainBefore: string
  lateRain: string
  safe: string
  safeDetail: string
  today: string
  full: string
  stressLine: string
  legendWater: string
  legendStress: string
  legendRain: string
  legendHeat: string
  hint: string
  chartLabel: string
  water: string
  belowStress: string
  aboveStress: string
  rain: string
  noRain: string
  rainValue: string
  tmax: string
  heatOver: string
  mm: string
  tableCaption: string
  colDay: string
  colWater: string
  colStress: string
  colRain: string
  colProb: string
  colTmax: string
  yes: string
  no: string
}> = {
  hi: {
    heading: 'अगले 16 दिन',
    sub: 'अनुमान: अगर खेत में पानी न दें और मौसम पूर्वानुमान जैसा रहे।',
    under: 'खेत का पानी अभी दबाव-रेखा से नीचे है',
    underDetail: 'फ़सल को पानी की कमी हो रही है। बारिश का इंतज़ार न करें।',
    rainFirst: 'बारिश पहले आएगी',
    rainFirstDetail: '{date} को लगभग {mm} मिमी बारिश की उम्मीद है ({prob}% संभावना)।',
    rainFirstThen: 'उसके बिना {date} तक पानी दबाव-रेखा से नीचे चला जाता।',
    cross: '{date} तक पानी दबाव-रेखा से नीचे',
    crossDetail: 'अगर पानी न दें, तो {n} दिन में फ़सल को पानी की कमी होगी।',
    crossDetail1: 'अगर पानी न दें, तो कल से फ़सल को पानी की कमी होगी।',
    noRainBefore: 'उससे पहले अच्छी बारिश नहीं दिख रही।',
    lateRain: '{date} को लगभग {mm} मिमी बारिश की उम्मीद है, पर वह बाद में आएगी।',
    safe: 'अगले 16 दिन पानी काफ़ी है',
    safeDetail: 'खेत का पानी पूरे समय दबाव-रेखा से ऊपर रहेगा।',
    today: 'आज',
    full: 'पूरा भरा',
    stressLine: 'दबाव-रेखा',
    legendWater: 'खेत में बचा पानी',
    legendStress: 'दबाव-रेखा: इससे नीचे फ़सल प्यासी',
    legendRain: 'बारिश, गहरा रंग यानी पक्की संभावना',
    legendHeat: 'ज़्यादा गर्मी',
    hint: 'किसी दिन पर टैप करें',
    chartLabel: 'अगले 16 दिन का पानी और मौसम',
    water: 'खेत में पानी',
    belowStress: 'दबाव-रेखा से नीचे',
    aboveStress: 'दबाव-रेखा से ऊपर',
    rain: 'बारिश',
    noRain: 'नहीं',
    rainValue: '{mm} मिमी, {prob}% संभावना',
    tmax: 'दिन का तापमान',
    heatOver: 'गर्मी की हद {c}°C से ऊपर',
    mm: '{mm} मिमी',
    tableCaption: 'अगले 16 दिन, दिन-ब-दिन',
    colDay: 'दिन',
    colWater: 'बचा पानी (मिमी)',
    colStress: 'दबाव-रेखा से नीचे',
    colRain: 'बारिश (मिमी)',
    colProb: 'संभावना',
    colTmax: 'अधिकतम तापमान',
    yes: 'हाँ',
    no: 'नहीं',
  },
  en: {
    heading: 'Next 16 days',
    sub: 'Estimate, if you do not irrigate and the weather follows the forecast.',
    under: 'Field water is already below the stress line',
    underDetail: 'The crop is short of water now. Do not wait for rain.',
    rainFirst: 'Rain arrives first',
    rainFirstDetail: 'About {mm} mm of rain is expected on {date} ({prob}% chance).',
    rainFirstThen: 'Without it, water would drop below the stress line by {date}.',
    cross: 'Water drops below the stress line by {date}',
    crossDetail: 'If you do not irrigate, the crop runs short of water in {n} days.',
    crossDetail1: 'If you do not irrigate, the crop runs short of water from tomorrow.',
    noRainBefore: 'No useful rain is expected before then.',
    lateRain: 'About {mm} mm of rain is expected on {date}, but that comes later.',
    safe: 'Enough water for the next 16 days',
    safeDetail: 'Field water stays above the stress line the whole time.',
    today: 'Today',
    full: 'Full',
    stressLine: 'Stress line',
    legendWater: 'Water left in the field',
    legendStress: 'Stress line: below it the crop is thirsty',
    legendRain: 'Rain, darker means more likely',
    legendHeat: 'Too hot',
    hint: 'Tap a day',
    chartLabel: 'Water and weather for the next 16 days',
    water: 'Field water',
    belowStress: 'below the stress line',
    aboveStress: 'above the stress line',
    rain: 'Rain',
    noRain: 'none',
    rainValue: '{mm} mm, {prob}% chance',
    tmax: 'Day temperature',
    heatOver: 'above the {c}°C heat limit',
    mm: '{mm} mm',
    tableCaption: 'Next 16 days, day by day',
    colDay: 'Day',
    colWater: 'Water left (mm)',
    colStress: 'Below stress line',
    colRain: 'Rain (mm)',
    colProb: 'Chance',
    colTmax: 'Max temperature',
    yes: 'yes',
    no: 'no',
  },
}

type T = (typeof strings)['hi']

interface Point {
  date: string
  water: number // mm still available (TAW - depletion)
  stress: number // water level at the stress line (TAW - RAW)
  taw: number
  below: boolean
  day: OutlookDay | null // null for today
  heat: boolean
}

type Status =
  | { kind: 'under' }
  | { kind: 'rain'; rain: number; cross: number | null }
  | { kind: 'cross'; cross: number; late: number | null }
  | { kind: 'safe' }

function buildPoints(today: Today, outlook: OutlookDay[]): Point[] {
  const first: Point = {
    date: today.date,
    water: Math.max(0, today.taw_mm - today.depletion_mm),
    stress: today.taw_mm - today.raw_mm,
    taw: today.taw_mm,
    below: today.depletion_mm > today.raw_mm,
    day: null,
    heat: false,
  }
  return [
    first,
    ...outlook.map((d) => ({
      date: d.date,
      water: Math.max(0, d.taw_mm - d.depletion_mm),
      stress: d.taw_mm - d.raw_mm,
      taw: d.taw_mm,
      below: d.depletion_mm > d.raw_mm,
      day: d,
      heat: d.heat_threshold_c != null && d.tmax_c != null && d.tmax_c >= d.heat_threshold_c,
    })),
  ]
}

function findStatus(pts: Point[]): Status {
  if (pts[0].below) return { kind: 'under' }
  const cross = pts.findIndex((p) => p.below)
  const rain = pts.findIndex(
    (p) => p.day != null && p.day.rain_mm >= RAIN_MIN_MM && p.day.rain_prob_pct >= RAIN_MIN_PROB,
  )
  if (rain > 0 && (cross < 0 || rain <= cross)) {
    // Projected depletion already includes forecast rain, so a later crossing is "after the rain".
    const before = cross < 0 ? null : cross
    return { kind: 'rain', rain, cross: before }
  }
  if (cross > 0) return { kind: 'cross', cross, late: rain > cross ? rain : null }
  return { kind: 'safe' }
}

function shortDate(iso: string, lang: Lang) {
  return `${weekday(iso, lang)}, ${dayMonth(iso, lang)}`
}

function summary(status: Status, pts: Point[], t: T, lang: Lang): { head: string; detail: string } {
  switch (status.kind) {
    case 'under':
      return { head: t.under, detail: t.underDetail }
    case 'rain': {
      const d = pts[status.rain].day!
      let detail = fill(t.rainFirstDetail, {
        date: shortDate(d.date, lang),
        mm: num(d.rain_mm, lang),
        prob: num(d.rain_prob_pct, lang),
      })
      // Show what would happen without the rain only when the projection crosses on that same day or later.
      if (status.cross != null && status.cross > status.rain) {
        detail += ' ' + fill(t.rainFirstThen, { date: shortDate(pts[status.cross].date, lang) })
      }
      return { head: t.rainFirst, detail }
    }
    case 'cross':
      return {
        head: fill(t.cross, { date: shortDate(pts[status.cross].date, lang) }),
        detail:
          (status.cross === 1 ? t.crossDetail1 : fill(t.crossDetail, { n: num(status.cross, lang) })) +
          ' ' +
          (status.late != null
            ? fill(t.lateRain, {
                date: shortDate(pts[status.late].date, lang),
                mm: num(pts[status.late].day!.rain_mm, lang),
              })
            : t.noRainBefore),
      }
    case 'safe':
      return { head: t.safe, detail: t.safeDetail }
  }
}

function useWidth<E extends HTMLElement>() {
  const ref = useRef<E>(null)
  const [w, setW] = useState(320)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const update = () => setW(Math.max(240, Math.floor(el.clientWidth)))
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, w] as const
}

export default function OutlookSection({ today, outlook }: { today: Today; outlook: OutlookDay[] }) {
  const t = useStrings(strings)
  const { lang } = useLang()
  const pts = useMemo(() => buildPoints(today, outlook), [today, outlook])
  const status = useMemo(() => findStatus(pts), [pts])
  const { head, detail } = summary(status, pts, t, lang)
  const keyIdx = status.kind === 'cross' ? status.cross : status.kind === 'rain' ? status.rain : null
  const firstHeat = pts.findIndex((p) => p.heat)
  const [sel, setSel] = useState<number>(keyIdx ?? (firstHeat > 0 ? firstHeat : 1))
  const [boxRef, W] = useWidth<HTMLDivElement>()
  const anyHeat = pts.some((p) => p.heat)

  // Geometry, in real pixels so text stays crisp and the same size at every width.
  const N = pts.length
  const colW = W / N
  const x = (i: number) => colW * (i + 0.5)
  const anyRain = pts.some((p) => (p.day?.rain_mm ?? 0) >= 0.5)
  const RAIN_H = anyRain ? 44 : 6
  const HEAT_Y = RAIN_H + 4
  const HEAT_H = anyHeat ? 30 : 10
  const PT = RAIN_H + HEAT_H
  const PH = W < 480 ? 160 : 200
  const PB = PT + PH
  const H = PB + 42
  const maxTaw = Math.max(...pts.map((p) => p.taw), 1)
  const y = (v: number) => PB - (v / maxTaw) * PH
  const maxRain = Math.max(10, ...pts.map((p) => p.day?.rain_mm ?? 0))
  const rainY = (mm: number) => (mm / maxRain) * (RAIN_H - 16)
  const barW = Math.max(4, Math.min(16, colW - 4))

  const edgeLine = (vals: number[]) =>
    vals.map((v, i) => `${i === 0 ? 'M0' : `L${x(i)}`},${y(v)}`).join(' ') + ` L${W},${y(vals[N - 1])}`
  const stressPath = edgeLine(pts.map((p) => p.stress))
  const tawPath = edgeLine(pts.map((p) => p.taw))
  const waterLine = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i)},${y(p.water)}`).join(' ')
  const waterArea = `${waterLine} L${x(N - 1)},${PB} L${x(0)},${PB} Z`
  const stressZone = `${stressPath} L${W},${PB} L0,${PB} Z`
  const aboveZone = `${stressPath} L${W},0 L0,0 Z`
  const uid = useId().replace(/:/g, '')

  // Label useful rain amounts, biggest first, skipping any that would touch a label already placed.
  const rainLabelled = new Set<number>()
  pts
    .map((p, i) => ({ i, mm: p.day?.rain_mm ?? 0 }))
    .filter((r) => r.mm >= RAIN_MIN_MM)
    .sort((a, b) => b.mm - a.mm)
    .forEach((r) => {
      if ([...rainLabelled].every((j) => Math.abs(x(j) - x(r.i)) > 46)) rainLabelled.add(r.i)
    })

  // Runs of consecutive heat days.
  const heatRuns: [number, number][] = []
  pts.forEach((p, i) => {
    if (!p.heat) return
    const last = heatRuns[heatRuns.length - 1]
    if (last && last[1] === i - 1) last[1] = i
    else heatRuns.push([i, i])
  })

  // Put a line label at the first spot (right or left end, above or below) the water line does not cross.
  const waterYAt = (px: number) => {
    const f = Math.min(N - 1, Math.max(0, px / colW - 0.5))
    const i = Math.floor(f)
    const j = Math.min(N - 1, i + 1)
    return y(pts[i].water + (pts[j].water - pts[i].water) * (f - i))
  }
  const LBL_W = 76
  const place = (yRight: number, yLeft: number) => {
    const spots = [
      { x: W - 2, y: yRight - 6, anchor: 'end' as const },
      { x: W - 2, y: yRight + 15, anchor: 'end' as const },
      { x: 2, y: yLeft - 6, anchor: 'start' as const },
      { x: 2, y: yLeft + 15, anchor: 'start' as const },
    ]
    const clear = (s: (typeof spots)[number]) => {
      if (s.y < PT + 12 || s.y > PB - 4) return false
      const x0 = s.anchor === 'end' ? s.x - LBL_W : s.x
      for (let px = x0; px <= x0 + LBL_W; px += 4) {
        const wy = waterYAt(px)
        if (wy > s.y - 18 && wy < s.y + 8) return false
      }
      return true
    }
    return spots.find(clear) ?? spots[0]
  }
  const stressLbl = place(y(pts[N - 1].stress), y(pts[0].stress))
  const fullLbl = place(y(pts[N - 1].taw), y(pts[0].taw))

  // Thin the day labels so they never touch: one every `stride` days, the key day always.
  const stride = Math.max(1, Math.ceil(38 / colW))
  const labelled = new Set<number>()
  for (let i = 0; i < N; i += stride) labelled.add(i)
  // The key day keeps its label unless it would sit on top of "today" (its dot and the verdict still name it).
  if (keyIdx != null && keyIdx >= stride) {
    for (const i of [...labelled]) if (i !== 0 && Math.abs(i - keyIdx) < stride) labelled.delete(i)
    labelled.add(keyIdx)
  }

  // Name the month on the first labelled day of a new month.
  const shown = [...labelled].sort((a, b) => a - b)
  const newMonth = (i: number) => {
    const k = shown.indexOf(i)
    return k > 0 && parseDate(pts[shown[k - 1]].date).getMonth() !== parseDate(pts[i].date).getMonth()
  }

  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'ArrowRight') setSel((s) => Math.min(N - 1, s + 1))
    else if (e.key === 'ArrowLeft') setSel((s) => Math.max(0, s - 1))
    else if (e.key === 'Home') setSel(0)
    else if (e.key === 'End') setSel(N - 1)
    else return
    e.preventDefault()
  }

  const sp = pts[Math.min(sel, N - 1)]

  return (
    <section className="ol" aria-labelledby="outlook-h">
      <h2 id="outlook-h">{t.heading}</h2>

      <div className={`ol__verdict ol__verdict--${status.kind}`}>
        <p className="ol__head">{head}</p>
        <p className="ol__detail">{detail}</p>
      </div>

      <figure className="ol__figure">
        <div
          ref={boxRef}
          className="ol__chart"
          tabIndex={0}
          role="group"
          aria-label={`${t.chartLabel}. ${t.hint}`}
          onKeyDown={onKey}
        >
          <svg
            width={W}
            height={H}
            viewBox={`0 0 ${W} ${H}`}
            role="img"
            aria-label={`${t.chartLabel}. ${head}. ${detail}`}
            className="ol__svg"
          >
            <line x1={x(sel)} x2={x(sel)} y1={0} y2={PB} className="ol__cross" />

            {/* Sky line and rain hanging from it */}
            <line x1={0} x2={W} y1={0.5} y2={0.5} className="ol__sky" />
            {pts.map((p, i) => {
              if (!p.day || p.day.rain_mm < 0.5) return null
              const h = Math.max(3, rainY(p.day.rain_mm))
              const r = Math.min(4, barW / 2, h / 2)
              const x0 = x(i) - barW / 2
              const op = 0.3 + 0.7 * Math.min(1, p.day.rain_prob_pct / 100)
              const d = `M${x0},1 h${barW} v${h - r} a${r},${r} 0 0 1 ${-r},${r} h${-(barW - 2 * r)} a${r},${r} 0 0 1 ${-r},${-r} Z`
              return <path key={`r${i}`} d={d} className="ol__rain" style={{ opacity: op }} />
            })}
            {pts.map((p, i) =>
              p.day && rainLabelled.has(i) ? (
                <text
                  key={`rl${i}`}
                  x={i > N - 3 ? x(i) + barW / 2 : x(i)}
                  y={Math.max(3, rainY(p.day.rain_mm)) + 13}
                  textAnchor={i > N - 3 ? 'end' : 'middle'}
                  className="ol__label ol__label--strong"
                >
                  {fill(t.mm, { mm: num(p.day.rain_mm, lang) })}
                </text>
              ) : null,
            )}

            {/* Heat: one pill per run of hot days, with the run's top temperature when it fits */}
            {heatRuns.map(([a, b]) => {
              const w = Math.max(32, (b - a + 1) * colW - 2)
              const x1 = Math.min(W - w, Math.max(0, (x(a) + x(b)) / 2 - w / 2))
              const top = Math.max(...pts.slice(a, b + 1).map((p) => p.day?.tmax_c ?? 0))
              return (
                <g key={`heat${a}`}>
                  <rect x={x1} y={HEAT_Y} width={w} height={18} rx={9} className="ol__heatpill" />
                  <text x={x1 + w / 2} y={HEAT_Y + 13.5} textAnchor="middle" className="ol__label ol__label--heat">
                    {num(top, lang)}°
                  </text>
                </g>
              )
            })}

            {/* The tank: full line, stress line, water left */}
            <defs>
              <clipPath id={`${uid}-above`}>
                <path d={aboveZone} />
              </clipPath>
              <clipPath id={`${uid}-below`}>
                <path d={stressZone} />
              </clipPath>
            </defs>
            <path d={tawPath} className="ol__full" />
            <text x={fullLbl.x} y={fullLbl.y} textAnchor={fullLbl.anchor} className="ol__label">
              {t.full}
            </text>
            <path d={waterArea} className="ol__water-area" />
            <path d={stressPath} className="ol__stress" />
            <text x={stressLbl.x} y={stressLbl.y} textAnchor={stressLbl.anchor} className="ol__label ol__label--stress">
              {t.stressLine}
            </text>
            <line x1={0} x2={W} y1={PB} y2={PB} className="ol__base" />
            {/* Water line turns soil-brown once it is under the stress line */}
            <path d={waterLine} className="ol__water" clipPath={`url(#${uid}-above)`} />
            <path d={waterLine} className="ol__water ol__water--dry" clipPath={`url(#${uid}-below)`} />

            {/* Selected day */}
            <circle cx={x(sel)} cy={y(sp.water)} r={5} className="ol__selpt" />

            {/* Key day: where the line crosses the stress line */}
            {(status.kind === 'cross' || (status.kind === 'rain' && status.cross != null)) && (
              <circle
                cx={x(status.kind === 'cross' ? status.cross : status.cross!)}
                cy={y(pts[status.kind === 'cross' ? status.cross : status.cross!].water)}
                r={6}
                className="ol__crosspt"
              />
            )}

            {/* Day axis */}
            {pts.map((_, i) => (
              <line key={`t${i}`} x1={x(i)} x2={x(i)} y1={PB} y2={PB + 4} className="ol__tick" />
            ))}
            {pts.map((p, i) => {
              if (!labelled.has(i)) return null
              const strong = i === keyIdx || i === 0
              const anchor = i === 0 ? 'start' : i === N - 1 ? 'end' : 'middle'
              const lx = i === 0 ? Math.max(0, x(0) - colW / 2) : i === N - 1 ? W : x(i)
              return (
                <text key={`l${i}`} x={lx} textAnchor={anchor} className={`ol__label${strong ? ' ol__label--strong' : ''}`}>
                  <tspan x={lx} y={PB + 18}>
                    {i === 0 ? t.today : weekday(p.date, lang)}
                  </tspan>
                  <tspan x={lx} y={PB + 34}>
                    {newMonth(i) ? dayMonth(p.date, lang) : parseDate(p.date).getDate()}
                  </tspan>
                </text>
              )
            })}

            {/* Hit areas, wider than the marks */}
            {pts.map((_, i) => (
              <rect
                key={`hit${i}`}
                x={x(i) - colW / 2}
                y={0}
                width={colW}
                height={H}
                fill="transparent"
                onPointerDown={() => setSel(i)}
                onPointerEnter={(e) => e.pointerType === 'mouse' && setSel(i)}
              />
            ))}
          </svg>
        </div>

        <div className="ol__readout" aria-live="polite">
          <p className="ol__rdate">
            {sel === 0 ? `${t.today}, ` : ''}
            {fullDate(sp.date, lang)}
          </p>
          <dl className="ol__facts">
            <div>
              <dt>{t.water}</dt>
              <dd>
                {fill(t.mm, { mm: num(sp.water, lang) })}
                <span className={sp.below ? 'ol__flag ol__flag--below' : 'ol__flag'}>
                  {sp.below ? t.belowStress : t.aboveStress}
                </span>
              </dd>
            </div>
            {sp.day && (
              <div>
                <dt>{t.rain}</dt>
                <dd>
                  {sp.day.rain_mm >= 0.5
                    ? fill(t.rainValue, { mm: num(sp.day.rain_mm, lang, 1), prob: num(sp.day.rain_prob_pct, lang) })
                    : t.noRain}
                </dd>
              </div>
            )}
            {sp.day && sp.day.tmax_c != null && (
              <div>
                <dt>{t.tmax}</dt>
                <dd>
                  {num(sp.day.tmax_c, lang)}°C
                  {sp.heat && sp.day.heat_threshold_c != null && (
                    <span className="ol__flag ol__flag--heat">
                      {fill(t.heatOver, { c: num(sp.day.heat_threshold_c, lang) })}
                    </span>
                  )}
                </dd>
              </div>
            )}
          </dl>
        </div>

        <figcaption className="ol__legend">
          <p className="ol__sub">{t.sub}</p>
          <ul>
            <li>
              <svg width="22" height="14" aria-hidden="true">
                <rect x="0" y="6" width="22" height="8" className="ol__water-area" />
                <line x1="0" x2="22" y1="6" y2="6" className="ol__water" />
              </svg>
              {t.legendWater}
            </li>
            <li>
              <svg width="22" height="14" aria-hidden="true">
                <line x1="0" x2="22" y1="7" y2="7" className="ol__stress" />
              </svg>
              {t.legendStress}
            </li>
            <li>
              <svg width="22" height="14" aria-hidden="true">
                <rect x="2" y="0" width="7" height="12" rx="2" className="ol__rain" style={{ opacity: 0.35 }} />
                <rect x="13" y="0" width="7" height="12" rx="2" className="ol__rain" />
              </svg>
              {t.legendRain}
            </li>
            {anyHeat && (
              <li>
                <svg width="22" height="14" aria-hidden="true">
                  <rect x="1" y="1.5" width="20" height="11" rx="5.5" className="ol__heatpill" />
                </svg>
                {t.legendHeat}
              </li>
            )}
          </ul>
        </figcaption>
      </figure>

      <div className="visually-hidden">
      <table>
        <caption>{t.tableCaption}</caption>
        <thead>
          <tr>
            <th scope="col">{t.colDay}</th>
            <th scope="col">{t.colWater}</th>
            <th scope="col">{t.colStress}</th>
            <th scope="col">{t.colRain}</th>
            <th scope="col">{t.colProb}</th>
            <th scope="col">{t.colTmax}</th>
          </tr>
        </thead>
        <tbody>
          {pts.map((p, i) => (
            <tr key={p.date}>
              <th scope="row">{i === 0 ? `${t.today}, ${shortDate(p.date, lang)}` : shortDate(p.date, lang)}</th>
              <td>{num(p.water, lang)}</td>
              <td>{p.below ? t.yes : t.no}</td>
              <td>{p.day ? num(p.day.rain_mm, lang, 1) : ''}</td>
              <td>{p.day ? `${num(p.day.rain_prob_pct, lang)}%` : ''}</td>
              <td>{p.day?.tmax_c != null ? `${num(p.day.tmax_c, lang)}°C` : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </section>
  )
}
