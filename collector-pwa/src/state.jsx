import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { api, clearSession, currentUser, setSession } from './lib/api'
import { getMeta, putMeta } from './lib/db'
import { setLanguage } from './i18n'

const SessionContext = createContext(null)
const SyncContext = createContext(null)

export function SessionProvider({ children }) {
  const [session, setSessionState] = useState(currentUser())
  const [profile, setProfile] = useState(null)

  const login = async (email, password) => {
    const result = await api.login(email, password)
    if (result.role !== 'collector') {
      clearSession()
      throw new Error('This app is for collectors. Please use the recycler console or ministry dashboard.')
    }
    setSession(result)
    setSessionState(currentUser())
    return result
  }

  const register = async (payload) => {
    const result = await api.register({ ...payload, role: 'collector' })
    setSession(result)
    setSessionState(currentUser())
    return result
  }

  const logout = () => {
    clearSession()
    setSessionState(null)
    setProfile(null)
  }

  const refreshProfile = async () => {
    if (!currentUser()) return null
    const me = await api.me()
    setProfile(me)
    if (me.collector?.preferred_language) {
      setLanguage(me.collector.preferred_language)
    }
    return me
  }

  useEffect(() => {
    if (session) refreshProfile().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session])

  const value = useMemo(
    () => ({ session, profile, login, register, logout, refreshProfile, setProfile }),
    [session, profile]
  )
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession() {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used inside SessionProvider')
  return ctx
}

/** Sync state shared across screens: pending count + live sync events. */
export function SyncProvider({ children }) {
  const [pending, setPending] = useState(0)
  const [syncing, setSyncing] = useState(false)
  const [lastResult, setLastResult] = useState(null)

  const refreshPending = async () => {
    const { db } = await import('./lib/db')
    const count = await db.lots.where('sync_state').equals('pending').count()
    setPending(count)
    await putMeta('pending_count', count)
    return count
  }

  const value = useMemo(
    () => ({ pending, syncing, lastResult, setPending, setSyncing, setLastResult, refreshPending }),
    [pending, syncing, lastResult]
  )
  return <SyncContext.Provider value={value}>{children}</SyncContext.Provider>
}

export function useSyncState() {
  const ctx = useContext(SyncContext)
  if (!ctx) throw new Error('useSyncState must be used inside SyncProvider')
  return ctx
}

export { getMeta, putMeta }
