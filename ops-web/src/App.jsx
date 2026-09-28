import { useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { api, clearSession, login, session, setSession } from './lib/api'

import LoginPage from './pages/LoginPage'
import RecyclerLots from './pages/RecyclerLots'
import RecyclerRates from './pages/RecyclerRates'
import RecyclerHistory from './pages/RecyclerHistory'
import AdminOverview from './pages/AdminOverview'
import AdminRecyclers from './pages/AdminRecyclers'
import AdminPrices from './pages/AdminPrices'
import AdminAudit from './pages/AdminAudit'
import RecyclerProfile from './pages/RecyclerProfile'

function TopBar({ user, onLogout, role }) {
  const nav = useNavigate()
  const loc = useLocation()
  const links = role === 'recycler'
    ? [
        { to: '/console', label: 'Incoming lots' },
        { to: '/console/history', label: 'History' },
        { to: '/console/rates', label: 'My rates' },
        { to: '/console/profile', label: 'Profile' }
      ]
    : [
        { to: '/dashboard', label: 'Overview' },
        { to: '/dashboard/recyclers', label: 'Recycler authorization' },
        { to: '/dashboard/prices', label: 'MSP & prices' },
        { to: '/dashboard/audit', label: 'Audit & fraud' }
      ]
  return (
    <header className="topbar">
      <div className="brand">
        ♻️ Kabadiwala Connect
        <small>{role === 'recycler' ? 'Recycler Console' : 'Ministry / Admin Dashboard'}</small>
      </div>
      <nav>
        {links.map((l) => (
          <a
            key={l.to}
            href={l.to}
            className={loc.pathname === l.to ? 'active' : ''}
            onClick={(e) => {
              e.preventDefault()
              nav(l.to)
            }}
          >
            {l.label}
          </a>
        ))}
      </nav>
      <div className="row" style={{ gap: '0.6rem' }}>
        <span style={{ fontSize: '0.82rem', opacity: 0.85 }}>{user?.full_name || user?.name}</span>
        <button className="btn-secondary btn-sm" onClick={onLogout}>
          Logout
        </button>
      </div>
    </header>
  )
}

export default function App() {
  const [user, setUser] = useState(session())
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(false)

  const onLogin = async (email, password) => {
    const result = await login(email, password)
    if (!['recycler', 'admin'].includes(result.role)) {
      throw new Error('This console is for recyclers and ministry admins.')
    }
    setSession(result)
    setUser(session())
  }

  const logout = () => {
    clearSession()
    setUser(null)
    setProfile(null)
  }

  useEffect(() => {
    if (!user) return
    setLoading(true)
    api
      .me()
      .then((me) => setProfile(me))
      .catch(() => logout())
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.token])

  if (!user) {
    return (
      <Routes>
        <Route path="/console/*" element={<RedirectLogin onLogin={onLogin} intent="recycler" />} />
        <Route path="/dashboard/*" element={<RedirectLogin onLogin={onLogin} intent="admin" />} />
        <Route path="*" element={<LoginPage onLogin={onLogin} />} />
      </Routes>
    )
  }

  const role = user.role

  return (
    <>
      <TopBar user={{ ...user, full_name: profile?.user?.full_name }} onLogout={logout} role={role} />
      <div className="layout">
        {role === 'recycler' ? (
          <Routes>
            <Route path="/console" element={<RecyclerLots profile={profile} />} />
            <Route path="/console/history" element={<RecyclerHistory />} />
            <Route path="/console/rates" element={<RecyclerRates />} />
            <Route path="/console/profile" element={<RecyclerProfile profile={profile} />} />
            <Route path="*" element={<Navigate to="/console" replace />} />
          </Routes>
        ) : (
          <Routes>
            <Route path="/dashboard" element={<AdminOverview />} />
            <Route path="/dashboard/recyclers" element={<AdminRecyclers />} />
            <Route path="/dashboard/prices" element={<AdminPrices />} />
            <Route path="/dashboard/audit" element={<AdminAudit />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        )}
      </div>
    </>
  )
}

function RedirectLogin({ onLogin, intent }) {
  return <LoginPage onLogin={onLogin} intent={intent} />
}
