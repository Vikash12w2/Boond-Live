# Boond dashboard

Mobile-first, Hindi-first dashboard for one field (Live Build Spec section 9). A field lives at `#/f/<token>`; the phone remembers its token, and the morning Web Push notification (sent by the backend) will open that page.

```bash
npm install
npm run dev          # http://localhost:5173
npm run build        # outputs dist/ for Amplify Hosting
```

## Data
- `VITE_API_BASE` points the page at the backend API (API Gateway). Set it in `.env.local` for development (see `.env.example`) and as an environment variable in Amplify Hosting. Without it the page runs on the bundled mocks and opens the demo field. `src/live.ts` adapts the API's responses to `src/types.ts`.
  - `POST /fields` (register page) returns `field_token`; the token is saved on the phone and the home screen opens that field.
  - `GET /fields/{token}` returns the profile, `state` and `latest_advice` (the engine's advice, null until the daily job runs).
- The demo tokens (`demo`, `irrigate`, `skip`, `wait`, `heat`, `waiting`) always read `public/mock/`: real 2021-22 Ludhiana weather run through a simplified FAO-56 wheat balance in `scripts/make_mocks.py`, labelled as test fields. These snapshots are not engine output.
- The replay page reads `public/mock/replay.json`, built from the real engine by `scripts/make_replay.py` (the same run as `python replay/replay.py`, sown 5 Nov 2021, loam), against the PAU calendar in `engine/baseline.json`.
- `src/live.ts` reads `../engine/soils.json`, so build from the whole repository (Amplify app root `frontend/`).
- The API's CORS must allow the page's origin (dev server `http://localhost:5173`, the Amplify URL, or `*`).

Regenerate and check the mocks (offline, uses the cached weather; run from `frontend/`):
```bash
python3 -I scripts/make_mocks.py
python3 -I scripts/make_replay.py
python3 -I scripts/validate_mocks.py
```

## Routes
| Route | Shows |
|---|---|
| `#/f/demo` | Heat protection day (27 Mar 2022) |
| `#/f/irrigate`, `#/f/skip`, `#/f/wait`, `#/f/heat` | One test field per action |
| `#/f/waiting` | Field not sown yet |
| `#/f/<token>` | A real field from the live API |
| `#/register` | Add a field (POST /fields) |
| `#/replay` | 2021-22 season replay from the engine: Boond vs the PAU calendar |

Add `?lang=en` for English. Design rules are in `DESIGN.md`.
