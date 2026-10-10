import { fetchField } from '../api'
import { useAsync } from '../useAsync'
import { LoadError, Loading } from '../components/LoadState'
import TodaySection from '../features/today/TodaySection'
import OutlookSection from '../features/outlook/OutlookSection'
import HistorySection from '../features/history/HistorySection'
import './FieldPage.css'

export default function FieldPage({ token }: { token: string }) {
  const state = useAsync(fetchField, token)
  if (state.status === 'loading') return <Loading />
  if (state.status === 'error') return <LoadError error={state.error} />
  const { field, today, outlook, history } = state.data

  return (
    <div className="field-page">
      <TodaySection field={field} today={today} />
      {today && outlook.length > 0 && <OutlookSection today={today} outlook={outlook} />}
      {history.length > 0 && <HistorySection history={history} />}
    </div>
  )
}
