import { useState, type FormEvent } from 'react'
import { registerField, saveToken } from '../api'
import { fill, useLang, useStrings, type Strings } from '../i18n'
import type { RegisterBody } from '../live'
import './RegisterPage.css'

type SoilKey = RegisterBody['soil']

const strings: Strings<{
  title: string
  intro: string
  where: string
  useLocation: string
  locating: string
  located: string
  locationDenied: string
  typeLocation: string
  lat: string
  lon: string
  crop: string
  wheat: string
  sowing: string
  sowingHint: string
  soil: string
  sandy: string
  sandyHint: string
  loam: string
  loamHint: string
  clay: string
  clayHint: string
  area: string
  areaUnit: string
  lift: string
  liftHint: string
  liftUnit: string
  pump: string
  electric: string
  submit: string
  saving: string
  needLocation: string
  badLocation: string
  failed: string
  privacy: string
  consent: string
  needConsent: string
}> = {
  hi: {
    title: 'अपना खेत जोड़ें',
    intro: 'पाँच छोटे सवाल। इसके बाद हर सुबह बताएँगे कि आज पानी देना है या नहीं, और कितना।',
    where: 'खेत कहाँ है?',
    useLocation: 'मेरी जगह लें',
    locating: 'जगह ढूँढ रहे हैं…',
    located: 'जगह मिल गई: {lat}°N, {lon}°E',
    locationDenied: 'फ़ोन ने जगह नहीं दी। नीचे खुद लिखें।',
    typeLocation: 'जगह खुद लिखें',
    lat: 'अक्षांश (latitude)',
    lon: 'देशांतर (longitude)',
    crop: 'फ़सल',
    wheat: 'गेहूँ',
    sowing: 'बुवाई की तारीख',
    sowingHint: 'अभी बुवाई नहीं हुई तो अंदाज़न तारीख डालें।',
    soil: 'मिट्टी कैसी है?',
    sandy: 'रेतीली',
    sandyHint: 'पानी जल्दी सूख जाता है',
    loam: 'दोमट',
    loamHint: 'न ज़्यादा भारी, न हल्की',
    clay: 'चिकनी',
    clayHint: 'पानी देर तक रुकता है',
    area: 'खेत कितना बड़ा है?',
    areaUnit: 'एकड़',
    lift: 'पानी कितनी गहराई से खींचते हैं?',
    liftHint: 'बोरवेल की गहराई। पता न हो तो 30 रहने दें।',
    liftUnit: 'मीटर',
    pump: 'पंप',
    electric: 'बिजली का पंप',
    submit: 'खेत जोड़ें',
    saving: 'जोड़ रहे हैं…',
    needLocation: 'पहले खेत की जगह दें।',
    badLocation: 'यह जगह सही नहीं लगती। अक्षांश -90 से 90 और देशांतर -180 से 180 के बीच होना चाहिए।',
    failed: 'खेत नहीं जुड़ सका ({msg})। इंटरनेट जाँचें और फिर कोशिश करें।',
    privacy: 'हम सिर्फ़ खेत की लगभग जगह (1 किमी तक) और ये जवाब रखते हैं। नाम या फ़ोन नंबर नहीं।',
    consent: 'मैं सहमत हूँ कि बूँद मेरे खेत की लगभग जगह और ये जवाब रखे, ताकि हर सुबह सलाह दे सके। मैं कभी भी अपना डेटा मिटा सकता/सकती हूँ।',
    needConsent: 'आगे बढ़ने के लिए ऊपर सहमति पर निशान लगाएँ।',
  },
  en: {
    title: 'Add your field',
    intro: 'Five short questions. Then every morning we tell you whether to water today, and how much.',
    where: 'Where is the field?',
    useLocation: 'Use my location',
    locating: 'Finding your location…',
    located: 'Location found: {lat}°N, {lon}°E',
    locationDenied: 'The phone did not share its location. Type it below.',
    typeLocation: 'Type the location',
    lat: 'Latitude',
    lon: 'Longitude',
    crop: 'Crop',
    wheat: 'Wheat',
    sowing: 'Sowing date',
    sowingHint: 'Not sown yet? Enter the expected date.',
    soil: 'What is the soil like?',
    sandy: 'Sandy',
    sandyHint: 'Dries out quickly',
    loam: 'Loam',
    loamHint: 'Neither heavy nor light',
    clay: 'Clay',
    clayHint: 'Holds water for long',
    area: 'How big is the field?',
    areaUnit: 'acres',
    lift: 'How deep is the water you pump?',
    liftHint: 'Borewell depth. Leave 30 if you are not sure.',
    liftUnit: 'metres',
    pump: 'Pump',
    electric: 'Electric pump',
    submit: 'Add field',
    saving: 'Adding…',
    needLocation: 'Give the field location first.',
    badLocation: 'That location does not look right. Latitude must be between -90 and 90, longitude between -180 and 180.',
    failed: 'Could not add the field ({msg}). Check your connection and try again.',
    privacy: 'We keep only the rough field location (about 1 km) and these answers. No name or phone number.',
    consent: 'I agree that Boond keeps my field\'s rough location and these answers so it can advise me every morning. I can delete my data at any time.',
    needConsent: 'Tick the agreement above to continue.',
  },
}

const round2 = (n: number) => Math.round(n * 100) / 100

