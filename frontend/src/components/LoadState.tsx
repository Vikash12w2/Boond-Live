import { useStrings, type Strings } from '../i18n'

const strings: Strings<{ loading: string; error: string; retry: string }> = {
  hi: {
    loading: 'खेत की जानकारी आ रही है…',
    error: 'जानकारी नहीं मिल सकी। इंटरनेट जाँचें और फिर कोशिश करें।',
    retry: 'फिर कोशिश करें',
  },
  en: {
    loading: 'Loading your field…',
    error: 'Could not load the data. Check your connection and try again.',
    retry: 'Try again',
  },
}

export function Loading() {
  const t = useStrings(strings)
  return (
    <p role="status" style={{ color: 'var(--ink-soft)', padding: 'var(--s6) 0' }}>
      {t.loading}
    </p>
  )
}

export function LoadError({ error }: { error: Error }) {
  const t = useStrings(strings)
  return (
    <div role="alert" style={{ padding: 'var(--s6) 0', display: 'grid', gap: 'var(--s3)', justifyItems: 'start' }}>
      <p>{t.error}</p>
      <p style={{ fontSize: 'var(--step--1)', color: 'var(--ink-soft)' }}>{error.message}</p>
      <button
        type="button"
        onClick={() => window.location.reload()}
        style={{
          minHeight: 'var(--tap)',
          padding: '0 var(--s5)',
          border: '1px solid var(--nehar)',
          background: 'transparent',
          color: 'var(--nehar)',
          borderRadius: 'var(--radius-sm)',
          cursor: 'pointer',
        }}
      >
        {t.retry}
      </button>
    </div>
  )
}
