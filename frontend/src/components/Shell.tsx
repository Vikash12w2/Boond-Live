import type { ReactNode } from 'react'
import type { Route } from '../App'
import { useLang, useStrings, type Strings } from '../i18n'
import { isMockToken, savedToken } from '../api'
import './Shell.css'

const strings: Strings<{
  brand: string
  field: string
  register: string
  replay: string
  nav: string
  lang: string
  mock: string
  disclaimer: string
}> = {
  hi: {
    brand: 'बूँद',
    field: 'मेरा खेत',
    register: 'खेत जोड़ें',
    replay: '2021–22 की जाँच',
    nav: 'मुख्य',
    lang: 'भाषा',
    mock: 'नमूना डेटा दिखाया जा रहा है',
    disclaimer: 'यह सलाह फ़ैसले में मदद के लिए है। आख़िरी फ़ैसला किसान का है।',
  },
  en: {
    brand: 'Boond',
    field: 'My field',
    register: 'Add field',
    replay: '2021–22 check',
    nav: 'Main',
    lang: 'Language',
    mock: 'Showing sample data',
    disclaimer: 'This is decision support. The farmer makes the final decision.',
  },
}

export default function Shell({ route, children }: { route: Route; children: ReactNode }) {
  const t = useStrings(strings)
  const { lang, setLang } = useLang()
  const mine = savedToken()
  const fieldHref =
    route.name === 'field' ? `#/f/${encodeURIComponent(route.token)}` : mine ? `#/f/${encodeURIComponent(mine)}` : '#/f/demo'
  const showingSample = route.name === 'field' && isMockToken(route.token)

  return (
    <div className="shell">
      <header className="shell__bar">
        <a className="shell__brand" href={fieldHref}>
          <svg viewBox="0 0 32 32" width="22" height="22" aria-hidden="true">
            <path d="M16 3C16 3 6 15 6 21a10 10 0 0 0 20 0C26 15 16 3 16 3z" fill="currentColor" />
          </svg>
          <span>{t.brand}</span>
        </a>
        <nav className="shell__nav" aria-label={t.nav}>
          <a href={fieldHref} aria-current={route.name === 'field' ? 'page' : undefined}>
            {t.field}
          </a>
          <a href="#/register" aria-current={route.name === 'register' ? 'page' : undefined}>
            {t.register}
          </a>
          <a href="#/replay" aria-current={route.name === 'replay' ? 'page' : undefined}>
            {t.replay}
          </a>
        </nav>
        <div className="shell__lang" role="group" aria-label={t.lang}>
          <button type="button" aria-pressed={lang === 'hi'} onClick={() => setLang('hi')} lang="hi">
            हिंदी
          </button>
          <button type="button" aria-pressed={lang === 'en'} onClick={() => setLang('en')} lang="en">
            English
          </button>
        </div>
      </header>

      {showingSample && <p className="shell__mock">{t.mock}</p>}

      <main className="shell__main">{children}</main>

      <footer className="shell__foot">
        <p>{t.disclaimer}</p>
      </footer>
    </div>
  )
}
