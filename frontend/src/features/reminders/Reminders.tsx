import { useEffect, useState } from 'react'
import { fetchConfig, savePushSubscription } from '../../api'
import { fill, useStrings, type Strings } from '../../i18n'
import { syncExistingSubscription } from './sync'
import './reminders.css'

const strings: Strings<{
  title: string
  intro: string
  turnOn: string
  working: string
  on: string
  denied: string
  ios: string
  unsupported: string
  failed: string
}> = {
  hi: {
    title: 'सुबह की याद',
    intro: 'हर सुबह 6 बजे फ़ोन पर बूँद की सलाह आएगी।',
    turnOn: 'याद दिलाना चालू करें',
    working: 'चालू कर रहे हैं…',
    on: 'चालू है। हर सुबह सलाह आएगी।',
    denied: 'फ़ोन ने सूचना की अनुमति नहीं दी। ब्राउज़र की सेटिंग में इस साइट के लिए सूचनाएँ चालू करें।',
    ios: 'iPhone पर: नीचे शेयर बटन दबाएँ, "होम स्क्रीन पर जोड़ें" चुनें, फिर वहाँ से बूँद खोलकर यह बटन दबाएँ।',
    unsupported: 'यह ब्राउज़र सूचनाएँ नहीं भेज सकता। Chrome में यह पेज खोलें।',
    failed: 'चालू नहीं हो सका ({msg})। फिर कोशिश करें।',
  },
  en: {
    title: 'Morning reminder',
    intro: "Boond's advice will arrive on this phone every morning at 6.",
    turnOn: 'Turn on reminders',
    working: 'Turning on…',
    on: 'On. The advice will arrive every morning.',
    denied: 'The phone did not allow notifications. Turn them on for this site in the browser settings.',
    ios: 'On iPhone: tap Share, choose "Add to Home Screen", then open Boond from there and tap this button.',
    unsupported: 'This browser cannot show notifications. Open this page in Chrome.',
    failed: 'Could not turn on ({msg}). Please try again.',
  },
}

type State = 'checking' | 'off' | 'working' | 'on' | 'denied' | 'ios' | 'unsupported' | 'failed'

// Web Push needs a service worker and PushManager. iPhones offer PushManager only to a
// page added to the Home Screen (iOS 16.4+); in-app browsers have none.
function initialState(): State {
  const standalone = window.matchMedia('(display-mode: standalone)').matches
  if (/iPhone|iPad|iPod/.test(navigator.userAgent) && !standalone) return 'ios'
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) return 'unsupported'
  if (Notification.permission === 'denied') return 'denied'
  return 'checking'
}

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padded = (base64 + '='.repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(padded)
  const bytes = new Uint8Array(new ArrayBuffer(raw.length))
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
  return bytes
}

export default function Reminders({ token }: { token: string }) {
  const t = useStrings(strings)
  const [state, setState] = useState<State>(initialState)
  const [error, setError] = useState('')

  useEffect(() => {
    if (state !== 'checking') return
    let live = true
    navigator.serviceWorker.ready
      .then((registration) => (Notification.permission === 'granted' ? syncExistingSubscription(token, registration) : false))
      .then((on) => live && setState(on ? 'on' : 'off'))
      .catch(() => live && setState('off'))
    return () => {
      live = false
    }
  }, [state, token])

  async function turnOn() {
    setState('working')
    try {
      const permission = await Notification.requestPermission()
      if (permission !== 'granted') {
        setState('denied')
        return
      }
      const [registration, config] = await Promise.all([navigator.serviceWorker.ready, fetchConfig()])
      if (!config.vapid_public_key) throw new Error('no push key on the server')
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(config.vapid_public_key),
      })
      await savePushSubscription(token, subscription.toJSON())
      setState('on')
    } catch (err) {
      setError((err as Error).message)
      setState('failed')
    }
  }

  const note: Partial<Record<State, string>> = {
    on: t.on,
    denied: t.denied,
    ios: t.ios,
    unsupported: t.unsupported,
    failed: fill(t.failed, { msg: error }),
  }
  const canTurnOn = state === 'off' || state === 'failed' || state === 'working'

  return (
    <section className="reminders" aria-labelledby="reminders-h">
      <h2 id="reminders-h" className="reminders__title">
        {t.title}
      </h2>
      <p className="reminders__intro">{t.intro}</p>
      {canTurnOn && (
        <button type="button" className="reminders__btn" disabled={state === 'working'} onClick={turnOn}>
          {state === 'working' ? t.working : t.turnOn}
        </button>
      )}
      {note[state] && (
        <p className={`reminders__note reminders__note--${state}`} role="status">
          {note[state]}
        </p>
      )}
    </section>
  )
}
