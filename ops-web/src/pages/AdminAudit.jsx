import { useEffect, useState } from 'react'
import { api } from '../lib/api'

export default function AdminAudit() {
  const [flags, setFlags] = useState([])
  const [log, setLog] = useState([])
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('audit')

  const load = async () => {
    try {
      const [f, l] = await Promise.all([api.fraudFlags(), api.auditLog()])
      setFlags(f)
      setLog(l)
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div className="grid">
      {error && <div className="error">{error}</div>}
      <div className="card">
        <div className="row">
          <button className={tab === 'audit' ? 'btn-primary' : 'btn-secondary'} onClick={() => setTab('audit')}>
            Audit log ({log.length})
          </button>
          <button className={tab === 'fraud' ? 'btn-primary' : 'btn-secondary'} onClick={() => setTab('fraud')}>
            Fraud & anomaly flags ({flags.length})
          </button>
          <span className="spacer" />
          <button className="btn-ghost btn-sm" onClick={load}>
            Refresh
          </button>
        </div>
      </div>

      {tab === 'audit' && (
        <div className="card">
          <h2>Audit trail (EPR compliance)</h2>
          <p className="muted">
            Immutable record of ministry actions — authorization changes, benchmark publications — for
            regulatory audit.
          </p>
          <div style={{ overflowX: 'auto' }}>
            <table className="log-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Actor</th>
                  <th>Action</th>
                  <th>Entity</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {log.map((row) => (
                  <tr key={row.id}>
                    <td className="muted">{new Date(row.created_at).toLocaleString()}</td>
                    <td>
                      <span className="badge created">{row.actor_role}</span>
                    </td>
                    <td>{row.action}</td>
                    <td className="muted">
                      {row.entity}
                      {row.entity_id ? ` · ${String(row.entity_id).slice(0, 8)}…` : ''}
                    </td>
                    <td>
                      {row.detail ? <pre className="detail">{JSON.stringify(row.detail, null, 1)}</pre> : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {log.length === 0 && <p className="muted">No audit entries yet.</p>}
        </div>
      )}

      {tab === 'fraud' && (
        <div className="card">
          <h2>Fraud & anomaly flags</h2>
          <p className="muted">
            Raised by the pricing anomaly detector (robust median/MAD z-score) and by weight
            discrepancies at verification.
          </p>
          <div style={{ overflowX: 'auto' }}>
            <table className="log-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Kind</th>
                  <th>Severity</th>
                  <th>Lot</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {flags.map((f) => (
                  <tr key={f.id}>
                    <td className="muted">{new Date(f.created_at).toLocaleString()}</td>
                    <td>{f.kind}</td>
                    <td>
                      <span className={`badge ${f.severity}`}>{f.severity}</span>
                    </td>
                    <td className="muted">{f.lot_id ? `${f.lot_id.slice(0, 8)}…` : '—'}</td>
                    <td>
                      {f.detail ? <pre className="detail">{JSON.stringify(f.detail, null, 1)}</pre> : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {flags.length === 0 && <p className="muted">No flags raised. Good sign.</p>}
        </div>
      )}
    </div>
  )
}
