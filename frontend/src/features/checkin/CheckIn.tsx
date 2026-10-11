import { useState } from 'react'
import { postEvent, type CheckInType } from '../../api'
import { istDate } from '../../format'
import { fill, useStrings } from '../../i18n'
import { strings } from './strings'
import './checkin.css'

// Farmer check-ins (spec 5). Levels are the engine's own keys (engine/checkins.py):
// watered light / normal / heavy, rain little / moderate / heavy. The backend stores
// the choice and recomputes; the engine applies a day's check-in to the balance from
// the next morning, so a check-in for today changes tomorrow's advice.

type Choice = { type: CheckInType; level: string; label: 'light' | 'normal' | 'heavy' | 'little' | 'moderate' | 'heavyRain' }

const WATERED: Choice[] = [
  { type: 'WATERED', level: 'light', label: 'light' },
  { type: 'WATERED', level: 'normal', label: 'normal' },
  { type: 'WATERED', level: 'heavy', label: 'heavy' },
]
const RAIN: Choice[] = [
  { type: 'RAIN', level: 'little', label: 'little' },
  { type: 'RAIN', level: 'moderate', label: 'moderate' },
  { type: 'RAIN', level: 'heavy', label: 'heavyRain' },
]

// `saved` is kept by the field page so the confirmation survives the reload that follows a check-in.
export default function CheckIn({ token, saved, onSaved }: { token: string; saved: string | null; onSaved: (message: string) => void }) {
  const t = useStrings(strings)
  const [offset, setOffset] = useState<0 | -1>(0)
  const [status, setStatus] = useState<{ kind: 'busy' | 'error'; text: string } | null>(null)

  async function save(choice: Choice) {
    setStatus({ kind: 'busy', text: t.saving })
    try {
      await postEvent(token, { type: choice.type, level: choice.level, date: istDate(offset) })
      setStatus(null)
      onSaved(offset === 0 ? t.savedToday : t.savedYesterday)
    } catch (err) {
      setStatus({ kind: 'error', text: fill(t.failed, { msg: (err as Error).message }) })
    }
  }

  const busy = status?.kind === 'busy'
  const group = (title: string, choices: Choice[]) => (
    <fieldset className="checkin__group">
      <legend>{title}</legend>
      <div className="checkin__buttons">
        {choices.map((c) => (
          <button key={c.level} type="button" className="checkin__btn" disabled={busy} onClick={() => save(c)}>
            {t[c.label]}
          </button>
        ))}
      </div>
    </fieldset>
  )

  return (
    <section className="checkin" aria-labelledby="checkin-h">
      <h2 id="checkin-h" className="checkin__title">
        {t.title}
      </h2>
      <p className="checkin__intro">{t.intro}</p>
      <div className="checkin__day" role="group" aria-label={t.day}>
        <button type="button" aria-pressed={offset === 0} onClick={() => setOffset(0)}>
          {t.today}
        </button>
        <button type="button" aria-pressed={offset === -1} onClick={() => setOffset(-1)}>
          {t.yesterday}
        </button>
      </div>
      {group(t.watered, WATERED)}
      {group(t.rained, RAIN)}
      {(status || saved) && (
        <p className={`checkin__status checkin__status--${status ? status.kind : 'ok'}`} role="status">
          {status ? status.text : saved}
        </p>
      )}
    </section>
  )
}
