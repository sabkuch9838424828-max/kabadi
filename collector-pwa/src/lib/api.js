/**
 * Thin API client. All calls go through the Vite proxy at /api so the browser
 * only ever talks to the PWA origin.
 */
const API = '/api/v1'

const TOKEN_KEY = 'kc_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setSession(session) {
  localStorage.setItem(TOKEN_KEY, session.access_token)
  localStorage.setItem('kc_role', session.role)
  localStorage.setItem('kc_user_id', session.user_id)
  localStorage.setItem('kc_name', session.full_name || '')
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem('kc_role')
  localStorage.removeItem('kc_user_id')
  localStorage.removeItem('kc_name')
}

export function currentUser() {
  const token = getToken()
  if (!token) return null
  return {
    token,
    role: localStorage.getItem('kc_role'),
    userId: localStorage.getItem('kc_user_id'),
    name: localStorage.getItem('kc_name')
  }
}

class ApiError extends Error {
  constructor(message, status, detail) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

async function request(path, { method = 'GET', body, auth = true, isForm = false } = {}) {
  const headers = {}
  if (auth && getToken()) headers.Authorization = `Bearer ${getToken()}`
  if (!isForm && body !== undefined) headers['Content-Type'] = 'application/json'

  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: isForm ? body : body !== undefined ? JSON.stringify(body) : undefined
  })

  const text = await res.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = text
  }

  if (!res.ok) {
    const detail = data && data.detail ? data.detail : data
    const message =
      typeof detail === 'string'
        ? detail
        : detail && detail.message
          ? detail.message
          : `Request failed (${res.status})`
    if (res.status === 401) clearSession()
    throw new ApiError(message, res.status, detail)
  }
  return data
}

export const api = {
  // --- auth ---
  register: (payload) => request('/auth/register', { method: 'POST', body: payload, auth: false }),
  login: async (email, password) => {
    const form = new URLSearchParams()
    form.append('username', email)
    form.append('password', password)
    const res = await fetch(`${API}/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form
    })
    const data = await res.json().catch(() => null)
    if (!res.ok) throw new ApiError(data?.detail || 'Login failed', res.status, data)
    return data
  },
  me: () => request('/auth/me'),

  // --- collector profile ---
  saveCollectorProfile: (payload) => request('/collectors/me', { method: 'POST', body: payload }),
  getCollectorProfile: () => request('/collectors/me'),
  ledger: () => request('/collectors/me/ledger'),

  // --- pricing ---
  priceBoard: (location) =>
    request(`/prices/board${location ? `?location=${encodeURIComponent(location)}` : ''}`, {
      auth: false
    }),
  priceHistory: (category) => request(`/prices/history/${category}`, { auth: false }),

  // --- ml ---
  valuationConfig: () => request('/ml/valuation-config', { auth: false }),
  classify: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/ml/classify', { method: 'POST', body: form, isForm: true, auth: false })
  },
  valuation: (category, weight, location) =>
    request(
      `/ml/valuation?category=${encodeURIComponent(category)}&weight_kg=${weight}` +
        (location ? `&location=${encodeURIComponent(location)}` : ''),
      { auth: false }
    ),

  // --- lots ---
  createLot: (payload) => request('/lots', { method: 'POST', body: payload }),
  listLots: () => request('/lots'),
  syncLots: (payload) => request('/lots/sync', { method: 'POST', body: payload }),
  lotMatches: (lotId) => request(`/lots/${lotId}/matches`),
  matchLot: (lotId, recyclerId) =>
    request(`/lots/${lotId}/match`, { method: 'POST', body: { recycler_id: recyclerId } }),
  createHandover: (lotId, payload) =>
    request(`/lots/${lotId}/handover`, { method: 'POST', body: payload }),

  // --- recyclers ---
  recyclers: (category) =>
    request(`/recyclers${category ? `?category=${encodeURIComponent(category)}` : ''}`, {
      auth: false
    }),
  matchRecyclers: ({ category, weightKg, latitude, longitude, authorizedOnly = true }) => {
    const params = new URLSearchParams({
      category,
      weight_kg: String(weightKg),
      authorized_only: String(authorizedOnly)
    })
    if (latitude != null) params.append('latitude', String(latitude))
    if (longitude != null) params.append('longitude', String(longitude))
    return request(`/recyclers/match?${params.toString()}`, { auth: false })
  }
}

export { ApiError }
