import { useEffect, useState } from 'react'

export function useOnline() {
  const [online, setOnline] = useState(navigator.onLine)
  useEffect(() => {
    const up = () => setOnline(true)
    const down = () => setOnline(false)
    window.addEventListener('online', up)
    window.addEventListener('offline', down)
    return () => {
      window.removeEventListener('online', up)
      window.removeEventListener('offline', down)
    }
  }, [])
  return online
}

/** Simple async data hook with loading/error state and manual refresh. */
export function useAsync(fn, deps = [], { immediate = true } = {}) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(immediate)

  const run = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fn()
      setData(result)
      return result
    } catch (err) {
      setError(err)
      throw err
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (immediate) {
      run().catch(() => {})
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { data, error, loading, refresh: run, setData }
}
