import type { Action, Lang } from './types'

// The one action vocabulary for the whole dashboard: word, colour and icon per
// engine action. Today, the history timeline and the replay all read from here,
// so a farmer sees the same word, colour and glyph for the same advice everywhere.
// Colour is never the only signal: always show the word and the icon with it
// (the icon is src/components/ActionIcon.tsx).

interface Words {
  /** The big decision in the Today hero. */
  hero: string
  /** Small line above the hero word (heat protection only). */
  kicker?: string
  /** Compact places: timeline rows, replay day panel, slider text. */
  short: string
}

export const ACTION_WORDS: Record<Action, Record<Lang, Words>> = {
  IRRIGATE: {
    hi: { hero: 'आज पानी दें', short: 'पानी दें' },
    en: { hero: 'Water today', short: 'Water' },
  },
  SKIP: {
    hi: { hero: 'आज पानी न दें', short: 'पानी न दें' },
    en: { hero: 'Don’t water today', short: 'Don’t water' },
  },
  WAIT: {
    hi: { hero: 'अभी रुकें', short: 'रुकें' },
    en: { hero: 'Wait for now', short: 'Wait' },
  },
  HEAT_PROTECTION: {
    // The pump runs, so the hero says what to do; the kicker and every compact
    // place name the reason, so it never reads as a plain irrigation.
    hi: { hero: 'हल्का पानी दें', kicker: 'गर्मी से बचाव', short: 'गर्मी से बचाव' },
    en: { hero: 'Water lightly', kicker: 'Heat protection', short: 'Heat protection' },
  },
}

export function actionWord(action: Action, lang: Lang, form: 'hero' | 'short' = 'short'): string {
  return ACTION_WORDS[action][lang][form]
}

export function actionKicker(action: Action, lang: Lang): string | undefined {
  return ACTION_WORDS[action][lang].kicker
}

/** CSS class suffix, e.g. `today--heat`. */
export const ACTION_CLASS: Record<Action, 'irrigate' | 'skip' | 'wait' | 'heat'> = {
  IRRIGATE: 'irrigate',
  SKIP: 'skip',
  WAIT: 'wait',
  HEAT_PROTECTION: 'heat',
}

export const ACTION_COLOR: Record<Action, string> = {
  IRRIGATE: 'var(--action-irrigate)',
  SKIP: 'var(--action-skip)',
  WAIT: 'var(--action-wait)',
  HEAT_PROTECTION: 'var(--action-heat)',
}

export const ACTION_TINT: Record<Action, string> = {
  IRRIGATE: 'var(--nehar-tint)',
  SKIP: 'var(--ok-tint)',
  WAIT: 'var(--surface)',
  HEAT_PROTECTION: 'var(--loo-tint)',
}
