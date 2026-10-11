import { useEffect, useState, type ReactNode } from 'react'
import { LangContext } from './i18n'
import type { Lang } from './types'

function initialLang(): Lang {
  const fromUrl = new URLSearchParams(window.location.search).get('lang')
  if (fromUrl === 'hi' || fromUrl === 'en') return fromUrl
  try {
    const saved = localStorage.getItem('boond.lang')
    if (saved === 'hi' || saved === 'en') return saved
  } catch {
    /* storage unavailable */
  }
  return 'hi'
}

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(initialLang)
  useEffect(() => {
    document.documentElement.lang = lang
    try {
      localStorage.setItem('boond.lang', lang)
    } catch {
      /* storage unavailable */
    }
  }, [lang])
  return <LangContext.Provider value={{ lang, setLang }}>{children}</LangContext.Provider>
}
