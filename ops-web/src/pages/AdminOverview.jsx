import { useEffect, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet'
import { api } from '../lib/api'

function fmt(n, d = 2) {
  return Number(n ?? 0).toLocaleString('en-IN', { maximumFractionDigits: d })
}

export default function AdminOverview() {
  const [a, setA] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .analytics()
      .then(setA)
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="error">{error}</div>
  if (!a) return <p className="muted">Loading analytics…</p>

  const maxDistrict = Math.max(1, ...(a.district_heatmap || []).map((d) => d.verified_kg))
  const maxCat = Math.max(1, ...(a.category_breakdown || []).map((c) => c.verified_kg))
  const dv = a.declared_vs_verified || {}

  // Approximate centroids for the seeded districts so the map is meaningful.
  const COORDS = {
    Pune: [18.5204, 73.8567],
    Mumbai: [19.076, 72.8777],
    Nagpur: [21.1458, 79.0882],
    Nashik: [19.9975, 73.7898],
    Thane: [19.2183, 72.9781],
    Aurangabad: [19.8762, 75.3433]
  }
  const points = (a.district_heatmap || []).filter((d) => COORDS[d.district])

  return (
    <div className="grid">
      <div className="grid cols-4">
        <div className="card kpi">
          <span className="value">{fmt(a.total_lots, 0)}</span>
          <span className="label">Total lots</span>
        </div>
        <div className="card kpi">
          <span className="value">{fmt(a.material_collected_kg, 1)}</span>
          <span className="label">Verified kg collected</span>
        </div>
        <div className="card kpi">
          <span className="value">{fmt(a.active_collectors, 0)}</span>
          <span className="label">Active collectors</span>
        </div>
        <div className="card kpi">
          <span className="value">{fmt(a.authorized_recyclers, 0)}</span>
          <span className="label">Authorized recyclers</span>
        </div>
        <div className="card kpi">
          <span className="value">{fmt(a.co2_offset_kg, 1)}</span>
          <span className="label">kg CO₂e offset (est.)</span>
        </div>
        <div className="card kpi">
          <span className="value">{fmt(a.recovery_score_avg, 1)}</span>
          <span className="label">Avg Recovery Score</span>
        </div>
        <div className="card kpi">
          <span className="value">{fmt(a.price_anomalies, 0)}</span>
          <span className="label">Fraud / anomaly flags</span>
        </div>
        <div className="card kpi">
          <span className="value">
            {a.active_recyclers}/{a.authorized_recyclers}
          </span>
          <span className="label">Engaged / authorized recyclers</span>
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h2>Declared vs verified weight (trust layer)</h2>
          <div className="grid cols-3">
            <div className="kpi">
              <span className="value">{fmt(dv.declared_kg, 1)}</span>
              <span className="label">Declared kg</span>
            </div>
            <div className="kpi">
              <span className="value">{fmt(dv.verified_kg, 1)}</span>
              <span className="label">Verified kg</span>
            </div>
            <div className="kpi">
              <span className="value">
                {dv.difference_pct != null ? `${dv.difference_pct > 0 ? '+' : ''}${dv.difference_pct}%` : '—'}
              </span>
              <span className="label">Difference</span>
            </div>
          </div>
          <p className="muted" style={{ marginTop: '0.6rem' }}>
            {fmt(dv.verified_lots, 0)} lots independently verified by an authorized recycler. Payment
            is settled on the verified weight, not the collector's declaration.
          </p>
        </div>

        <div className="card">
          <h2>Critical minerals recovered (estimated)</h2>
          {(a.critical_minerals_recovered || []).length === 0 && (
            <p className="muted">No verified lots yet.</p>
          )}
          {(a.critical_minerals_recovered || []).map((m) => (
            <div key={m.element} style={{ marginBottom: '0.5rem' }}>
              <div className="row">
                <strong>{m.element}</strong>
                <span className="spacer" />
                <span className="muted">
                  {fmt(m.kg, 3)} kg · ₹{fmt(m.estimated_value_inr)}
                </span>
              </div>
            </div>
          ))}
          <p className="disclaimer">{a.is_estimate_disclaimer}</p>
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h2>District collection heatmap</h2>
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>District</th>
                  <th>Lots</th>
                  <th>Verified kg</th>
                  <th>Share</th>
                </tr>
              </thead>
              <tbody>
                {(a.district_heatmap || []).map((d) => (
                  <tr key={d.district}>
                    <td>{d.district}</td>
                    <td>{d.lots}</td>
                    <td>{fmt(d.verified_kg, 1)}</td>
                    <td style={{ minWidth: 120 }}>
                      <div className="bar-track">
                        <div
                          className="bar-fill"
                          style={{ width: `${Math.round((d.verified_kg / maxDistrict) * 100)}%` }}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {points.length > 0 && (
            <div style={{ marginTop: '0.8rem' }}>
              <MapContainer
                center={[19.5, 74.5]}
                zoom={5}
                className="map"
                scrollWheelZoom={false}
              >
                <TileLayer
                  attribution="&copy; OpenStreetMap"
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                {points.map((d) => (
                  <CircleMarker
                    key={d.district}
                    center={COORDS[d.district]}
                    radius={10 + (d.verified_kg / maxDistrict) * 26}
                    pathOptions={{ color: '#0f766e', fillColor: '#0f766e', fillOpacity: 0.35 }}
                  >
                    <Tooltip>
                      {d.district}: {fmt(d.verified_kg, 1)} kg across {d.lots} lots
                    </Tooltip>
                  </CircleMarker>
                ))}
              </MapContainer>
            </div>
          )}
        </div>

        <div className="card">
          <h2>Category breakdown</h2>
          <table>
            <thead>
              <tr>
                <th>Category</th>
                <th>Lots</th>
                <th>Verified kg</th>
                <th>Avg score</th>
              </tr>
            </thead>
            <tbody>
              {(a.category_breakdown || []).map((c) => (
                <tr key={c.material_category}>
                  <td>{c.material_category}</td>
                  <td>{c.lots}</td>
                  <td>{fmt(c.verified_kg, 1)}</td>
                  <td>
                    {fmt(c.avg_recovery_score, 1)}
                    <div className="bar-track" style={{ marginTop: 4 }}>
                      <div
                        className="bar-fill"
                        style={{ width: `${Math.min(100, c.avg_recovery_score || 0)}%` }}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
