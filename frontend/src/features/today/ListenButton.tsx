import { useEffect, useRef, useState } from 'react'
import type { Lang } from '../../types'
import type { TodayStrings } from './strings'
import { SpeakerIcon } from './icons'

// Plays the Polly MP3 when there is one. Otherwise the phone reads the advice
// aloud with SpeechSynthesis (a hi-IN voice if installed). If neither works the
// button is disabled and says why.

type Mode = 'audio' | 'speech' | 'none'

function speechAvailable() {
  return typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window
}

function pickVoice(lang: Lang): SpeechSynthesisVoice | undefined {
  const want = lang === 'hi' ? 'hi' : 'en-IN'
  const voices = window.speechSynthesis.getVoices()
  return (
    voices.find((v) => v.lang.replace('_', '-').toLowerCase().startsWith(want.toLowerCase())) ??
    (lang === 'en' ? voices.find((v) => v.lang.toLowerCase().startsWith('en')) : undefined)
  )
}

export default function ListenButton({
  url,
  text,
  lang,
  t,
}: {
  url: string | null
  text: string
  lang: Lang
  t: TodayStrings
}) {
  const mode: Mode = url ? 'audio' : speechAvailable() ? 'speech' : 'none'
  const [playing, setPlaying] = useState(false)
  const [failed, setFailed] = useState<false | 'error' | 'no-voice'>(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  // Stop anything playing on unmount. The parent keys this component by language and
  // advice, so a change there remounts it with fresh state.
  useEffect(() => {
    return () => {
      audioRef.current?.pause()
      audioRef.current = null
      if (speechAvailable()) window.speechSynthesis.cancel()
    }
  }, [])

  // Some browsers load voices late; touching getVoices() early warms the list.
  useEffect(() => {
    if (mode === 'speech') window.speechSynthesis.getVoices()
  }, [mode])

  function stop() {
    audioRef.current?.pause()
    if (audioRef.current) audioRef.current.currentTime = 0
    if (mode === 'speech') window.speechSynthesis.cancel()
    setPlaying(false)
  }

  function play() {
    setFailed(false)
    if (mode === 'audio' && url) {
      if (!audioRef.current) {
        const a = new Audio(url)
        a.onended = () => setPlaying(false)
        a.onerror = () => {
          setPlaying(false)
          setFailed('error')
        }
        audioRef.current = a
      }
      audioRef.current.play().then(
        () => setPlaying(true),
        () => setFailed('error'),
      )
      return
    }
    if (mode === 'speech') {
      const synth = window.speechSynthesis
      synth.cancel()
      const u = new SpeechSynthesisUtterance(text)
      u.lang = lang === 'hi' ? 'hi-IN' : 'en-IN'
      const voice = pickVoice(lang)
      // A phone with voices but none for Hindi would read Hindi with an English voice.
      if (!voice && lang === 'hi' && synth.getVoices().length > 0) {
        setFailed('no-voice')
        return
      }
      if (voice) u.voice = voice
      u.rate = 0.9
      u.onend = () => setPlaying(false)
      u.onerror = (e) => {
        setPlaying(false)
        if (e.error !== 'canceled' && e.error !== 'interrupted') setFailed('error')
      }
      synth.speak(u)
      setPlaying(true)
    }
  }

  const note =
    mode === 'none'
      ? t.audio_unavailable
      : failed === 'no-voice'
        ? t.audio_no_hindi
        : failed
          ? t.audio_failed
          : mode === 'speech'
            ? t.audio_device_voice
            : null

  return (
    <div className="listen">
      <button
        type="button"
        className="listen__btn"
        onClick={playing ? stop : play}
        disabled={mode === 'none'}
        aria-describedby={note ? 'listen-note' : undefined}
      >
        <SpeakerIcon playing={playing} />
        <span>{playing ? t.stop : t.listen}</span>
      </button>
      {note && (
        <p id="listen-note" className={`listen__note${mode === 'none' || failed ? ' listen__note--warn' : ''}`} role={failed ? 'status' : undefined}>
          {note}
        </p>
      )}
    </div>
  )
}
