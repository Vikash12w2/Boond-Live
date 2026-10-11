import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react'
import type { Lang, ReplayResponse } from '../../types'
import { fill } from '../../i18n'
import { num } from '../../format'
import { daysBetween, dayMonthLong, monthShort, stressPct, waterPct } from './model'
import type { ReplayStrings } from './strings'

// Hand-built season chart in three stacked strips that share one time axis:
// water left in the soil (the main story), rain, and the day's highest temperature.
// Each strip has its own scale, so no strip ever carries two y-axes.

export interface ChartGeometry {
  left: number
  plotW: number
}

interface Props {
  data: ReplayResponse
  index: number
  lang: Lang
  t: ReplayStrings
  onScrub: (i: number) => void
  onGeometry: (g: ChartGeometry) => void
}

const M = { l: 40, r: 14 }
const TEMP_FLOOR = 5
const TEMP_CEIL = 45

export default function ReplayChart({ data, index, lang, t, onScrub, onGeometry }: Props) {
  const wrap = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const dragging = useRef(false)

  useEffect(() => {
    const el = wrap.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const days = data.days
  const n = days.length
  const narrow = width < 560
  const plotW = Math.max(10, width - M.l - M.r)

  useEffect(() => {
    if (width > 0) onGeometry({ left: M.l, plotW })
  }, [width, plotW, onGeometry])

  const g = useMemo(() => {
    const waterTop = 10
    const waterH = narrow ? 190 : 250
    const rainTop = waterTop + waterH + 26
    const rainH = 30
    // A reserved row above the temperature plot carries the heat-warning note,
    // so the text never sits on the line.
    const annTop = rainTop + rainH + 30
    const tempTop = annTop + 38
    const tempH = narrow ? 96 : 116
    const axisTop = tempTop + tempH
    const height = axisTop + 26

    const x = (i: number) => M.l + (n > 1 ? (i / (n - 1)) * plotW : 0)
    const yW = (p: number) => waterTop + (1 - p / 100) * waterH
    const rainMax = Math.max(10, ...days.map((d) => d.rain_mm))
    const yR = (mm: number) => rainTop + rainH - (mm / rainMax) * rainH
    const tLo = Math.min(TEMP_FLOOR, ...days.map((d) => d.tmax_c))
    const tHi = Math.max(TEMP_CEIL, ...days.map((d) => d.tmax_c))
    const yT = (c: number) => tempTop + (1 - (c - tLo) / (tHi - tLo)) * tempH

    const line = (vals: number[], y: (v: number) => number) =>
      vals.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('')

    const boondPct = days.map((d) => waterPct(d.taw_mm, d.boond.depletion_mm))
    const basePct = days.map((d) => waterPct(d.taw_mm, d.baseline.depletion_mm))
    const stress = days.map(stressPct)
    const stressPath = line(stress, yW)
    const band = `${stressPath}L${x(n - 1).toFixed(1)},${yW(0)}L${x(0).toFixed(1)},${yW(0)}Z`

    // Threshold runs: consecutive days that carry a heat threshold.
    const runs: { from: number; to: number; c: number }[] = []
    days.forEach((d, i) => {
      if (d.heat_threshold_c == null) return
      const last = runs[runs.length - 1]
      if (last && last.to === i - 1 && last.c === d.heat_threshold_c) last.to = i
      else runs.push({ from: i, to: i, c: d.heat_threshold_c })
    })

    const months = days
      .map((d, i) => ({ d, i }))
      .filter(({ d, i }) => d.date.endsWith('-01') || (i === 0 && Number(d.date.slice(8, 10)) <= 5))

    const rainPeak = days.reduce((best, d, i) => (d.rain_mm > days[best].rain_mm ? i : best), 0)

    return {
      waterTop, waterH, rainTop, rainH, annTop, tempTop, tempH, axisTop, height,
      x, yW, yR, yT, rainMax, boondPct, basePct, stress, band, stressPath, runs, months, rainPeak,
      boondPath: line(boondPct, yW),
      basePath: line(basePct, yW),
      tempPath: line(days.map((d) => d.tmax_c), yT),
    }
  }, [days, n, narrow, plotW])

  const events = data.heat_events
    .map((e) => ({
      ...e,
      i: days.findIndex((d) => d.date === e.date),
      w: days.findIndex((d) => d.date === e.warned_on),
      lead: daysBetween(e.warned_on, e.date),
    }))
    .filter((e) => e.i >= 0)

  const toIndex = (clientX: number, el: SVGSVGElement) => {
    const r = el.getBoundingClientRect()
    const frac = (clientX - r.left - M.l) / plotW
    return Math.max(0, Math.min(n - 1, Math.round(frac * (n - 1))))
  }
  const down = (e: PointerEvent<SVGSVGElement>) => {
    dragging.current = true
    e.currentTarget.setPointerCapture(e.pointerId)
    onScrub(toIndex(e.clientX, e.currentTarget))
  }
  const move = (e: PointerEvent<SVGSVGElement>) => {
    if (dragging.current) onScrub(toIndex(e.clientX, e.currentTarget))
  }
  const up = () => {
    dragging.current = false
  }

  const totalB = days.reduce((s, d) => s + d.boond.depth_mm, 0)
  const totalF = days.reduce((s, d) => s + d.baseline.depth_mm, 0)
  const summary = fill(t.chartSummary, {
    bn: days.filter((d) => d.boond.depth_mm > 0).length,
    bmm: num(totalB, lang),
    fn: days.filter((d) => d.baseline.depth_mm > 0).length,
    fmm: num(totalF, lang),
  })

  const cx = g.x(index)
  const cur = days[index]

  return (
    <div className="rp-chart" ref={wrap}>
      {width > 0 && (
        <svg
          width={width}
          height={g.height}
          viewBox={`0 0 ${width} ${g.height}`}
          role="img"
          aria-label={summary}
          className="rp-chart__svg"
          onPointerDown={down}
          onPointerMove={move}
          onPointerUp={up}
          onPointerCancel={up}
        >
          {/* Water strip */}
          {[0, 50, 100].map((p) => (
            <g key={p}>
              <line className="rp-grid" x1={M.l} x2={M.l + plotW} y1={g.yW(p)} y2={g.yW(p)} />
              <text className="rp-tick" x={M.l - 6} y={g.yW(p) + 4} textAnchor="end">
                {num(p, lang)}%
              </text>
            </g>
          ))}
          <path className="rp-band" d={g.band} />
          <path className="rp-stress" d={g.stressPath} />
          <text className="rp-band__label" x={M.l + 6} y={g.yW(0) - 8}>
            {t.thirsty}
          </text>

          {events.map((e) =>
            e.w >= 0 ? (
              <line key={`w${e.date}`} className="rp-warnline" x1={g.x(e.w)} x2={g.x(e.w)} y1={g.waterTop} y2={g.axisTop} />
            ) : null,
          )}

          <path className="rp-line rp-line--base" d={g.basePath} />
          <path className="rp-line rp-line--boond" d={g.boondPath} />

          {days.map((d, i) =>
            d.baseline.depth_mm > 0 ? (
              <circle key={`f${i}`} className="rp-dot rp-dot--base" cx={g.x(i)} cy={g.yW(g.basePct[i])} r={4} />
            ) : null,
          )}
          {days.map((d, i) =>
            d.boond.depth_mm > 0 ? (
              <circle
                key={`b${i}`}
                className={`rp-dot ${d.boond.action === 'HEAT_PROTECTION' ? 'rp-dot--heat' : 'rp-dot--boond'}`}
                cx={g.x(i)}
                cy={g.yW(g.boondPct[i])}
                r={4.5}
              />
            ) : null,
          )}

          {/* Rain strip */}
          <text className="rp-strip" x={M.l} y={g.rainTop - 8}>
            {t.rain}
          </text>
          <line className="rp-axis" x1={M.l} x2={M.l + plotW} y1={g.rainTop + g.rainH} y2={g.rainTop + g.rainH} />
          {days.map((d, i) => {
            if (d.rain_mm <= 0) return null
            const bw = Math.max(1.5, Math.min(6, (plotW / n) * 0.7))
            const y = g.yR(d.rain_mm)
            return (
              <rect
                key={`r${i}`}
                className="rp-rain"
                x={g.x(i) - bw / 2}
                y={y}
                width={bw}
                height={Math.max(1, g.rainTop + g.rainH - y)}
                rx={Math.min(1.5, bw / 2)}
              />
            )
          })}
          {days[g.rainPeak].rain_mm > 0 && (
            <text
              className="rp-tick"
              x={g.x(g.rainPeak) + (g.x(g.rainPeak) > M.l + plotW - 60 ? -6 : 6)}
              y={g.rainTop + 10}
              textAnchor={g.x(g.rainPeak) > M.l + plotW - 60 ? 'end' : 'start'}
            >
              {fill(t.mm, { v: num(days[g.rainPeak].rain_mm, lang) })}
            </text>
          )}

          {/* Temperature strip */}
          <text className="rp-strip" x={M.l} y={g.annTop - 8}>
            {t.temp}
          </text>
          {[20, 40].map((c) => (
            <g key={c}>
              <line className="rp-grid" x1={M.l} x2={M.l + plotW} y1={g.yT(c)} y2={g.yT(c)} />
              <text className="rp-tick" x={M.l - 6} y={g.yT(c) + 4} textAnchor="end">
                {num(c, lang)}°
              </text>
            </g>
          ))}
          {events.map((e) =>
            e.w >= 0 && e.w < e.i ? (
              <rect
                key={`lead${e.date}`}
                className="rp-lead"
                x={g.x(e.w)}
                y={g.annTop}
                width={g.x(e.i) - g.x(e.w)}
                height={g.axisTop - g.annTop}
              />
            ) : null,
          )}
          {g.runs.map((r) => (
            <line
              key={`t${r.from}`}
              className="rp-limit"
              x1={Math.max(M.l, g.x(r.from) - plotW / n / 2)}
              x2={Math.min(M.l + plotW, g.x(r.to) + plotW / n / 2)}
              y1={g.yT(r.c)}
              y2={g.yT(r.c)}
            />
          ))}
          <path className="rp-temp" d={g.tempPath} />
          {days.map((d, i) =>
            d.heat_threshold_c != null && d.tmax_c >= d.heat_threshold_c ? (
              <circle key={`h${i}`} className="rp-dot rp-dot--hot" cx={g.x(i)} cy={g.yT(d.tmax_c)} r={3.5} />
            ) : null,
          )}

          {/* Heat warning annotation: first event only, the others keep their markers */}
          {events.slice(0, 1).map((e) => {
            const anchorX = e.w >= 0 ? g.x(e.w) : g.x(e.i)
            const l1 = fill(t.warned, { warned: dayMonthLong(e.warned_on, lang) })
            const l2 = fill(t.warnedSub, { n: num(e.lead, lang) })
            const est = Math.max(l1.length, l2.length) * (lang === 'hi' ? 6.6 : 6.4)
            const left = anchorX - 8 - est >= M.l
            const tx = left ? anchorX - 8 : g.x(e.i) + 8
            return (
              <g key="ann" className="rp-ann">
                <circle className="rp-dot rp-dot--event" cx={g.x(e.i)} cy={g.yT(e.tmax_c)} r={5} />
                <text x={tx} y={g.annTop + 14} textAnchor={left ? 'end' : 'start'}>
                  <tspan className="rp-ann__main">{l1}</tspan>
                  <tspan className="rp-ann__sub" x={tx} dy={17}>
                    {l2}
                  </tspan>
                </text>
              </g>
            )
          })}

          {/* Months */}
          <line className="rp-axis" x1={M.l} x2={M.l + plotW} y1={g.axisTop} y2={g.axisTop} />
          {g.months.map(({ d, i }) => (
            <g key={d.date}>
              <line className="rp-axis" x1={g.x(i)} x2={g.x(i)} y1={g.axisTop} y2={g.axisTop + 4} />
              <text className="rp-tick" x={g.x(i) + 3} y={g.axisTop + 18}>
                {monthShort(d.date, lang)}
              </text>
            </g>
          ))}

          {/* Cursor */}
          <g className="rp-cursor" aria-hidden="true">
            <line x1={cx} x2={cx} y1={g.waterTop - 4} y2={g.axisTop} />
            <circle className="rp-cursor__dot rp-cursor__dot--base" cx={cx} cy={g.yW(g.basePct[index])} r={5} />
            <circle className="rp-cursor__dot rp-cursor__dot--boond" cx={cx} cy={g.yW(g.boondPct[index])} r={5} />
            <circle className="rp-cursor__dot rp-cursor__dot--temp" cx={cx} cy={g.yT(cur.tmax_c)} r={4} />
          </g>

          <rect className="rp-hit" x={0} y={0} width={width} height={g.height} />
        </svg>
      )}
    </div>
  )
}
