# Boond dashboard: design brief

**Who and what.** A Punjab or Haryana wheat farmer opens this from the morning Web Push notification or the home-screen shortcut on a cheap Android phone, often outdoors in sun. Many read Hindi slowly or not at all. The page answers one question: *should I run the pump today, and how much?* Judges also see it in a 3-minute video, so the first screen must make the decision obvious in two seconds.

**Source of truth:** `Boond Live Build Specification` section 9 (Today, Water wallet, 16-day outlook, History, Validation replay). The data contract is `src/types.ts`; do not change shapes without updating the mock files and every consumer.

## Tokens (`src/styles/tokens.css`)
- `--nehar` canal blue: water, irrigation, primary actions. `--kanak` wheat gold: crop stage, season. `--mitti` soil brown: soil column, dry soil. `--loo` hot-wind red: heat warnings only. `--ok` green: healthy balance. Page `--page` cool field mist, ink `--ink` deep field green.
- Type: `--font-display` Tiro Devanagari Hindi (action word, headings), `--font-ui` Mukta (everything else, numbers). Scale `--step--1 … --step-4`. Body is 17px for outdoor reading.
- Touch targets at least `--tap` (48px). Gutter 16px. No horizontal scroll at 320px.

## Principles
1. **One bold thing:** the water wallet drawn as a soil cross-section (root zone, water level, stress line at RAW). Everything else is quiet.
2. **Colour is never the only signal.** Every action has a word and an icon as well as a colour.
3. **Hindi first.** Every visible string lives in a `strings` object `{ hi, en }` in the feature folder, read with `useStrings()` from `src/i18n.tsx`. Write natural, simple Hindi (village register, not Sanskritised). Units: मिमी, लीटर, यूनिट (kWh), °C.
4. **Plain words, farmer's view.** "पानी दें" not "सिंचाई अनुशंसित". Say what to do, how much, and why in one line.
5. **Honesty labels.** Seeded fields say "test field". Savings say "estimate". The replay says "simulation".
6. **Avoid template tells:** no all-caps labels, no eyebrow labels above every heading, no grids of identical rounded cards with soft shadows, no monospace data labels, no "→" on links, no gradient washes, no single-word accent colour in a headline, no fade-up on every section. One orchestrated motion moment at most per page (the wallet fill), and respect `prefers-reduced-motion`.
7. Charts are hand-built SVG (no chart library). Accessible: `role="img"` plus an `aria-label` summary, or a visually hidden table.

## File ownership (parallel work, do not edit other folders)
- `src/features/today/` hero: action word, amount, reason, audio player, rain/heat chips, soil-column water wallet.
- `src/features/outlook/` and `src/features/history/` 16-day outlook chart and history timeline.
- `src/features/replay/` the 2021-22 validation replay page.
- `scripts/` and `public/mock/` realistic mock data from real Open-Meteo weather.
- Shared files (`types.ts`, `i18n.tsx`, `format.ts`, `api.ts`, `index.css`, `tokens.css`, `components/`, `pages/`, `App.tsx`) belong to the lead. If you need a shared helper, put it in your own folder.
