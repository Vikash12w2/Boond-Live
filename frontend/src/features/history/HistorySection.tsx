import { useState } from 'react'
import type { FarmerReport, HistoryDay, Lang } from '../../types'
import { fill, useLang, useStrings, type Strings } from '../../i18n'
import { num, parseDate } from '../../format'
import { ACTION_COLOR, ACTION_TINT, actionWord } from '../../actions'
import ActionIcon from '../../components/ActionIcon'
import './history.css'

const SHOW_FIRST = 7

const strings: Strings<{
  heading: string
  intro: string
  depth: string
  wallet: string
  walletLabel: string
  youSaid: string
  watered: string
  rained: string
  notToday: string
  approx: string
  failed: string
  pending: string
  showAll: string
  showLess: string
}> = {
  hi: {
    heading: 'पिछले दिन',
    intro: 'हर दिन की सलाह और आपने जो बताया।',
    depth: '{mm} मिमी',
    wallet: 'पानी {pct}%',
    walletLabel: 'खेत में पानी {pct}% बचा था',
    youSaid: 'आपने बताया:',
    watered: 'पानी दिया',
    rained: 'बारिश हुई',
    notToday: 'आज पानी नहीं दिया',
    approx: '~{mm} मिमी',
    failed: 'संदेश नहीं पहुँचा',
    pending: 'संदेश अभी भेजा जा रहा है',
    showAll: 'सब दिखाएँ ({n} दिन)',
    showLess: 'कम दिखाएँ',
  },
  en: {
    heading: 'Past days',
    intro: 'Each day’s advice, and what you told us.',
    depth: '{mm} mm',
    wallet: 'Water {pct}%',
    walletLabel: '{pct}% of the field’s water was left',
    youSaid: 'You said:',
    watered: 'watered',
    rained: 'it rained',
    notToday: 'did not water today',
    approx: '~{mm} mm',
    failed: 'Message not delivered',
    pending: 'Message still being sent',
    showAll: 'Show all ({n} days)',
    showLess: 'Show fewer',
  },
}

// Bot choices arrive verbatim in English (spec 6: Light/Normal/Heavy, Little/Moderate/Heavy).
const choiceWords: Record<string, Record<Lang, string>> = {
  light: { hi: 'हल्का', en: 'light' },
  normal: { hi: 'सामान्य', en: 'normal' },
  heavy: { hi: 'ज़्यादा', en: 'heavy' },
  little: { hi: 'थोड़ी', en: 'little' },
  moderate: { hi: 'ठीक-ठाक', en: 'moderate' },
}
const rainHeavy: Record<Lang, string> = { hi: 'तेज़', en: 'heavy' }

function choiceText(r: FarmerReport, lang: Lang): string {
  const key = r.choice.trim().toLowerCase()
  if (r.type === 'RAIN' && key === 'heavy') return rainHeavy[lang]
  return choiceWords[key]?.[lang] ?? r.choice
}

function dateParts(iso: string, lang: Lang) {
  const loc = lang === 'hi' ? 'hi-IN' : 'en-IN'
  const d = parseDate(iso)
  return {
    wd: new Intl.DateTimeFormat(loc, { weekday: 'short' }).format(d),
    dm: new Intl.DateTimeFormat(loc, { day: 'numeric', month: 'short' }).format(d),
  }
}

type T = (typeof strings)['hi']

function Report({ r, t, lang }: { r: FarmerReport; t: T; lang: Lang }) {
  let what = t.notToday
  let detail = ''
  if (r.type === 'WATERED' || r.type === 'RAIN') {
    what = r.type === 'WATERED' ? t.watered : t.rained
    const parts = [choiceText(r, lang)]
    if (r.mm_assumed > 0) parts.push(fill(t.approx, { mm: num(r.mm_assumed, lang) }))
    detail = ` (${parts.join(', ')})`
  }
  return (
    <p className="hist__said">
      <svg className="hist__said-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
        <path
          d="M4 5.5h16v10H10l-4.5 3.5v-3.5H4z"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinejoin="round"
        />
      </svg>
      <span>
        <strong>{t.youSaid}</strong> {what}
        {detail}
      </span>
    </p>
  )
}

export default function HistorySection({ history }: { history: HistoryDay[] }) {
  const t = useStrings(strings)
  const { lang } = useLang()
  const [all, setAll] = useState(false)
  const days = all ? history : history.slice(0, SHOW_FIRST)
  const more = history.length > SHOW_FIRST

  return (
    <section className="hist" aria-labelledby="history-h">
      <h2 id="history-h">{t.heading}</h2>
      <p className="hist__intro">{t.intro}</p>

      <ol className="hist__list" id="history-list">
        {days.map((d) => {
          const { wd, dm } = dateParts(d.date, lang)
          const pct = Math.max(0, Math.min(100, Math.round(d.water_wallet_pct)))
          const hasDepth = (d.action === 'IRRIGATE' || d.action === 'HEAT_PROTECTION') && d.depth_mm > 0
          // Quiet days (wait or skip, delivered, nothing reported) get one compact line so action days stand out.
          const quiet =
            (d.action === 'WAIT' || d.action === 'SKIP') && d.reports.length === 0 && d.delivery_status === 'DELIVERED'
          return (
            <li key={d.date} className={quiet ? 'hist__day hist__day--quiet' : 'hist__day'} data-action={d.action}>
              <span
                className="hist__node"
                style={{ color: ACTION_COLOR[d.action], background: ACTION_TINT[d.action] }}
              >
                <ActionIcon action={d.action} size={quiet ? 16 : 22} />
              </span>

              <div className="hist__body">
                <p className="hist__date">
                  <time dateTime={d.date}>
                    <span className="hist__wd">{wd}</span> {dm}
                  </time>
                </p>

                <p className="hist__head">
                  <span className="hist__word" style={{ color: ACTION_COLOR[d.action] }}>
                    {actionWord(d.action, lang)}
                  </span>
                  {hasDepth && <span className="hist__depth">{fill(t.depth, { mm: num(d.depth_mm, lang) })}</span>}
                </p>

                <p className="hist__wallet" title={fill(t.walletLabel, { pct: num(pct, lang) })}>
                  <span className="hist__meter" aria-hidden="true">
                    <span style={{ width: `${pct}%` }} />
                  </span>
                  <span className="visually-hidden">{fill(t.walletLabel, { pct: num(pct, lang) })}</span>
                  <span aria-hidden="true">{quiet ? `${num(pct, lang)}%` : fill(t.wallet, { pct: num(pct, lang) })}</span>
                </p>

                {!quiet && d.advice_text[lang] && <p className="hist__advice">{d.advice_text[lang]}</p>}

                {d.delivery_status === 'FAILED' && (
                  <p className="hist__delivery hist__delivery--failed">
                    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                      <path
                        d="M3.5 6.5h17v11h-17zM3.5 6.5l8.5 6.5 8.5-6.5M4 20L20 4"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinejoin="round"
                        strokeLinecap="round"
                      />
                    </svg>
                    {t.failed}
                  </p>
                )}
                {d.delivery_status === 'PENDING' && <p className="hist__delivery">{t.pending}</p>}

                {d.reports.map((r) => (
                  <Report key={r.at + r.type} r={r} t={t} lang={lang} />
                ))}
              </div>
            </li>
          )
        })}
      </ol>

      {more && (
        <button
          type="button"
          className="hist__toggle"
          aria-expanded={all}
          aria-controls="history-list"
          onClick={() => setAll((v) => !v)}
        >
          {all ? t.showLess : fill(t.showAll, { n: num(history.length, lang) })}
        </button>
      )}
    </section>
  )
}
