import { useEffect, useState } from 'react'
import { api } from '../lib/api'

export default function AdminRecyclers() {
  const [rows, setRows] = useState([])
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(null)
  const [filter, setFilter] = useState('all')

  const load = async () => {
    try {
      setRows(await api.allRecyclers())
      setError(null)
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const update = async (r, status) => {
    setBusy(r.recycler_id)
    setError(null)
    setNotice(null)
    try {
      const note =
        status === 'authorized'
          ? 'CPCB registration verified by ministry officer'
          : status === 'suspended'
            ? 'Suspended pending compliance review'
            : 'Returned for verification'
      await api.authorizeRecycler(r.recycler_id, status, note)
      setNotice(`${r.name} is now ${status}. Change recorded in the audit log.`)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(null)
    }
  }

  const visible = rows.filter((r) =>
    filter === 'all' ? true : filter === 'unverified' ? r.authorization_status !== 'authorized' : r.authorization_status === filter
  )

  return (
    <div className="grid">
      {error && <div className="error">{error}</div>}
      {notice && <div className="notice">{notice}</div>}

      <div className="card">
        <div className="row">
          <h2 style={{ margin: 0 }}>Recycler authorization (CPCB / EPR)</h2>
          <span className="spacer" />
          <select value={filter} onChange={(e) => setFilter(e.target.value)} style={{ padding: '0.4rem' }}>
            <option value="all">All</option>
            <option value="authorized">Authorized</option>
            <option value="unverified">Not authorized</option>
            <option value="pending">Pending</option>
            <option value="suspended">Suspended</option>
          </select>
          <button className="btn-secondary btn-sm" onClick={load}>
            Refresh
          </button>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th>Facility</th>
                <th>District</th>
                <th>CPCB reg. no.</th>
                <th>Materials</th>
                <th>Capacity</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((r) => (
                <tr key={r.recycler_id}>
                  <td>
                    <strong>{r.name}</strong>
                    {r.pickup_available && <div className="muted">pickup available</div>}
                  </td>
                  <td>{r.district || '—'}</td>
                  <td className="muted">{r.cpcb_registration_number || r.registration_number || '—'}</td>
                  <td className="muted">{(r.materials_accepted || []).join(', ') || '—'}</td>
                  <td className="muted">{r.capacity_kg_per_day ? `${Number(r.capacity_kg_per_day)} kg/day` : '—'}</td>
                  <td>
                    <span className={`badge ${r.authorization_status}`}>{r.authorization_status}</span>
                  </td>
                  <td>
                    <div className="row">
                      {r.authorization_status !== 'authorized' && (
                        <button
                          className="btn-primary btn-sm"
                          disabled={busy === r.recycler_id || !(r.cpcb_registration_number || r.registration_number)}
                          title={
                            !(r.cpcb_registration_number || r.registration_number)
                              ? 'A CPCB registration number is required to authorize'
                              : ''
                          }
                          onClick={() => update(r, 'authorized')}
                        >
                          Authorize
                        </button>
                      )}
                      {r.authorization_status === 'authorized' && (
                        <button className="btn-danger btn-sm" disabled={busy === r.recycler_id} onClick={() => update(r, 'suspended')}>
                          Suspend
                        </button>
                      )}
                      {r.authorization_status !== 'pending' && r.authorization_status !== 'authorized' && (
                        <button className="btn-secondary btn-sm" disabled={busy === r.recycler_id} onClick={() => update(r, 'pending')}>
                          Mark pending
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {visible.length === 0 && <p className="muted">No recyclers in this filter.</p>}
      </div>
    </div>
  )
}
