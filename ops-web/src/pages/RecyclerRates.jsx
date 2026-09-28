import { useEffect, useState } from 'react'
import { api } from '../lib/api'

const CATEGORIES = [
  'PCB',
  'battery',
  'motor_magnet',
  'cable',
  'CRT',
  'LCD',
  'mixed_plastic',
  'other'
]

export default function RecyclerRates() {
  const [mine, setMine] = useState([])
  const [form, setForm] = useState({ material_category: 'PCB', location: '', buying_price: '' })
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(false)
  const [profile, setProfile] = useState(null)

  const load = async () => {
    try {
      const [m, p] = await Promise.all([api.myPrices(), api.recyclerProfile()])
      setMine(m)
      setProfile(p)
      if (p?.district && !form.location) setForm((f) => ({ ...f, location: p.district }))
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const save = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await api.publishPrice({
        material_category: form.material_category,
        location: form.location || undefined,
        buying_price: Number(form.buying_price)
      })
      setNotice('Rate published to the price board.')
      setForm({ ...form, buying_price: '' })
      await load()
    } catch (err) {
      // The backend rejects off-market quotes with a detailed anomaly payload.
      const detail = err.detail
      setError(
        typeof detail === 'object' && detail?.anomaly
          ? `${detail.message} (${detail.anomaly.detail})`
          : err.message
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid cols-2">
      <div className="card">
        <h2>Publish a buying rate</h2>
        <p className="muted">
          Rates feed the collector price board and the matching engine. Off-market quotes are
          rejected by the anomaly detector and logged.
        </p>
        {error && <div className="error">{error}</div>}
        {notice && <div className="notice">{notice}</div>}
        {profile && profile.authorization_status !== 'authorized' && (
          <div className="warn">
            Your facility is <strong>{profile.authorization_status}</strong>. Rates are accepted but
            collectors will not be matched to you until the ministry authorizes you.
          </div>
        )}
        <form onSubmit={save}>
          <div className="field">
            <label>Material category</label>
            <select
              value={form.material_category}
              onChange={(e) => setForm({ ...form, material_category: e.target.value })}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Location / district (blank = your district)</label>
            <input
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
              placeholder="e.g. Pune"
            />
          </div>
          <div className="field">
            <label>Buying price (₹ per kg)</label>
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
            {busy ? 'Publishing…' : 'Publish rate'}
          </button>
        </form>
      </div>

      <div className="card">
        <h2>My published rates</h2>
        {mine.length === 0 && <p className="muted">No rates published yet.</p>}
        {mine.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Category</th>
                <th>Location</th>
                <th>₹/kg</th>
                <th>Published</th>
              </tr>
            </thead>
            <tbody>
              {mine.map((p) => (
                <tr key={p.price_id}>
                  <td>{p.material_category}</td>
                  <td>{p.location}</td>
                  <td>{Number(p.buying_price).toFixed(2)}</td>
                  <td className="muted">{new Date(p.recorded_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
