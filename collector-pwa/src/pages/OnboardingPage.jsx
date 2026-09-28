import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../lib/api'
import { useSession } from '../state'
import { setLanguage } from '../i18n'

const LANGS = [
  { code: 'hi', label: 'हिंदी' },
  { code: 'mr', label: 'मराठी' },
  { code: 'en', label: 'English' }
]

const DISTRICTS = [
  'Pune',
  'Mumbai',
  'Nagpur',
  'Nashik',
  'Thane',
  'Aurangabad',
  'Other'
]

export default function OnboardingPage() {
  const { t } = useTranslation()
  const nav = useNavigate()
  const { profile, refreshProfile } = useSession()
  const [form, setForm] = useState({
    preferred_language: profile?.collector?.preferred_language || 'hi',
    display_name: profile?.user?.full_name || '',
    district: '',
    state: 'Maharashtra',
    latitude: null,
    longitude: null
  })
  const [geoMsg, setGeoMsg] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const useLocation = () => {
    if (!navigator.geolocation) {
      setGeoMsg(t('onboarding.locationDenied'))
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setForm((f) => ({
          ...f,
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude
        }))
        setGeoMsg(t('onboarding.locationCaptured'))
      },
      () => setGeoMsg(t('onboarding.locationDenied'))
    )
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.saveCollectorProfile({ ...form, phone: profile?.user?.phone || null })
      setLanguage(form.preferred_language)
      await refreshProfile()
      nav('/', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app-shell" style={{ paddingBottom: 0 }}>
      <header className="app-header">
        <h1>{t('onboarding.title')}</h1>
      </header>
      <main className="page">
        {error && <div className="error-box">{error}</div>}
        <form onSubmit={submit}>
          <div className="field">
            <label>{t('onboarding.language')}</label>
            <div className="chip-grid">
              {LANGS.map((l) => (
                <button
                  key={l.code}
                  type="button"
                  className={`chip ${form.preferred_language === l.code ? 'selected' : ''}`}
                  onClick={() => {
                    setForm({ ...form, preferred_language: l.code })
                    setLanguage(l.code)
                  }}
                >
                  {l.label}
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <label htmlFor="name">{t('auth.name')}</label>
            <input
              id="name"
              value={form.display_name}
              onChange={(e) => setForm({ ...form, display_name: e.target.value })}
            />
          </div>

          <div className="field">
            <label htmlFor="district">{t('onboarding.district')}</label>
            <select
              id="district"
              required
              value={form.district}
              onChange={(e) => setForm({ ...form, district: e.target.value })}
            >
              <option value="">—</option>
              {DISTRICTS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="state">{t('onboarding.state')}</label>
            <input
              id="state"
              value={form.state}
              onChange={(e) => setForm({ ...form, state: e.target.value })}
            />
          </div>

          <button type="button" className="btn-secondary" onClick={useLocation}>
            📍 {t('onboarding.useLocation')}
          </button>
          {geoMsg && <p className="muted">{geoMsg}</p>}

          <button className="btn-primary" type="submit" disabled={busy} style={{ marginTop: '0.8rem' }}>
            {busy ? <span className="spinner" /> : t('onboarding.finish')}
          </button>
        </form>
      </main>
    </div>
  )
}
