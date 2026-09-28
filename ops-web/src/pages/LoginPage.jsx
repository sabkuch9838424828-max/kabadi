import { useState } from 'react'

const DEMOS = {
  recycler: { email: 'greenloop@recycler.in', password: 'Recycler@123' },
  admin: { email: 'admin@kabadiwala.gov.in', password: 'Admin@12345' }
}

export default function LoginPage({ onLogin, intent }) {
  const [mode, setMode] = useState(intent || 'recycler')
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await onLogin(form.email.trim(), form.password)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <h2 style={{ fontSize: '1.3rem' }}>♻️ Kabadiwala Connect — Ops</h2>
        <p className="muted">
          Recycler Console and Ministry Dashboard. Collector PWA runs separately on port 12000.
        </p>

        <div className="row" style={{ marginBottom: '0.9rem' }}>
          <button
            className={mode === 'recycler' ? 'btn-primary' : 'btn-secondary'}
            onClick={() => setMode('recycler')}
          >
            Recycler
          </button>
          <button
            className={mode === 'admin' ? 'btn-primary' : 'btn-secondary'}
            onClick={() => setMode('admin')}
          >
            Ministry / Admin
          </button>
        </div>

        {error && <div className="error">{error}</div>}

        <form onSubmit={submit}>
          <div className="field">
            <label>Email</label>
            <input
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Password</label>
            <input
              type="password"
              required
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </div>
          <button className="btn-primary" type="submit" disabled={busy} style={{ width: '100%' }}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <button
          className="btn-ghost btn-sm"
          style={{ marginTop: '0.7rem' }}
          onClick={() => setForm(DEMOS[mode])}
        >
          Use demo {mode} account
        </button>
      </div>
    </div>
  )
}
