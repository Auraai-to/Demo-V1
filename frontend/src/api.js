const BASE = (import.meta.env.VITE_API_URL ?? '') + '/api'

async function request(method, path, body) {
  const headers = {}
  if (body) headers['Content-Type'] = 'application/json'

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
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
