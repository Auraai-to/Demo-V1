const BASE = (import.meta.env.VITE_API_URL || '') + '/api'

async function request(method, path, body) {
  const token = localStorage.getItem('aura_token')
  const headers = {}
  if (body) headers['Content-Type'] = 'application/json'
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401) {
    localStorage.removeItem('aura_token')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  // Auth
  login:          (email, password) => request('POST', '/auth/login', { email, password }),
  getMe:          ()  => request('GET', '/auth/me'),

  // Runs
  submitRun:      (agentType, intent) => request('POST', '/runs', { agent_type: agentType, intent }),
  getRuns:        ()       => request('GET', '/runs'),
  getRun:         (id)     => request('GET', `/runs/${id}`),
  approvePlan:    (id)     => request('POST', `/runs/${id}/approve-plan`),
  approveStep:    (id)     => request('POST', `/runs/${id}/approve`),
  cancelRun:      (id)     => request('POST', `/runs/${id}/cancel`),
  clearRuns:      ()       => request('DELETE', '/runs'),
  getStats:       ()       => request('GET', '/stats'),
  getTrustScores: ()       => request('GET', '/trust-scores'),

  // Integrations
  getIntegrations:   ()    => request('GET', '/integrations'),
  toggleIntegration: (id)  => request('POST', `/integrations/${id}/toggle`),
}