export default function RegisterPage() {
  const t = useStrings(strings)
  const { lang } = useLang()
  const [lat, setLat] = useState('')
  const [lon, setLon] = useState('')
  const [geo, setGeo] = useState<'idle' | 'busy' | 'ok' | 'denied'>('idle')
  const [manual, setManual] = useState(false)
  const [sowing, setSowing] = useState('')
  const [soil, setSoil] = useState<SoilKey>('loam')
  const [area, setArea] = useState('1')
  const [lift, setLift] = useState('30')
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const locate = () => {
    if (!navigator.geolocation) {
      setGeo('denied')
      setManual(true)
      return
    }
    setGeo('busy')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(String(round2(pos.coords.latitude)))
        setLon(String(round2(pos.coords.longitude)))
        setGeo('ok')
      },
      () => {
        setGeo('denied')
        setManual(true)
      },
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 600000 },
    )
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    const la = Number(lat)
    const lo = Number(lon)
    if (!lat || !lon || !Number.isFinite(la) || !Number.isFinite(lo)) {
      setError(t.needLocation)
      return
    }
    if (Math.abs(la) > 90 || Math.abs(lo) > 180) {
      setError(t.badLocation)
      return
    }
    if (!consent) {
      setError(t.needConsent)
      return
    }
    setBusy(true)
    try {
      const token = await registerField({
        language: lang,
        latitude: round2(la),
        longitude: round2(lo),
        crop: 'wheat',
        sowing_date: sowing,
        soil,
        area_acres: Number(area),
        pump_type: 'electric',
        lift_m: Number(lift) || 30,
        consent: true,
      })
      saveToken(token)
      window.location.hash = `#/f/${encodeURIComponent(token)}`
    } catch (err) {
      setError(fill(t.failed, { msg: (err as Error).message }))
      setBusy(false)
    }
  }

  const soils: { key: SoilKey; name: string; hint: string }[] = [
    { key: 'sandy', name: t.sandy, hint: t.sandyHint },
    { key: 'loam', name: t.loam, hint: t.loamHint },
    { key: 'clay', name: t.clay, hint: t.clayHint },
  ]

  return (
    <form className="reg" onSubmit={submit} noValidate={false}>
      <h1 className="reg__title">{t.title}</h1>
      <p className="reg__intro">{t.intro}</p>

      <fieldset className="reg__q">
        <legend>{t.where}</legend>
        <button type="button" className="reg__locate" onClick={locate} disabled={geo === 'busy'}>
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            <path
              d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21zm0-8.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"
              fill="currentColor"
            />
          </svg>
          {geo === 'busy' ? t.locating : t.useLocation}
        </button>
        <p className="reg__status" role="status">
          {geo === 'ok' && fill(t.located, { lat, lon })}
          {geo === 'denied' && t.locationDenied}
        </p>
        {!manual && geo !== 'ok' && (
          <button type="button" className="reg__link" onClick={() => setManual(true)}>
            {t.typeLocation}
          </button>
        )}
        {manual && (
          <div className="reg__pair">
            <label>
              <span>{t.lat}</span>
              <input inputMode="decimal" value={lat} onChange={(e) => setLat(e.target.value)} placeholder="30.90" />
            </label>
            <label>
              <span>{t.lon}</span>
              <input inputMode="decimal" value={lon} onChange={(e) => setLon(e.target.value)} placeholder="75.85" />
            </label>
          </div>
        )}
      </fieldset>

      <div className="reg__q">
        <p className="reg__label">{t.crop}</p>
        <p className="reg__fixed">{t.wheat}</p>
      </div>

      <label className="reg__q">
        <span className="reg__label">{t.sowing}</span>
        <span className="reg__hint">{t.sowingHint}</span>
        <input type="date" required value={sowing} onChange={(e) => setSowing(e.target.value)} />
      </label>

      <fieldset className="reg__q">
        <legend>{t.soil}</legend>
        <div className="reg__choices">
          {soils.map((s) => (
            <label key={s.key} className="reg__choice">
              <input type="radio" name="soil" value={s.key} checked={soil === s.key} onChange={() => setSoil(s.key)} />
              <span className="reg__choice-name">{s.name}</span>
              <span className="reg__choice-hint">{s.hint}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <label className="reg__q">
        <span className="reg__label">{t.area}</span>
        <span className="reg__unit-row">
          <input type="number" required min="0.1" step="0.1" inputMode="decimal" value={area} onChange={(e) => setArea(e.target.value)} />
          <span>{t.areaUnit}</span>
        </span>
      </label>

      <label className="reg__q">
        <span className="reg__label">{t.lift}</span>
        <span className="reg__hint">{t.liftHint}</span>
        <span className="reg__unit-row">
          <input type="number" min="1" max="300" step="1" inputMode="numeric" value={lift} onChange={(e) => setLift(e.target.value)} />
          <span>{t.liftUnit}</span>
        </span>
      </label>

      <div className="reg__q">
        <p className="reg__label">{t.pump}</p>
        <p className="reg__fixed">{t.electric}</p>
      </div>

      <label className="reg__consent">
        <input type="checkbox" required checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>{t.consent}</span>
      </label>

      {error && (
        <p className="reg__error" role="alert">
          {error}
        </p>
      )}

      <button type="submit" className="reg__submit" disabled={busy}>
        {busy ? t.saving : t.submit}
      </button>
      <p className="reg__privacy">{t.privacy}</p>
    </form>
  )
}
