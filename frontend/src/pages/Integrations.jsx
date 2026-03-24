import React, { useEffect, useState } from 'react'
import { api } from '../api'

const CATEGORY_ICONS = {
  Advertising: '📣',
  Analytics:   '📊',
  CRM:         '🤝',
  Email:       '✉️',
  Messaging:   '💬',
}

export default function Integrations() {
  const [integrations, setIntegrations] = useState([])
  const [loading, setLoading]           = useState(true)
  const [toggling, setToggling]         = useState(null)

  useEffect(() => {
    api.getIntegrations()
      .then(setIntegrations)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const toggle = async (id) => {
    setToggling(id)
    try {
      const updated = await api.toggleIntegration(id)
      setIntegrations(prev => prev.map(i => i.id === id ? updated : i))
    } catch (e) {
      console.error(e)
    } finally {
      setToggling(null)
    }
  }

  const connected = integrations.filter(i => i.connected).length

  return (
    <>
      <div className="topbar">
        <span className="topbar-title">Integrations</span>
        <span className="topbar-sub">{connected} of {integrations.length} tools connected</span>
      </div>

      <div className="page">
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center' }}><div className="spinner" /></div>
        ) : (
          <div className="grid-4">
            {integrations.map(item => (
              <div key={item.id} className="integration-card">
                <div className="integration-icon">
                  {CATEGORY_ICONS[item.category] ?? '🔌'}
                </div>
                <div className="integration-name">{item.name}</div>
                <div className="integration-category">{item.category}</div>
                <span className={`badge badge-${item.connected ? 'connected' : 'not_connected'}`}>
                  {item.connected ? 'Connected' : 'Not connected'}
                </span>
                <button
                  className={`btn btn-sm ${item.connected ? 'btn-secondary' : 'btn-primary'}`}
                  style={{ marginTop: 10, width: '100%' }}
                  disabled={toggling === item.id}
                  onClick={() => toggle(item.id)}
                >
                  {toggling === item.id ? '…' : item.connected ? 'Disconnect' : 'Connect'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  )
}
