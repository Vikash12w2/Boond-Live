import type { ReactNode } from 'react'
import type { Stage } from '../../types'

// The water wallet drawn as a slice of the field: a wheat plant on top, soil
// below, the root zone down to root_depth_m, and water filling the root zone
// from the bottom up to the share of TAW still available. The dashed stress
// line sits at RAW: once the water drops below it the crop starts to suffer.
//
// The SVG is drawn at 1 unit = 1 CSS px so the HTML labels beside it line up
// with exact y positions.

export const COL_W = 136 // svg width, including the leader-line gutter
const H = 432
const COL_L = 6
const COL_R = 92
const CX = (COL_L + COL_R) / 2
const SURFACE = 98
const BOTTOM = H - 6
const MAX_DEPTH_M = 1.25 // the slice shows the top 1.25 m of soil

export type PlantStage = Stage | 'SEED'

// Headroom above the soil each plant needs (ears and awns included).
const SKY: Record<PlantStage, number> = {
  SEED: 40,
  INITIAL: 40,
  TILLERING: 50,
  JOINTING: 72,
  FLOWERING: 96,
  GRAIN_FILLING: 96,
  MATURITY: 96,
}

export interface WalletLabel {
  key: string
  pct: number | 'root' // level inside the root zone, or the root tip
  height: number // approximate rendered height of the HTML label, px
  className?: string
  content: ReactNode
}

function depthY(m: number) {
  return SURFACE + (Math.min(m, MAX_DEPTH_M) / MAX_DEPTH_M) * (BOTTOM - SURFACE)
}

// Push labels apart so they never overlap, keeping each as close as possible
// to the level it describes. Leader lines show where each one really points.
function layout(items: { y: number; h: number }[], top: number) {
  const order = items.map((it, i) => ({ ...it, i })).sort((a, b) => a.y - b.y)
  const gap = 6
  const out = order.map((o) => o.y)
  for (let k = 1; k < order.length; k++) {
    const min = out[k - 1] + (order[k - 1].h + order[k].h) / 2 + gap
    if (out[k] < min) out[k] = min
  }
  const last = order.length - 1
  if (last >= 0 && out[last] + order[last].h / 2 > H) {
    out[last] = H - order[last].h / 2
    for (let k = last - 1; k >= 0; k--) {
      const max = out[k + 1] - (order[k].h + order[k + 1].h) / 2 - gap
      if (out[k] > max) out[k] = max
    }
  }
  if (order.length && out[0] - order[0].h / 2 < top) {
    out[0] = top + order[0].h / 2
    for (let k = 1; k < order.length; k++) {
      const min = out[k - 1] + (order[k - 1].h + order[k].h) / 2 + gap
      if (out[k] < min) out[k] = min
    }
  }
  const result: number[] = []
  order.forEach((o, k) => (result[o.i] = out[k]))
  return result
}

