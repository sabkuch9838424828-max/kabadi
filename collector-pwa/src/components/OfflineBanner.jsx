import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useOnline } from '../lib/hooks'
import { useSyncState } from '../state'
import { isSyncing, syncPendingLots } from '../lib/sync'

export default function OfflineBanner() {
  const { t } = useTranslation()
  const online = useOnline()
  const { pending, refreshPending } = useSyncState()
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    refreshPending().catch(() => {})
  }, [online, refreshPending])

  const onSync = async () => {
    setBusy(true)
    setMessage(null)
    const res = await syncPendingLots()
    setBusy(false)
    if (res.error) setMessage(t('offline.syncFailed', { message: res.error }))
    else if (res.synced) setMessage(t('offline.synced', { count: res.synced }))
    await refreshPending()
  }

  if (online && !pending) return null

  return (
    <div className={`offline-banner ${online ? 'online' : ''}`}>
      <span>
        {online
          ? t('offline.pending', { count: pending })
          : `${t('offline.title')} — ${t('offline.on')}`}
      </span>
      {online && pending > 0 && (
        <button onClick={onSync} disabled={busy || isSyncing()}>
          {busy ? <span className="spinner" /> : t('offline.syncNow')}
        </button>
      )}
      {message && <span className="sr-only">{message}</span>}
    </div>
  )
}
