import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../lib/api'
import { getMeta, putMeta } from '../lib/db'
import { boardPriceFor, resolveUnitPrice } from '../lib/board'
import { CATEGORY_EMOJI, CATEGORY_ORDER, fmtInr } from '../lib/constants'
import { boardToSpeech, speak, speechSupported, stopSpeaking } from '../lib/speech'
import { useOnline } from '../lib/hooks'
import { useSession } from '../state'

export default function PriceBoardPage() {
  const { t, i18n } = useTranslation()
  const online = useOnline()
  const { profile } = useSession()
  const district = profile?.collector?.district || null
  const [board, setBoard] = useState([])
  const [stale, setStale] = useState(false)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const rows = await api.priceBoard(district || undefined)
      const merged = mergeWithHistory(await getMeta('price_board'), rows)
      setBoard(merged)
      setStale(false)
      await putMeta('price_board', merged)
      await putMeta('price_board_at', new Date().toISOString())
    } catch {
      const cached = (await getMeta('price_board')) || []
      setBoard(cached)
      setStale(cached.length > 0)
    } finally {
      setLoading(false)
    }
  }

  const mergeWithHistory = (previous, current) => {
    // Keep entries the server did not return (e.g. showing stale local prices).
    const prev = new Map((previous || []).map((r) => [`${r.material_category}|${r.location}`, r]))
    return current.map((row) => {
      const old = prev.get(`${row.material_category}|${row.location}`)
      return old ? { ...old, ...row } : row
    })
  }

  useEffect(() => {
    load().catch(() => {})
    return () => stopSpeaking()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const rows = CATEGORY_ORDER.map((cat) => {
    const row = boardPriceFor(board, cat, district)
    return { category: cat, row }
  }).filter((r) => r.row)

  const speakAll = () => {
    const text = boardToSpeech(
      board.map((r) => ({ ...r, best_price: resolveUnitPrice(r), material_category: r.material_category })),
      t
    )
    speak(text, i18n.language)
  }

  return (
    <div>
      <header className="app-header">
        <div>
          <h1>{t('prices.title')}</h1>
          <div className="sub">{district || 'India'}</div>
        </div>
        {speechSupported() && (
          <button
            className="btn-ghost"
            style={{ color: '#fff', minHeight: 40 }}
            onClick={speakAll}
            aria-label={t('prices.speak')}
          >
            🔊
          </button>
        )}
      </header>

      <main className="page">
        {stale && <div className="warn-box">📴 {t('prices.offline')}</div>}
        <p className="muted">{t('prices.subtitle')}</p>
        {loading && !board.length && (
          <p className="muted">
            <span className="spinner" /> {t('common.loading')}
          </p>
        )}

        {rows.map(({ category, row }) => {
          const best = resolveUnitPrice(row)
          const trend = row.trend || 'flat'
          const arrow = trend === 'up' ? '▲' : trend === 'down' ? '▼' : '▬'
          return (
            <div key={category} className="card">
              <div className="row-between">
                <strong>
                  {CATEGORY_EMOJI[category]} {t(`category.${category}`)}
                </strong>
                <span className={`trend-${trend}`} title={t(`prices.trend.${trend}`)}>
                  {arrow} {t(`prices.trend.${trend}`)}
                </span>
              </div>
              <div className="row-between" style={{ marginTop: '0.4rem' }}>
                <span style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--teal-700)' }}>
                  ₹{fmtInr(best)} <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>/ {t('common.kg')}</span>
                </span>
                {speechSupported() && (
                  <button
                    className="btn-ghost"
                    onClick={() => {
                      speak(
                        `${t(`category.${category}`)}: ${Math.round(best)} rupaye per kilo`,
                        i18n.language
                      )
                    }}
                    aria-label={`${t('prices.speak')} ${t(`category.${category}`)}`}
                  >
                    🔊 {t('prices.speak')}
                  </button>
                )}
              </div>
              <div className="row-between muted">
                <span>{t('prices.best')}</span>
                {row.benchmark_price && (
                  <span>
                    {t('prices.benchmark')}: ₹{fmtInr(row.benchmark_price)}
                  </span>
                )}
              </div>
            </div>
          )
        })}

        {!loading && rows.length === 0 && (
          <div className="info-box">No rates available yet. Connect to the internet once to cache them.</div>
        )}
        <p className="disclaimer">{t('prices.estimateNote')}</p>
      </main>
    </div>
  )
}
