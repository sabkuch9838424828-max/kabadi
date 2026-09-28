import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { SessionProvider, SyncProvider, useSession, useSyncState } from './state'
import { useOnline } from './lib/hooks'
import { getMeta } from './lib/db'
import { installSyncTriggers, onSyncEvent, syncPendingLots } from './lib/sync'

import BottomNav from './components/BottomNav'
import OfflineBanner from './components/OfflineBanner'

import LoginPage from './pages/LoginPage'
import OnboardingPage from './pages/OnboardingPage'
import HomePage from './pages/HomePage'
import AddLotPage from './pages/AddLotPage'
import LotDetailPage from './pages/LotDetailPage'
import PriceBoardPage from './pages/PriceBoardPage'
import EarningsPage from './pages/EarningsPage'
import SafetyPage from './pages/SafetyPage'
import ProfilePage from './pages/ProfilePage'

function Shell() {
  const { session, profile, logout } = useSession()
  const { setPending, setSyncing, setLastResult, refreshPending } = useSyncState()
  const online = useOnline()
  const location = useLocation()

  useEffect(() => {
    installSyncTriggers()
    refreshPending().catch(() => {})
    const off = onSyncEvent((event) => {
      if (event.type === 'start') setSyncing(true)
      if (event.type === 'done') {
        setSyncing(false)
        setLastResult({ synced: event.synced, failed: event.failed })
        refreshPending().catch(() => {})
      }
      if (event.type === 'error') {
        setSyncing(false)
        setLastResult({ error: event.message })
      }
    })
    return off
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (online && session) {
      syncPendingLots().catch(() => {})
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [online, session])

  const needsOnboarding =
    session && profile && !profile.collector?.district && location.pathname !== '/onboarding'

  if (!session) {
    return (
      <Routes>
        <Route path="*" element={<LoginPage />} />
      </Routes>
    )
  }

  return (
    <div className="app-shell">
      <OfflineBanner />
      {needsOnboarding ? (
        <Navigate to="/onboarding" replace />
      ) : (
        <Routes>
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/" element={<HomePage />} />
          <Route path="/add" element={<AddLotPage />} />
          <Route path="/lots/:lotId" element={<LotDetailPage />} />
          <Route path="/prices" element={<PriceBoardPage />} />
          <Route path="/earnings" element={<EarningsPage />} />
          <Route path="/safety" element={<SafetyPage />} />
          <Route path="/profile" element={<ProfilePage onLogout={logout} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      )}
      <BottomNav />
    </div>
  )
}

export default function App() {
  return (
    <SessionProvider>
      <SyncProvider>
        <Shell />
      </SyncProvider>
    </SessionProvider>
  )
}
