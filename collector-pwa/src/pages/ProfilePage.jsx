import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../lib/api'
import { clearAll } from '../lib/db'
import { useSession } from '../state'
import { setLanguage } from '../i18n'
import { syncPendingLots } from '../lib/sync'
import { useSyncState } from '../state'

const LANGS = [
  { code: 'hi', label: 'हिंदी' },
  { code: 'mr', label: 'मराठी' },
  { code: 'en', label: 'English' }
]

export default function ProfilePage({ onLogout }) {
  const { t, i18n } = useTranslation()
  const { session, profile, refreshProfile } = useSession()
  const { pending, refreshPending } = useSyncState()
  const [form, setForm] = useState({ preferred_language: i18n.language, district: '', state: '' })
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (profile?.collector) {
      setForm({
        preferred_language: profile.collector.preferred_language || i18n.language,
        district: profile.collector.district || '',
        state: profile.collector.state || ''
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile])

  const save = async () => {
    setBusy(true)
    try {
      await api.saveCollectorProfile(form)
      setLanguage(form.preferred_language)
      await refreshProfile()
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setBusy(false)
    }
  }

  const syncNow = async () => {
    await syncPendingLots()
    await refreshPending()
  }

  const wipe = async () => {
    if (!confirm('Delete all data stored on this phone? Synced lots remain on the server.')) return
    await clearAll()
    await refreshPending()
    window.location.reload()
  }

  return (
    <div>
      <header className="app-header">
        <h1>{t('profile.title')}</h1>
      </header>
      <main className="page">
        <div className="card">
          <p style={{ margin: 0 }}>
            <strong>{profile?.user?.full_name || session?.name}</strong>
          </p>
          <p className="muted" style={{ margin: '0.2rem 0 0' }}>
            {profile?.user?.email} · {t('auth.role.collector')}
          </p>
        </div>

        {saved && <div className="info-box">✅ {t('profile.saved')}</div>}

        <div className="field">
          <label>{t('profile.language')}</label>
          <select
            value={form.preferred_language}
            onChange={(e) => {
              setForm({ ...form, preferred_language: e.target.value })
              setLanguage(e.target.value)
            }}
          >
            {LANGS.map((l) => (
              <option key={l.code} value={l.code}>
                {l.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>{t('profile.district')}</label>
          <input value={form.district} onChange={(e) => setForm({ ...form, district: e.target.value })} />
        </div>
        <div className="field">
          <label>{t('onboarding.state')}</label>
          <input value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })} />
        </div>

        <button className="btn-primary" onClick={save} disabled={busy}>
          {busy ? <span className="spinner" /> : t('common.save')}
        </button>

        <div className="card" style={{ marginTop: '0.9rem' }}>
          <div className="row-between">
            <span>{t('offline.pending', { count: pending })}</span>
            <button className="btn-secondary" style={{ width: 'auto' }} onClick={syncNow} disabled={!pending}>
              {t('offline.syncNow')}
            </button>
          </div>
        </div>

        <button className="btn-danger" onClick={onLogout} style={{ marginTop: '0.5rem' }}>
          {t('auth.logout')}
        </button>
        <button className="btn-ghost" onClick={wipe} style={{ width: '100%', marginTop: '0.4rem' }}>
          Clear local data
        </button>
      </main>
    </div>
  )
}
