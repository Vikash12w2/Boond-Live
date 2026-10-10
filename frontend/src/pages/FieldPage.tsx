import { useState } from 'react'
import { fetchField, isMockToken } from '../api'
import { useAsync } from '../useAsync'
import { LoadError, Loading } from '../components/LoadState'
import TodaySection, { Unavailable } from '../features/today/TodaySection'
import OutlookSection from '../features/outlook/OutlookSection'
import HistorySection from '../features/history/HistorySection'
import CheckIn from '../features/checkin/CheckIn'
import DeleteField from '../features/settings/DeleteField'
import Reminders from '../features/reminders/Reminders'
import './FieldPage.css'

// The key carries a reload counter ("<n>:<token>") so a check-in can refetch the field.
const loadField = (key: string) => fetchField(key.slice(key.indexOf(':') + 1))

export default function FieldPage({ token }: { token: string }) {
  const [reloads, setReloads] = useState(0)
  const [saved, setSaved] = useState<string | null>(null)
  const state = useAsync(loadField, `${reloads}:${token}`)
  if (state.status === 'loading') return <Loading />
  if (state.status === 'error') return <LoadError error={state.error} />
  const { field, today, outlook, history, unavailable } = state.data
  const live = !isMockToken(token)

  return (
    <div className="field-page">
      {unavailable ? (
        <Unavailable field={field} date={unavailable.date} text={unavailable.text} />
      ) : (
        <TodaySection field={field} today={today} />
      )}
      {live && today && (
        <CheckIn
          token={token}
          saved={saved}
          onSaved={(message) => {
            setSaved(message)
            setReloads((n) => n + 1)
          }}
        />
      )}
      {live && <Reminders token={token} />}
      {today && outlook.length > 0 && <OutlookSection today={today} outlook={outlook} />}
      {history.length > 0 && <HistorySection history={history} />}
      {live && <DeleteField token={token} />}
    </div>
  )
}
