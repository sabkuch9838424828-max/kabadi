import { useEffect, useState } from 'react'
import { api } from '../lib/api'

function fmt(n, d = 2) {
  return Number(n ?? 0).toLocaleString('en-IN', { maximumFractionDigits: d })
}

export default function RecyclerLots({ profile }) {
  const [lots, setLots] = useState([])
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [verify, setVerify] = useState({}) // lotId -> { weight, mode }
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      setLots(await api.incomingLots())
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (profile?.recycler) load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile])

  if (profile && !profile.recycler) {
    return (
      <div className="card">
        <div className="warn">
          Your recycler profile is not set up yet. Open <strong>Profile</strong> to register your
          facility and materials accepted.
        </div>
      </div>
    )
  }

  const onVerify = async (lot) => {
    const input = verify[lot.lot_id] || {}
    if (!input.weight || Number(input.weight) <= 0) {
      setError('Enter the physically verified weight.')
      return
    }
    setBusyId(lot.lot_id)
    setError(null)
    try {
      const updated = await api.verifyLot(lot.lot_id, {
        verified_weight: Number(input.weight),
        payment_mode: input.mode || 'cash'
      })
      setNotice(
        `Verified ${fmt(updated.verified_weight, 3)} kg (declared ${fmt(updated.declared_weight, 3)} kg). ` +
          `Final price ₹${fmt(updated.final_price)}.` +
          (updated.weight_anomaly?.is_anomaly
            ? ` ⚠ Weight anomaly flagged (${updated.weight_anomaly.severity}).`
            : '')
      )
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  const onPay = async (lot, mode) => {
    setBusyId(lot.lot_id)
    setError(null)
    try {
      await api.payLot(lot.lot_id, mode)
      setNotice('Payment marked as received. Collector ledger updated.')
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  const onDecline = async (lot) => {
    const reason = prompt('Reason for declining this lot (min 3 characters):')
    if (!reason || reason.length < 3) return
    setBusyId(lot.lot_id)
    try {
      await api.declineLot(lot.lot_id, reason)
      setNotice('Lot declined. Reason recorded against the handover.')
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  const awaiting = lots.filter((l) => ['handover', 'matched'].includes(l.status))
  const verified = lots.filter((l) => l.status === 'verified')

  return (
    <div className="grid">
      {error && <div className="error">{error}</div>}
      {notice && <div className="notice">{notice}</div>}

      <div className="grid cols-3">
        <div className="card kpi">
          <span className="value">{lots.length}</span>
          <span className="label">Assigned lots</span>
        </div>
        <div className="card kpi">
          <span className="value">{awaiting.length}</span>
          <span className="label">Awaiting verification</span>
        </div>
        <div className="card kpi">
          <span className="value">₹{fmt(verified.reduce((s, l) => s + Number(l.final_price || 0), 0))}</span>
          <span className="label">Verified value pending payment</span>
        </div>
      </div>

      <div className="card">
        <div className="row">
          <h2 style={{ margin: 0 }}>Incoming lots</h2>
          <span className="spacer" />
          <button className="btn-secondary btn-sm" onClick={load}>
            Refresh
          </button>
        </div>
        {loading && <p className="muted">Loading…</p>}
        {!loading && lots.length === 0 && (
          <p className="muted">
            No lots assigned yet. Collectors see your facility in matching once you are authorized.
          </p>
        )}

        {lots.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Declared kg</th>
                  <th>Verified kg</th>
                  <th>Price ₹/kg</th>
                  <th>Final ₹</th>
                  <th>Status</th>
                  <th>Handover</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {lots.map((lot) => (
                  <tr key={lot.lot_id}>
                    <td>
                      <strong>{lot.material_category}</strong>
                      <div className="muted">{lot.collection_district || '—'}</div>
                    </td>
                    <td>{fmt(lot.declared_weight, 3)}</td>
                    <td>{lot.verified_weight ? fmt(lot.verified_weight, 3) : '—'}</td>
                    <td>{fmt(lot.quoted_price || lot.estimated_value)}</td>
                    <td>{lot.final_price ? fmt(lot.final_price) : '—'}</td>
                    <td>
                      <span className={`badge ${lot.status}`}>{lot.status}</span>
                    </td>
                    <td className="muted">
                      {lot.handover ? (
                        <>
                          {lot.handover.reference_number}
                          <div>{lot.handover.recycler_confirmation ? 'confirmed' : 'unconfirmed'}</div>
                        </>
                      ) : (
                        'not recorded'
                      )}
                    </td>
                    <td>
                      {['matched', 'handover'].includes(lot.status) && lot.handover && (
                        <div className="row">
                          <input
                            type="number"
                            step="0.01"
                            placeholder="kg"
                            style={{ width: 80, padding: '0.3rem' }}
                            value={verify[lot.lot_id]?.weight || ''}
                            onChange={(e) =>
                              setVerify({
                                ...verify,
                                [lot.lot_id]: { ...verify[lot.lot_id], weight: e.target.value }
                              })
                            }
                          />
                          <select
                            style={{ padding: '0.3rem' }}
                            value={verify[lot.lot_id]?.mode || 'cash'}
                            onChange={(e) =>
                              setVerify({
                                ...verify,
                                [lot.lot_id]: { ...verify[lot.lot_id], mode: e.target.value }
                              })
                            }
                          >
                            <option value="cash">Cash</option>
                            <option value="upi">UPI</option>
                          </select>
                          <button
                            className="btn-primary btn-sm"
                            disabled={busyId === lot.lot_id}
                            onClick={() => onVerify(lot)}
                          >
                            Verify
                          </button>
                          <button className="btn-danger btn-sm" onClick={() => onDecline(lot)}>
                            Decline
                          </button>
                        </div>
                      )}
                      {lot.status === 'verified' && (
                        <div className="row">
                          <button
                            className="btn-primary btn-sm"
                            disabled={busyId === lot.lot_id}
                            onClick={() => onPay(lot, lot.transaction?.payment_mode || 'cash')}
                          >
                            Mark {lot.transaction?.payment_mode === 'upi' ? 'UPI' : 'cash'} paid
                          </button>
                        </div>
                      )}
                      {lot.status === 'paid' && <span className="muted">settled</span>}
                      {['matched', 'handover'].includes(lot.status) && !lot.handover && (
                        <span className="muted">waiting for collector handover</span>
                      )}
                      <button className="btn-ghost btn-sm" onClick={() => setSelected(lot)}>
                        Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selected && (
        <div className="card">
          <div className="row">
            <h3 style={{ margin: 0 }}>Lot {selected.lot_id.slice(0, 8)}… details</h3>
            <span className="spacer" />
            <button className="btn-ghost btn-sm" onClick={() => setSelected(null)}>
              Close
            </button>
          </div>
          <div className="grid cols-2">
            <div>
              <p className="muted">Composition-based estimate (not a lab assay)</p>
              {selected.mineral_estimate?.minerals &&
                Object.entries(selected.mineral_estimate.minerals).map(([el, m]) => (
                  <div key={el} className="row" style={{ justifyContent: 'space-between' }}>
                    <span>
                      <strong>{el}</strong>{' '}
                      {m.is_critical && <span className="badge pending">critical</span>}
                    </span>
                    <span className="muted">
                      {fmt(m.kg_low, 3)}–{fmt(m.kg_high, 3)} kg
                    </span>
                  </div>
                ))}
              <p className="disclaimer">{selected.mineral_estimate?.disclaimer}</p>
            </div>
            <div>
              <p>
                <strong>Recovery Score:</strong> {fmt(selected.recovery_score, 1)} / 100
              </p>
              <p>
                <strong>CO₂ offset (est.):</strong> {fmt(selected.mineral_estimate?.co2_offset_kg, 2)} kg
              </p>
              <p>
                <strong>Handover:</strong>{' '}
                {selected.handover
                  ? `${selected.handover.reference_number} at ${new Date(
                      selected.handover.captured_at
                    ).toLocaleString()}`
                  : '—'}
              </p>
              <p>
                <strong>Transaction:</strong>{' '}
                {selected.transaction
                  ? `₹${fmt(selected.transaction.amount)} · ${selected.transaction.payment_status}`
                  : '—'}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