export default function SoilColumn({
  rootDepthM,
  pct,
  stressPct,
  afterPct,
  stage,
  labels,
  ariaLabel,
  dim = false,
}: {
  rootDepthM: number
  pct: number
  stressPct: number | null
  afterPct: number | null
  stage: PlantStage
  labels: WalletLabel[]
  ariaLabel: string
  dim?: boolean
}) {
  const rootY = depthY(rootDepthM)
  const zoneH = rootY - SURFACE
  const levelY = (p: number) => rootY - (Math.max(0, Math.min(100, p)) / 100) * zoneH
  const waterY = levelY(pct)
  const stressY = stressPct === null ? null : levelY(stressPct)
  const afterY = afterPct === null ? null : levelY(afterPct)

  const wanted = labels.map((l) => ({ y: l.pct === 'root' ? rootY : levelY(l.pct), h: l.height }))
  // Trim the empty sky above a short plant so the slice starts close to its heading.
  const top = SURFACE - SKY[stage]
  const placed = layout(wanted, top)

  return (
    <div className={`wallet${dim ? ' wallet--dim' : ''}`} role="img" aria-label={ariaLabel}>
      <svg
        className="wallet__svg"
        width={COL_W}
        height={H - top}
        style={{ width: `calc(${COL_W}px * var(--wallet-k, 1))`, height: `calc(${H - top}px * var(--wallet-k, 1))` }}
        viewBox={`0 ${top} ${COL_W} ${H - top}`} aria-hidden="true" focusable="false">
        <defs>
          <clipPath id="wallet-slab">
            <rect x={COL_L} y={SURFACE} width={COL_R - COL_L} height={BOTTOM - SURFACE} rx="5" />
          </clipPath>
          <pattern id="wallet-grain" width="11" height="9" patternUnits="userSpaceOnUse">
            <circle cx="2" cy="2" r="1.1" className="wallet__grain" />
            <circle cx="7.5" cy="6" r="0.8" className="wallet__grain" />
            <circle cx="9.5" cy="1.5" r="0.5" className="wallet__grain" />
          </pattern>
          <pattern id="wallet-after" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" className="wallet__after-bg" />
            <line x1="0" y1="0" x2="0" y2="6" className="wallet__after-hatch" />
          </pattern>
        </defs>

        <g clipPath="url(#wallet-slab)">
          {/* deep soil, below the roots */}
          <rect x={COL_L} y={rootY} width={COL_R - COL_L} height={BOTTOM - rootY} className="wallet__deep" />
          {/* root zone, dry part */}
          <rect x={COL_L} y={SURFACE} width={COL_R - COL_L} height={zoneH} className="wallet__zone" />

          {/* what today's watering would add */}
          {afterY !== null && afterY < waterY && (
            <g className="wallet__after">
              <rect x={COL_L} y={afterY} width={COL_R - COL_L} height={waterY - afterY} fill="url(#wallet-after)" />
              <line x1={COL_L} x2={COL_R} y1={afterY} y2={afterY} className="wallet__after-line" />
            </g>
          )}

          {/* water held in the root zone: the one animated moment */}
          <g className="wallet__water">
            <rect x={COL_L} y={waterY} width={COL_R - COL_L} height={rootY - waterY} className="wallet__water-fill" />
            <line x1={COL_L} x2={COL_R} y1={waterY} y2={waterY} className="wallet__water-top" />
          </g>

          {/* soil grains over everything, so the water reads as wet soil, not a tank */}
          <rect x={COL_L} y={SURFACE} width={COL_R - COL_L} height={BOTTOM - SURFACE} fill="url(#wallet-grain)" />

          {/* the bottom of the root zone */}
          <line x1={COL_L} x2={COL_R} y1={rootY} y2={rootY} className="wallet__root-edge" />

          {stage !== 'SEED' && <Roots tipY={rootY} />}

          {/* topsoil crust */}
          <rect x={COL_L} y={SURFACE} width={COL_R - COL_L} height="5" className="wallet__crust" />
        </g>

        {stressY !== null && (
          <g>
            <line x1={COL_L} x2={COL_R} y1={stressY} y2={stressY} className="wallet__stress-halo" />
            <line x1={COL_L} x2={COL_R} y1={stressY} y2={stressY} className="wallet__stress" />
          </g>
        )}

        <Plant stage={stage} />

        {labels.map((l, i) => {
          const y = wanted[i].y
          const ly = placed[i]
          return (
            <path
              key={l.key}
              className={`wallet__leader wallet__leader--${l.key}`}
              d={`M${COL_R + 2} ${y} H${COL_R + 12} L${COL_R + 26} ${ly} H${COL_W}`}
            />
          )
        })}
      </svg>

      <div className="wallet__labels" style={{ height: `calc(${H - top}px * var(--wallet-k, 1))` }}>
        {labels.map((l, i) => (
          <div key={l.key} className={`wallet__label ${l.className ?? ''}`} style={{ top: `calc(${placed[i] - top}px * var(--wallet-k, 1))` }}>
            {l.content}
          </div>
        ))}
      </div>
    </div>
  )
}

