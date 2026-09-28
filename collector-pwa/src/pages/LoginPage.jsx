import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSession } from '../state'
import { setLanguage } from '../i18n'

const LANGS = [
  { code: 'hi', label: 'हिंदी' },
  { code: 'mr', label: 'मराठी' },
  { code: 'en', label: 'English' }
]

export default function LoginPage() {
  const { t, i18n } = useTranslation()
  const { login, register } = useSession()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ email: '', password: '', full_name: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      if (mode === 'login') {
        await login(form.email.trim(), form.password)
      } else {
        if (form.full_name.trim().length < 2) throw new Error('Please enter your name')
        await register({
          email: form.email.trim(),
          password: form.password,
          full_name: form.full_name.trim()
        })
      }
    } catch (err) {
      setError(err.message || t('common.somethingWentWrong'))
    } finally {
      setBusy(false)
    }
  }

  const useDemo = () => {
    setMode('login')
    setForm({ ...form, email: 'ravi@kabadiwala.in', password: 'Collector@123' })
  }

  return (
    <div className="app-shell" style={{ paddingBottom: 0 }}>
      <header className="app-header">
        <div>
          <h1>♻️ {t('app.name')}</h1>
          <div className="sub">{t('app.tagline')}</div>
        </div>
        <select
          aria-label={t('profile.language')}
          value={i18n.language}
          onChange={(e) => setLanguage(e.target.value)}
          style={{
            background: 'rgba(255,255,255,0.2)',
            color: '#fff',
            border: 'none',
            borderRadius: 10,
            minHeight: 40,
            padding: '0 0.5rem'
          }}
        >
          {LANGS.map((l) => (
            <option key={l.code} value={l.code} style={{ color: '#0f172a' }}>
              {l.label}
            </option>
          ))}
        </select>
      </header>

      <main className="page">
        <h2>{mode === 'login' ? t('auth.login') : t('auth.register')}</h2>
        {error && <div className="error-box">{error}</div>}

        <form onSubmit={submit}>
          {mode === 'register' && (
            <div className="field">
              <label htmlFor="full_name">{t('auth.name')}</label>
              <input id="full_name" value={form.full_name} onChange={set('full_name')} autoComplete="name" />
            </div>
          )}
          <div className="field">
            <label htmlFor="email">{t('auth.email')}</label>
            <input
              id="email"
              type="email"
              required
              value={form.email}
              onChange={set('email')}
              autoComplete="username"
              inputMode="email"
            />
          </div>
          <div className="field">
            <label htmlFor="password">{t('auth.password')}</label>
            <input
              id="password"
              type="password"
              required
              minLength={6}
              value={form.password}
              onChange={set('password')}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
          </div>

          <button className="btn-primary" type="submit" disabled={busy}>
            {busy ? <span className="spinner" /> : mode === 'login' ? t('auth.login') : t('auth.register')}
          </button>
        </form>

        <button className="btn-ghost" style={{ width: '100%', marginTop: '0.6rem' }} onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
          {mode === 'login' ? t('auth.noAccount') : t('auth.haveAccount')}
        </button>

        <div className="info-box" style={{ marginTop: '1rem' }}>
          {t('auth.demoHint')}
          <button className="btn-secondary" style={{ marginTop: '0.6rem' }} onClick={useDemo}>
            Use demo collector
          </button>
        </div>

        <div className="info-box">
          Recycler console: <strong>:12001/console</strong> · Ministry dashboard:{' '}
          <strong>:12001/dashboard</strong>
        </div>
      </main>
    </div>
  )
}
