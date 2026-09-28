const API = '/api/v1'
const TOKEN_KEY = 'kc_ops_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setSession(s) {
  localStorage.setItem(TOKEN_KEY, s.access_token)
  localStorage.setItem('kc_ops_role', s.role)
  localStorage.setItem('kc_ops_name', s.full_name || '')
  localStorage.setItem('kc_ops_user', s.user_id)
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem('kc_ops_role')
  localStorage.removeItem('kc_ops_name')
  localStorage.removeItem('kc_ops_user')
}

export function session() {
  const token = getToken()
  if (!token) return null
  return {
    token,
    role: localStorage.getItem('kc_ops_role'),
    name: localStorage.getItem('kc_ops_name'),
    userId: localStorage.getItem('kc_ops_user')
  }
}

async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = {}
  if (auth && getToken()) headers.Authorization = `Bearer ${getToken()}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined
  })
  const text = await res.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = text
  }
  if (!res.ok) {
    if (res.status === 401) clearSession()
    const detail = data?.detail
    const message =
      typeof detail === 'string' ? detail : detail?.message ? detail.message : `Failed (${res.status})`
    const err = new Error(message)
    err.status = res.status
    err.detail = detail
    throw err
  }
  return data
}

export async function login(email, password) {
  const form = new URLSearchParams()
  form.append('username', email)
  form.append('password', password)
  const res = await fetch(`${API}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form
  })
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new Error(data?.detail || 'Login failed')
  return data
}

export const api = {
  me: () => request('/auth/me'),
  // recycler
  recyclerProfile: () => request('/recyclers/me'),
  saveRecyclerProfile: (p) => request('/recyclers/me', { method: 'POST', body: p }),
  incomingLots: () => request('/recycler/lots'),
  verifyLot: (id, body) => request(`/recycler/lots/${id}/verify`, { method: 'POST', body }),
  payLot: (id, mode) => request(`/recycler/lots/${id}/pay?payment_mode=${mode}`, { method: 'POST' }),
  declineLot: (id, reason) =>
    request(`/recycler/lots/${id}/decline`, { method: 'POST', body: { reason } }),
  recyclerHistory: () => request('/recycler/history'),
  handovers: () => request('/recycler/handovers'),
  publishPrice: (body) => request('/prices', { method: 'POST', body }),
  myPrices: () => request('/prices/mine'),
  // admin
  allRecyclers: () => request('/admin/recyclers'),
  authorizeRecycler: (id, authorization_status, note) =>
    request(`/admin/recyclers/${id}/authorization`, {
      method: 'PATCH',
      body: { authorization_status, note }
    }),
  analytics: () => request('/admin/analytics'),
  fraudFlags: () => request('/admin/fraud-flags'),
  auditLog: () => request('/admin/audit-log'),
  allPrices: () => request('/admin/prices'),
  setBenchmark: (body) => request('/admin/prices/benchmark', { method: 'POST', body })
}

export { request }
