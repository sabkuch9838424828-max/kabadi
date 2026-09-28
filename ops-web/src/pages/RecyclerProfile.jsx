import { useEffect, useState } from 'react'
import { api } from '../lib/api'

const CATEGORIES = ['PCB', 'battery', 'motor_magnet', 'cable', 'CRT', 'LCD', 'mixed_plastic', 'other']

const EMPTY = {
  name: '',
  district: '',
  state: '',
  materials_accepted: [],
  cpcb_registration_number: '',
  registration_number: '',
  contact_details: '',
  service_area_radius_km: 50,
  capacity_kg_per_day: 1000,
  pickup_available: true,
  latitude: null,
  longitude: null
}

export default function RecyclerProfile({ profile }) {
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (profile?.recycler) {
      setForm({ ...EMPTY, ...profile.recycler })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile])

  const useLocation = () => {
    if (!navigator.geolocation) return
    navigator.geolocation.getCurrentPosition(
      (pos) => setForm((f) => ({ ...f, latitude: pos.coords.latitude, longitude: pos.coords.longitude })),
      () => setError('Could not read your location')
    )
  }

  const toggleMaterial = (m) => {
    setForm((f) => ({
      ...f,
      materials_accepted: f.materials_accepted.includes(m)
        ? f.materials_accepted.filter((x) => x !== m)
        : [...f.materials_accepted, m]
    }))
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await api.saveRecyclerProfile({
        ...form,
        service_area_radius_km: Number(form.service_area_radius_km) || 50,
        capacity_kg_per_day: Number(form.capacity_kg_per_day) || 1000
      })
      setNotice('Facility profile saved. The ministry must authorize you before collectors are matched.')
      window.location.reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card">
      <h2>Facility profile</h2>
      <p className="muted">
        Your materials-accepted list and location drive collector matching. Authorization is granted by
        the ministry and requires a CPCB registration number.
      </p>
      {error && <div className="error">{error}</div>}
      {notice && <div className="notice">{notice}</div>}
      {profile?.recycler && (
        <p>
          Current status: <span className={`badge ${profile.recycler.authorization_status}`}>{profile.recycler.authorization_status}</span>
        </p>
      )}

      <form onSubmit={submit}>
        <div className="grid cols-2">
          <div className="field">
            <label>Facility name</label>
            <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="field">
            <label>District</label>
            <input value={form.district || ''} onChange={(e) => setForm({ ...form, district: e.target.value })} />
          </div>
          <div className="field">
            <label>State</label>
            <input value={form.state || ''} onChange={(e) => setForm({ ...form, state: e.target.value })} />
          </div>
          <div className="field">
            <label>CPCB registration number</label>
            <input
              value={form.cpcb_registration_number || ''}
              onChange={(e) => setForm({ ...form, cpcb_registration_number: e.target.value })}
              placeholder="e.g. CPCB/EW/2025/..."
            />
          </div>
          <div className="field">
            <label>Contact details</label>
            <input
              value={form.contact_details || ''}
              onChange={(e) => setForm({ ...form, contact_details: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Service area radius (km)</label>
            <input
              type="number"
              min="1"
              value={form.service_area_radius_km}
              onChange={(e) => setForm({ ...form, service_area_radius_km: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Capacity (kg/day)</label>
            <input
              type="number"
              min="1"
              value={form.capacity_kg_per_day}
              onChange={(e) => setForm({ ...form, capacity_kg_per_day: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Pickup service</label>
            <select
              value={String(form.pickup_available)}
              onChange={(e) => setForm({ ...form, pickup_available: e.target.value === 'true' })}
            >
              <option value="true">Available</option>
              <option value="false">Not available</option>
            </select>
          </div>
        </div>

        <div className="field">
          <label>Materials accepted</label>
          <div className="row">
            {CATEGORIES.map((c) => (
              <button
                type="button"
                key={c}
                className={form.materials_accepted.includes(c) ? 'btn-primary btn-sm' : 'btn-secondary btn-sm'}
                onClick={() => toggleMaterial(c)}
              >
                {c}
              </button>
            ))}
          </div>
        </div>

        <div className="row">
          <button type="button" className="btn-secondary btn-sm" onClick={useLocation}>
            📍 Use my location
          </button>
          {form.latitude != null && (
            <span className="muted">
              {Number(form.latitude).toFixed(4)}, {Number(form.longitude).toFixed(4)}
            </span>
          )}
        </div>

        <button className="btn-primary" type="submit" disabled={busy} style={{ marginTop: '0.9rem' }}>
          {busy ? 'Saving…' : 'Save facility profile'}
        </button>
      </form>
    </div>
  )
}
