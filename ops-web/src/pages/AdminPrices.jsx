import { useEffect, useState } from 'react'
import { api } from '../lib/api'

const CATEGORIES = ['PCB', 'battery', 'motor_magnet', 'cable', 'CRT', 'LCD', 'mixed_plastic', 'other']

export default function AdminPrices() {
  const [rows, setRows] = useState([])
  const [form, setForm] = useState({ material_category: 'PCB', location: 'IN', buying_price: '' })
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = async () => {
    try {
      setRows(await api.allPrices())
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await api.setBenchmark({
        material_category: form.material_category,
        location: form.location || 'IN',
        buying_price: Number(form.buying_price)
      })
      setNotice('MSP benchmark published. It anchors the collector price board for this category.')
      setForm({ ...form, buying_price: '' })
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const benchmarks = rows.filter((r) => r.is_benchmark)
  const recyclerRates = rows.filter((r) => !r.is_benchmark)

  return (
    <div className="grid cols-2">
      <div className="card">
        <h2>Set MSP benchmark (Ministry of Mines)</h2>
        <p className="muted">
          Benchmarks anchor the price board and give the anomaly detector its reference band. Setting
          a benchmark is recorded in the audit log.
        </p>
        {error && <div className="error">{error}</div>}
        {notice && <div className="notice">{notice}</div>}
        <form onSubmit={submit}>
          <div className="field">
            <label>Material category</label>
            <select
              value={form.material_category}
              onChange={(e) => setForm({ ...form, material_category: e.target.value })}
            >
              {CATEGORIES.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Location</label>
            <input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
          </div>
          <div className="field">
            <label>Benchmark price (₹ per kg)</label>
            <input
              type="number"
              min="1"
              step="0.01"
              required
              value={form.buying_price}
              onChange={(e) => setForm({ ...form, buying_price: e.target.value })}
            />
          </div>
          <button className="btn-primary" type="submit" disabled={busy}>
            {busy ? 'Publishing…' : 'Publish benchmark'}
          </button>
        </form>
      </div>

      <div className="card">
        <h2>Benchmarks on file</h2>
        <table>
          <thead>
            <tr>
              <th>Category</th>
              <th>Location</th>
              <th>₹/kg</th>
              <th>Set</th>
            </tr>
          </thead>
          <tbody>
            {benchmarks.map((r) => (
              <tr key={r.price_id}>
                <td>{r.material_category}</td>
                <td>{r.location}</td>
                <td>{Number(r.buying_price).toFixed(2)}</td>
                <td className="muted">{new Date(r.recorded_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {benchmarks.length === 0 && <p className="muted">No benchmarks set.</p>}
      </div>

      <div className="card" style={{ gridColumn: '1 / -1' }}>
        <h2>Published rates (recyclers + ministry)</h2>
        <div style={{ overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Category</th>
                <th>Location</th>
                <th>₹/kg</th>
                <th>Recorded</th>
              </tr>
            </thead>
            <tbody>
              {recyclerRates.slice(0, 100).map((r) => (
                <tr key={r.price_id}>
                  <td>
                    <span className="badge created">{r.source}</span>
                  </td>
                  <td>{r.material_category}</td>
                  <td>{r.location}</td>
                  <td>{Number(r.buying_price).toFixed(2)}</td>
                  <td className="muted">{new Date(r.recorded_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
