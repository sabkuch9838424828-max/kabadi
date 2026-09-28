import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../lib/api'
import { db, getMeta, listLocalLots, putMeta, readRecyclers, saveLocalLot } from '../lib/db'
import { matchRecyclersOffline } from '../lib/matching'
import { CATEGORY_EMOJI, fmtInr, fmtKg } from '../lib/constants'
import { useOnline } from '../lib/hooks'
import { useSyncState } from '../state'
import { syncPendingLots } from '../lib/sync'
import LotStatusBadge from '../components/LotStatusBadge'
import RecoveryScore from '../components/RecoveryScore'
import MineralBreakdown from '../components/MineralBreakdown'

export default function LotDetailPage() {
  const { t } = useTranslation()
  const { lotId } = useParams()
  const nav = useNavigate()
  const online = useOnline()
  const { refreshPending } = useSyncState()

  const [lot, setLot] = useState(null)
  const [matches, setMatches] = useState([])
  const [matchesOffline, setMatchesOffline] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [handoverDone, setHandoverDone] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const local = (await listLocalLots()).find(
        (l) => l.client_uuid === lotId || l.lot_id === lotId
      )
      setLot(local || null)
      if (local && local.sync_state === 'synced' && local.lot_id) {
        try {
          const server = await api.listLots()
          const s = server.find((x) => x.lot_id === local.lot_id || x.client_uuid === local.client_uuid)
          if (s) setLot({ ...local, ...s })
        } catch {
          /* offline */
        }
      }
      await loadMatches(local)
    } finally {
      setLoading(false)
    }
  }

  const loadMatches = async (local) => {
    if (!local) return
    if (local.lot_id && online) {
      try {
        const rows = await api.lotMatches(local.lot_id)
        setMatches(rows)
        setMatchesOffline(false)
        return
      } catch {
        /* fall through to offline */
      }
    }
    // Offline path: cached directory + cached board + local ranking.
    let recyclers = await readRecyclers()
    let board = (await getMeta('price_board')) || []
    if (online && (!recyclers.length || !board.length)) {
      try {
        const [r, b] = await Promise.all([api.recyclers(), api.priceBoard()])
        recyclers = r
        board = b
        await putMeta('price_board', b)
        await db.transaction('rw', db.recyclers, async () => {
          for (const row of r) await db.recyclers.put(row)
        })
      } catch {
        /* keep cached */
      }
    }
    const ranked = matchRecyclersOffline({
      recyclers,
      board,
      category: local.material_category,
      weightKg: Number(local.declared_weight),
      lat: local.latitude,
      lon: local.longitude
    })
    setMatches(ranked)
    setMatchesOffline(true)
  }

  useEffect(() => {
    load().catch((err) => setError(err.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lotId])

  const chooseRecycler = async (match) => {
    if (!lot) return
    setBusy(true)
    setError(null)
    try {
      if (lot.lot_id && online && lot.sync_state === 'synced') {
        const updated = await api.matchLot(lot.lot_id, match.recycler_id)
        setLot({ ...lot, ...updated })
      } else {
        // Offline: store the chosen recycler on the local lot; sync applies it.
        const next = {
          ...lot,
          recycler_id: match.recycler_id,
          recycler_name: match.name,
          status: 'matched',
          quoted_price: match.offered_price
        }
        await saveLocalLot(next)
        setLot(next)
        await refreshPending()
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const recordHandover = async () => {
    if (!lot) return
    setBusy(true)
    setError(null)
    try {
      let coords = { latitude: lot.latitude, longitude: lot.longitude }
      if (navigator.geolocation) {
        coords = await new Promise((resolve) =>
          navigator.geolocation.getCurrentPosition(
            (p) => resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude }),
            () => resolve(coords),
            { timeout: 8000 }
          )
        )
      }
      const payload = {
        photo_ref: lot.image_ref || 'local://handover',
        latitude: coords.latitude,
        longitude: coords.longitude,
        notes: 'Handover recorded from collector PWA',
        captured_at: new Date().toISOString()
      }
      if (lot.lot_id && online && lot.sync_state === 'synced') {
        const updated = await api.createHandover(lot.lot_id, payload)
        setLot({ ...lot, ...updated })
      } else {
        const next = { ...lot, status: 'handover', handover: payload }
        await saveLocalLot(next)
        setLot(next)
        await refreshPending()
      }
      setHandoverDone(true)
      if (online) syncPendingLots().catch(() => {})
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const retrySync = async () => {
    setBusy(true)
    await syncPendingLots()
    await refreshPending()
    await load()
    setBusy(false)
  }

  if (loading) {
    return (
      <div className="page">
        <p className="muted">
          <span className="spinner" /> {t('common.loading')}
        </p>
      </div>
    )
  }

  if (!lot) {
    return (
      <div className="page">
        <div className="error-box">Lot not found on this device.</div>
        <Link className="btn-secondary" to="/" style={{ textDecoration: 'none' }}>
          {t('common.back')}
        </Link>
      </div>
    )
  }

  const minerals = lot.mineral_estimate?.minerals || null
  const isSynced = lot.sync_state === 'synced'
  const canMatch = lot.status === 'created' && matches.length > 0
  const canHandover = lot.status === 'matched'

  return (
    <div>
      <header className="app-header">
        <button className="btn-ghost" style={{ minHeight: 40, color: '#fff' }} onClick={() => nav(-1)}>
          ← {t('common.back')}
        </button>
        <LotStatusBadge status={lot.status} />
      </header>

      <main className="page">
        {!online && <div className="warn-box">📴 {t('offline.on')}</div>}
        {!isSynced && (
          <div className="warn-box">
            {t('offline.pending', { count: 1 })}
            {online && (
              <button className="btn-secondary" style={{ marginTop: '0.5rem' }} onClick={retrySync} disabled={busy}>
                {t('offline.syncNow')}
              </button>
            )}
          </div>
        )}
        {lot.sync_warning && <div className="warn-box">⚠️ {lot.sync_warning}</div>}
        {error && <div className="error-box">{error}</div>}

        <div className="card">
          <div className="row-between">
            <h2 style={{ margin: 0 }}>
              {CATEGORY_EMOJI[lot.material_category]} {t(`category.${lot.material_category}`)}
            </h2>
            <span className="badge status">{isSynced ? 'Synced' : 'Offline'}</span>
          </div>
          <div className="metric-row" style={{ marginTop: '0.7rem' }}>
            <div className="metric">
              <span className="value">{fmtKg(lot.declared_weight)}</span>
              <span className="label">{t('lot.declared')}</span>
            </div>
            <div className="metric">
              <span className="value">{lot.verified_weight ? fmtKg(lot.verified_weight) : '—'}</span>
              <span className="label">{t('lot.verified')}</span>
            </div>
            <div className="metric">
              <span className="value">₹{fmtInr(lot.final_price ?? lot.estimated_value)}</span>
              <span className="label">{lot.final_price ? t('lot.finalPrice') : t('lot.value')}</span>
            </div>
          </div>
          {lot.collection_district && (
            <p className="muted" style={{ marginTop: '0.5rem' }}>
              📍 {lot.collection_district}
              {lot.collection_latitude != null &&
                ` (${Number(lot.collection_latitude).toFixed(3)}, ${Number(lot.collection_longitude).toFixed(3)})`}
            </p>
          )}
        </div>

        {lot.recovery_score != null && (
          <div className="card">
            <RecoveryScore score={lot.recovery_score} />
          </div>
        )}

        {minerals && (
          <MineralBreakdown
            minerals={minerals}
            co2={lot.mineral_estimate?.co2_offset_kg}
            disclaimer={lot.mineral_estimate?.disclaimer}
          />
        )}

        {/* Recycler matching */}
        {lot.status === 'created' && (
          <div className="card">
            <h3>{t('lot.findRecycler')}</h3>
            {matchesOffline && <p className="disclaimer">Ranked on this device from cached data (offline).</p>}
            {matches.length === 0 && <p className="muted">{t('lot.noMatches')}</p>}
            {matches.map((m) => (
              <div key={m.recycler_id} className="list-row" style={{ alignItems: 'flex-start' }}>
                <span style={{ flex: 1 }}>
                  <strong>{m.name}</strong>
                  <span
                    className={`badge ${m.authorization_status === 'authorized' ? 'authorized' : 'pending'}`}
                    style={{ marginLeft: 6 }}
                  >
                    {m.authorization_status}
                  </span>
                  <span className="meta" style={{ display: 'block', marginTop: 4 }}>
                    {m.distance_km != null && `${t('lot.distance', { km: m.distance_km.toFixed(1) })} · `}
                    {m.offered_price ? t('lot.offers', { price: fmtInr(m.offered_price) }) : ''}
                  </span>
                  <span className="muted" style={{ display: 'block', fontSize: '0.74rem' }}>
                    {t('lot.whyRanked')}: {(m.rank_reasons || []).join(' · ')}
                  </span>
                </span>
                <button className="btn-primary" style={{ width: 'auto', padding: '0 0.8rem' }} onClick={() => chooseRecycler(m)} disabled={busy}>
                  ✓
                </button>
              </div>
            ))}
          </div>
        )}

        {lot.recycler_name && (
          <div className="card">
            <p style={{ margin: 0 }}>
              ✅ {t('lot.matched', { name: lot.recycler_name })}
            </p>
          </div>
        )}

        {canHandover && !handoverDone && (
          <div className="card">
            <h3>{t('lot.handover')}</h3>
            <p className="muted">{t('lot.handoverPhoto')} + GPS + timestamp</p>
            <button className="btn-secondary" onClick={recordHandover} disabled={busy}>
              {busy ? <span className="spinner" /> : `📸 ${t('lot.handover')}`}
            </button>
          </div>
        )}

        {(handoverDone || lot.handover) && (
          <div className="card flat">
            <h3>{t('lot.handoverDone')}</h3>
            {lot.handover?.reference_number && (
              <p style={{ margin: 0 }}>
                <strong>{t('lot.reference')}:</strong> {lot.handover.reference_number}
              </p>
            )}
            {lot.handover?.gps_latitude != null && (
              <p className="muted" style={{ margin: '0.3rem 0 0' }}>
                GPS: {Number(lot.handover.gps_latitude).toFixed(4)},{' '}
                {Number(lot.handover.gps_longitude).toFixed(4)} ·{' '}
                {new Date(lot.handover.captured_at).toLocaleString()}
              </p>
            )}
            <p className="muted" style={{ margin: '0.3rem 0 0' }}>
              Recycler confirmation: {lot.handover?.recycler_confirmation ? 'Confirmed' : 'Pending'}
            </p>
          </div>
        )}

        <p className="disclaimer">{t('lot.estimateNote')}</p>
      </main>
    </div>
  )
}
