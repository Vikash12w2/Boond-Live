import { useEffect, useState } from 'react'

export type AsyncState<T> = { status: 'loading' } | { status: 'error'; error: Error } | { status: 'ready'; data: T }

// Load data for one key, e.g. useAsync(fetchField, token). `load` must be a stable
// (module-level) function. While a new key is loading the previous result is not
// shown: the state is "loading" until the result for this key arrives.
export function useAsync<T>(load: (key: string) => Promise<T>, key = ''): AsyncState<T> {
  const [result, setResult] = useState<{ key: string; state: AsyncState<T> } | null>(null)
  useEffect(() => {
    let live = true
    load(key).then(
      (data) => live && setResult({ key, state: { status: 'ready', data } }),
      (error: Error) => live && setResult({ key, state: { status: 'error', error } }),
    )
    return () => {
      live = false
    }
  }, [load, key])
  return result && result.key === key ? result.state : { status: 'loading' }
}
