import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../lib/api'
import { listLocalLots } from '../lib/db'
import { CATEGORY_EMOJI, fmtInr, fmtKg } from '../lib/constants'
import { useSession, useSyncState } from '../state'
import LotStatusBadge from '../components/LotStatusBadge'

export default function HomePage() {
  const { t } = useTranslation()
  const { session, profile } = useSession()
  const { pending } = useSyncState()
  const [lots, setLots] = useState([])
  const [ledger, setLedger] = useState(null)

  const load = async () => {
    const local = await listLocalLots()
    setLots(local)
    try {
      const l = await api.ledger()
      setLedger(l)
      const server = await api.listLots()
      const byUuid = new Map(server.map((s) => [s.client_uuid, s]))
      // Server state wins for settled lots; local-only lots stay visible.
      const merged = local.map((row) => {
        const s = byUuid.get(row.client_uuid)
        return s ? { ...row, ...s, sync_state: row.sync_state } : row
      })
      setLots(merged)
    } catch {
      /* offline: local data only */
    }
  }

  useEffect(() => {
    load().catch(() => {})
    const id = setInterval(() => load().catch(() => {}), 15000)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending])

  const name = profile?.collector?.display_name || session?.name || t('auth.role.collector')

  return (
    <div>
      <header className="app-header">
        <div>
          <h1>{t('home.greeting', { name })}</h1>
          <div className="sub">
            {profile?.collector?.district ? `${profile.collector.district}` : t('app.name')}
          </div>
        </div>
        <span style={{ fontSize: '1.6rem' }} aria-hidden="true">
          ♻️
        </span>
      </header>

      <main className="page">
        {pending > 0 && <div className="warn-box">⏳ {t('home.syncBanner', { count: pending })}</div>}

        <div className="metric-row" style={{ marginBottom: '0.9rem' }}>
          <div className="metric">
            <span className="value">₹{fmtInr(ledger?.total_earned ?? 0)}</span>
            <span className="label">{t('home.totalEarned')}</span>
          </div>
          <div className="metric">
            <span className="value">₹{fmtInr(ledger?.pending_dues ?? 0)}</span>
            <span className="label">{t('home.pendingDues')}</span>
          </div>
          <div className="metric">
            <span className="value">{fmtKg(ledger?.lifetime_kg ?? 0)}</span>
            <span className="label">{t('home.lifetimeKg')}</span>
          </div>
        </div>

        <Link to="/add" className="btn-primary" style={{ textDecoration: 'none', marginBottom: '1rem' }}>
          ➕ {t('home.addLot')}
        </Link>

        <h2>{t('home.myLots')}</h2>
        {lots.length === 0 && <p className="muted">{t('home.noLots')}</p>}

        {lots.map((lot) => {
          const estimate = lot.mineral_estimate
          const score = lot.recovery_score
          return (
            <Link key={lot.client_uuid || lot.lot_id} to={`/lots/${lot.client_uuid || lot.lot_id}`} className="list-row">
              <span className="emoji" aria-hidden="true">
                {CATEGORY_EMOJI[lot.material_category] || '📦'}
              </span>
              <span style={{ flex: 1 }}>
                <strong>{t(`category.${lot.material_category}`)}</strong>
                <span className="meta" style={{ display: 'block' }}>
                  {fmtKg(lot.declared_weight)} {t('common.kg')} · ₹{fmtInr(lot.final_price ?? lot.estimated_value)}
                  {score != null && ` · ${t('lot.recoveryScore')} ${Math.round(score)}`}
                </span>
              </span>
              <span style={{ textAlign: 'right' }}>
                <LotStatusBadge status={lot.status} />
                {lot.sync_state === 'pending' && (
                  <span className="badge offline" style={{ display: 'block', marginTop: 4 }}>
                    {t('offline.pending', { count: 1 })}
                  </span>
                )}
              </span>
            </Link>
          )
        })}
      </main>
    </div>
  )
}
