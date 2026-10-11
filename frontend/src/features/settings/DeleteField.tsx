import { useState } from 'react'
import { deleteField, forgetToken } from '../../api'
import { fill, useStrings, type Strings } from '../../i18n'
import './settings.css'

const strings: Strings<{ title: string; button: string; confirm: string; yes: string; no: string; deleting: string; failed: string }> = {
  hi: {
    title: 'मेरा डेटा',
    button: 'मेरा डेटा मिटाएँ',
    confirm: 'इस खेत की सारी जानकारी हमेशा के लिए मिट जाएगी। पक्का?',
    yes: 'हाँ, मिटाएँ',
    no: 'रहने दें',
    deleting: 'मिटा रहे हैं…',
    failed: 'नहीं मिट सका ({msg})। फिर कोशिश करें।',
  },
  en: {
    title: 'My data',
    button: 'Delete my data',
    confirm: 'Everything about this field will be deleted for good. Are you sure?',
    yes: 'Yes, delete',
    no: 'Cancel',
    deleting: 'Deleting…',
    failed: 'Could not delete ({msg}). Please try again.',
  },
}

// Spec 11: "Delete my data" removes every item of the field on the server, then this
// phone forgets the field and opens the registration page.
export default function DeleteField({ token }: { token: string }) {
  const t = useStrings(strings)
  const [step, setStep] = useState<'idle' | 'confirm' | 'busy'>('idle')
  const [error, setError] = useState<string | null>(null)

  async function remove() {
    setStep('busy')
    setError(null)
    try {
      await deleteField(token)
      forgetToken()
      window.location.hash = '#/register'
    } catch (err) {
      setError(fill(t.failed, { msg: (err as Error).message }))
      setStep('confirm')
    }
  }

  return (
    <section className="settings" aria-labelledby="settings-h">
      <h2 id="settings-h" className="settings__title">
        {t.title}
      </h2>
      {step === 'idle' ? (
        <button type="button" className="settings__danger" onClick={() => setStep('confirm')}>
          {t.button}
        </button>
      ) : (
        <div className="settings__confirm" role="group" aria-label={t.button}>
          <p>{t.confirm}</p>
          <button type="button" className="settings__danger" disabled={step === 'busy'} onClick={remove}>
            {step === 'busy' ? t.deleting : t.yes}
          </button>
          <button type="button" className="settings__plain" disabled={step === 'busy'} onClick={() => setStep('idle')}>
            {t.no}
          </button>
        </div>
      )}
      {error && <p role="alert" className="settings__error">{error}</p>}
    </section>
  )
}
