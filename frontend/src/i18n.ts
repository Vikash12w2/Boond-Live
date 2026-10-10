import { createContext, useContext } from 'react'
import type { Lang } from './types'

// Each feature keeps its own strings file shaped like { hi: {...}, en: {...} }
// and reads it with useStrings(strings). Hindi is the default (spec 9).
// The provider that owns the language state is in LangProvider.tsx.

type Dict = Record<string, string>
export type Strings<T extends Dict> = { hi: T; en: T }

export const LangContext = createContext<{ lang: Lang; setLang: (l: Lang) => void }>({
  lang: 'hi',
  setLang: () => {},
})

export function useLang() {
  return useContext(LangContext)
}

export function useStrings<T extends Dict>(strings: Strings<T>): T {
  return strings[useLang().lang]
}

// Fill "{name}" placeholders.
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, k: string) => String(values[k] ?? `{${k}}`))
}
