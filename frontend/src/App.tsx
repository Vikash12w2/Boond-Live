import { useEffect, useState } from 'react'
import Shell from './components/Shell'
import FieldPage from './pages/FieldPage'
import RegisterPage from './pages/RegisterPage'
import ReplayPage from './features/replay/ReplayPage'
import { hasLiveApi, savedToken } from './api'

// Hash routes keep Amplify static hosting simple (no rewrite rules needed).
//   #/f/<token>  one field's dashboard (demo tokens: demo, irrigate, skip, wait, heat, waiting)
//   #/register   add a field (POST /fields)
//   #/replay     2021-22 validation replay
//   anything else -> this phone's saved field, else register (live) or the demo field
export type Route = { name: 'field'; token: string } | { name: 'replay' } | { name: 'register' }

function parse(hash: string): Route {
  const path = hash.replace(/^#/, '')
  if (path.startsWith('/replay')) return { name: 'replay' }
  if (path.startsWith('/register')) return { name: 'register' }
  const m = path.match(/^\/f\/([^/?]+)/)
  if (m) return { name: 'field', token: decodeURIComponent(m[1]) }
  const mine = savedToken()
  if (mine) return { name: 'field', token: mine }
  return hasLiveApi ? { name: 'register' } : { name: 'field', token: 'demo' }
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash))
  useEffect(() => {
    const onHash = () => {
      setRoute(parse(window.location.hash))
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  return (
    <Shell route={route}>
      {route.name === 'replay' ? (
        <ReplayPage />
      ) : route.name === 'register' ? (
        <RegisterPage />
      ) : (
        <FieldPage token={route.token} />
      )}
    </Shell>
  )
}
