import React, { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { api } from '../api'

export default function Sidebar() {
  const navigate = useNavigate()
  const [llmStatus, setLlmStatus] = useState(null)
  const [user, setUser] = useState(null)

  useEffect(() => {
    fetch((import.meta.env.VITE_API_URL || '') + '/api/health').then(r => r.json()).then(d => setLlmStatus(d.llm)).catch(() => {})
    api.getMe().then(setUser).catch(() => {})
  }, [])

  const logout = () => {
    localStorage.removeItem('aura_token')
    navigate('/login')
  }

  return (
    <nav className="sidebar">
      <div className="sidebar-logo">
        <h1>Aura</h1>
        <p>Your AI Command Center</p>
      </div>

      <div className="sidebar-nav">
        <div className="nav-section-label">Platform</div>

        <NavLink to="/dashboard" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="icon">⚡</span>
          Dashboard
        </NavLink>

        <button className="nav-item" onClick={() => navigate('/new')}>
          <span className="icon">＋</span>
          New Run
        </button>

        <NavLink to="/trust" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="icon">◆</span>
          Trust Registry
        </NavLink>

        <NavLink to="/integrations" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="icon">🔌</span>
          Integrations
        </NavLink>

        <div className="nav-section-label" style={{ marginTop: 16 }}>Marketing Agents</div>

        <button className="nav-item" onClick={() => navigate('/new?agent=campaign')}>
          <span className="icon">📈</span>
          Campaign Analyst
        </button>

        <button className="nav-item" onClick={() => navigate('/new?agent=optimizer')}>
          <span className="icon">🎯</span>
          Ad Optimizer
        </button>

        <div className="nav-section-label" style={{ marginTop: 16 }}>Finance Agents</div>

        <button className="nav-item" onClick={() => navigate('/new?agent=research')}>
          <span className="icon">🔬</span>
          Research Analyst
        </button>

        <button className="nav-item" onClick={() => navigate('/new?agent=portfolio')}>
          <span className="icon">📊</span>
          Portfolio Manager
        </button>
      </div>

      <div className="sidebar-footer">
        {user && (
          <div className="sidebar-user">
            <div className="sidebar-user-name">{user.name}</div>
            <div className="sidebar-user-email">{user.email}</div>
          </div>
        )}
        <button className="btn btn-secondary btn-sm" onClick={logout} style={{ width: '100%', marginBottom: 8 }}>
          Sign out
        </button>
        <div className="sidebar-badge" style={{ marginBottom: 8 }}>
          <span className="dot-green" />
          <span>Governed · Audited · Safe</span>
        </div>
        {llmStatus && (
          <div className="sidebar-badge" style={{
            background: llmStatus === 'not_configured'
              ? 'rgba(239,68,68,0.08)' : 'rgba(139,92,246,0.1)',
            borderRadius: 8, padding: '6px 10px',
          }}>
            <span style={{ fontSize: 12 }}>🤖</span>
            <span style={{
              fontSize: 11,
              color: llmStatus === 'not_configured' ? 'var(--danger)' : 'var(--purple)',
            }}>
              {llmStatus === 'not_configured' ? 'LLM: not configured' : llmStatus}
            </span>
          </div>
        )}
      </div>
    </nav>
  )
}