function Roots({ tipY }: { tipY: number }) {
  const d = tipY - SURFACE
  const at = (f: number) => SURFACE + d * f
  return (
    <g className="wallet__roots">
      <path d={`M${CX} ${SURFACE} C${CX - 3} ${at(0.3)} ${CX + 4} ${at(0.6)} ${CX} ${tipY - 1}`} />
      <path d={`M${CX - 1} ${at(0.12)} C${CX - 14} ${at(0.25)} ${CX - 22} ${at(0.5)} ${CX - 24} ${at(0.78)}`} />
      <path d={`M${CX + 1} ${at(0.18)} C${CX + 15} ${at(0.3)} ${CX + 20} ${at(0.55)} ${CX + 27} ${at(0.86)}`} />
      <path d={`M${CX - 1} ${at(0.45)} C${CX - 8} ${at(0.55)} ${CX - 10} ${at(0.7)} ${CX - 12} ${at(0.95)}`} />
      <path d={`M${CX + 1} ${at(0.55)} C${CX + 8} ${at(0.65)} ${CX + 9} ${at(0.78)} ${CX + 11} ${at(0.92)}`} />
    </g>
  )
}

// A wheat plant whose shape follows the growth stage.
function Plant({ stage }: { stage: PlantStage }) {
  const b = SURFACE
  const blade = (dx: number, h: number, bend: number) => (
    <path key={`${dx}-${h}`} d={`M${CX} ${b} Q${CX + dx * 0.25} ${b - h * 0.6} ${CX + dx + bend} ${b - h}`} />
  )
  const ear = (x: number, y: number, tilt: number, key: string) => (
    <g key={key} transform={`translate(${x} ${y}) rotate(${tilt})`} className="wallet__ear">
      <path d="M0 0 C-4 -4 -4 -14 0 -19 C4 -14 4 -4 0 0z" />
      <path d="M-1.6 -6 L-5 -9 M1.6 -6 L5 -9 M-1.6 -11 L-5 -14 M1.6 -11 L5 -14" className="wallet__ear-line" />
      <path d="M0 -19 L0 -28 M-1.5 -16 L-4.5 -26 M1.5 -16 L4.5 -26" className="wallet__awn" />
    </g>
  )
  const stem = (dx: number, h: number) => <path key={`s${dx}`} d={`M${CX + dx * 0.2} ${b} Q${CX + dx * 0.6} ${b - h * 0.5} ${CX + dx} ${b - h}`} />

  switch (stage) {
    case 'SEED':
      return (
        <g className="wallet__plant">
          <ellipse cx={CX} cy={b + 12} rx="3.2" ry="5" transform={`rotate(-20 ${CX} ${b + 12})`} className="wallet__seed" />
        </g>
      )
    case 'INITIAL':
      return <g className="wallet__plant wallet__leaves">{[blade(-6, 14, -2), blade(4, 19, 2)]}</g>
    case 'TILLERING':
      return (
        <g className="wallet__plant wallet__leaves">
          {[blade(-14, 20, -6), blade(-7, 31, -3), blade(0, 36, 1), blade(7, 30, 3), blade(14, 21, 6)]}
        </g>
      )
    case 'JOINTING':
      return (
        <g className="wallet__plant wallet__leaves">
          {[stem(-7, 52), stem(0, 62), stem(7, 50)]}
          {[blade(-18, 26, -6), blade(16, 30, 7), blade(-11, 40, -4)]}
        </g>
      )
    case 'FLOWERING':
    case 'GRAIN_FILLING':
    case 'MATURITY': {
      const ripe = stage === 'MATURITY'
      const tilt = stage === 'FLOWERING' ? 0 : ripe ? 24 : 10
      return (
        <g className={`wallet__plant wallet__leaves wallet__plant--${stage.toLowerCase()}`}>
          {[stem(-8, 52), stem(0, 60), stem(8, 50)]}
          {[blade(-18, 24, -6), blade(17, 28, 7)]}
          {ear(CX - 8, b - 52, -8 + tilt * 0.6, 'e1')}
          {ear(CX, b - 60, tilt * 0.5, 'e2')}
          {ear(CX + 8, b - 50, 8 + tilt, 'e3')}
        </g>
      )
    }
  }
}
