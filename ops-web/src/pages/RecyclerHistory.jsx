import { useEffect, useState } from 'react'
import { api } from '../lib/api'

function fmt(n, d = 2) {
  return Number(n ?? 0).toLocaleString('en-IN', { maximumFractionDigits: d })
}

export default function RecyclerHistory() {
  const [lots, setLots] = useState([])
  const [handovers, setHandovers] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.recyclerHistory(), api.handovers()])
      .then(([h, ho]) => {
        setLots(h)
        setHandovers(ho)
      })
      .catch((e) => setError(e.message))
  }, [])

  const totalKg = lots.reduce((s, l) => s + Number(l.verified_weight || 0), 0)
  const totalValue = lots.reduce((s, l) => s + Number(l.final_price || 0), 0)
  const co2 = lots.reduce((s, l) => s + Number(l.mineral_estimate?.co2_offset_kg || 0), 0)

  return (
    <div className="grid">
      {error && <div className="error">{error}</div>}
      <div className="grid cols-4">
        <div className="card kpi">
          <span className="value">{lots.length}</span>
          <span className="label">Settled lots</span>
        </div>
        <div className="card kpi">
          <span className="value">{fmt(totalKg, 2)}</span>
          <span className="label">Verified kg processed</span>
        </div>
        <div className="card kpi">
          <span className="value">₹{fmt(totalValue)}</span>
          <span className="label">Value paid</span>
        </div>
        <div className="card kpi">
          <span className="value">{fmt(co2, 1)}</span>
          <span className="label">kg CO₂e offset (est.)</span>
        </div>
      </div>

      <div className="card">
        <h2>Processed lots</h2>
        <div style={{ overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th>Category</th>
                <th>Declared kg</th>
                <th>Verified kg</th>
                <th>Final ₹</th>
                <th>Payment</th>
                <th>Status</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {lots.map((l) => (
                <tr key={l.lot_id}>
                  <td>{l.material_category}</td>
                  <td>{fmt(l.declared_weight, 3)}</td>
                  <td>{fmt(l.verified_weight, 3)}</td>
                  <td>{fmt(l.final_price)}</td>
                  <td>{l.transaction?.payment_status || '—'}</td>
                  <td>
                    <span className={`badge ${l.status}`}>{l.status}</span>
                  </td>
                  <td className="muted">{new Date(l.updated_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {lots.length === 0 && <p className="muted">Nothing processed yet.</p>}
      </div>

      <div className="card">
        <h2>Digital receipts (handovers)</h2>
        <p className="muted">GPS + timestamp + photo reference for every handover — EPR audit trail.</p>
        <div style={{ overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th>Reference</th>
                <th>Photo</th>
                <th>GPS</th>
                <th>Captured</th>
                <th>Confirmed</th>
              </tr>
            </thead>
            <tbody>
              {handovers.map((h) => (
                <tr key={h.handover_id}>
                  <td>{h.reference_number}</td>
                  <td className="muted">{h.photo_ref || '—'}</td>
                  <td className="muted">
                    {h.gps_latitude != null
                      ? `${Number(h.gps_latitude).toFixed(4)}, ${Number(h.gps_longitude).toFixed(4)}`
                      : '—'}
                  </td>
                  <td className="muted">{new Date(h.captured_at).toLocaleString()}</td>
                  <td>
                    <span className={`badge ${h.recycler_confirmation ? 'verified' : 'pending'}`}>
                      {h.recycler_confirmation ? 'confirmed' : 'pending'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {handovers.length === 0 && <p className="muted">No handovers recorded.</p>}
      </div>
    </div>
  )
}
