import type { FieldResponse, ReplayResponse } from './types'
import { toFieldResponse, type LiveField, type RegisterBody } from './live'

// Live backend (API Gateway). Set in .env as VITE_API_BASE.
const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? ''

export const hasLiveApi = API_BASE !== ''

// Demo tokens always read the bundled mocks (real 2021-22 weather, test fields),
// so the video can show every state. Any other token is a real field.
export const MOCK_TOKENS = ['demo', 'irrigate', 'skip', 'wait', 'heat', 'waiting'] as const
export const isMockToken = (token: string) => !hasLiveApi || (MOCK_TOKENS as readonly string[]).includes(token)

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const msg = (body && (body.error || body.message)) || res.statusText
    throw new Error(`${res.status}: ${msg}`)
  }
  return body as T
}

export function fetchField(token: string): Promise<FieldResponse> {
  if (isMockToken(token)) {
    const safe = /^[a-z0-9-]+$/.test(token) ? token : 'demo'
    return getJson(`${import.meta.env.BASE_URL}mock/field-${safe}.json`)
  }
  return getJson<LiveField>(`${API_BASE}/fields/${encodeURIComponent(token)}`).then(toFieldResponse)
}

export async function registerField(body: RegisterBody): Promise<string> {
  const res = await getJson<{ field_token: string }>(`${API_BASE}/fields`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
  return res.field_token
}

// The backend has no GET /replay yet; the bundled replay is the same engine idea
// run on real 2021-22 Ludhiana weather (see scripts/make_mocks.py).
export function fetchReplay(): Promise<ReplayResponse> {
  return getJson(`${import.meta.env.BASE_URL}mock/replay.json`)
}

// Remember the farmer's field on this phone so the home screen opens it directly.
const KEY = 'boond.field'
export function savedToken(): string | null {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}
export function saveToken(token: string) {
  try {
    localStorage.setItem(KEY, token)
  } catch {
    /* storage unavailable: the link still works */
  }
}
