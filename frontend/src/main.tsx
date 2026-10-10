import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Fonts are bundled and served with the page (no Google Fonts request on slow rural links).
// Each file covers Devanagari and Latin with unicode-range, so phones fetch only what they show.
import '@fontsource/mukta/400.css'
import '@fontsource/mukta/500.css'
import '@fontsource/mukta/700.css'
import '@fontsource/tiro-devanagari-hindi/400.css'
import './index.css'
import App from './App.tsx'
import { LangProvider } from './LangProvider.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <LangProvider>
      <App />
    </LangProvider>
  </StrictMode>,
)
