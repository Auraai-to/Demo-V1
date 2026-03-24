import React, { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

function StatusBadge({ status }) {
  return <span className={`badge badge-${status}`}>{status.replace(/_/g, ' ')}</span>
}

export default function Dashboard() {
  const [runs, setRuns] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  const load = useCallback(async () => {
    try {
      const [runsData, statsData] = await Promise.all([api.getRuns(), api.getStats()])
      setRuns(runsData)
      setStats(statsData)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const interval = setInterval(load, 3000)
    return () => clearInterval(interval)
  }, [load])

  const clearAll = async () => {
    if (!confirm('Clear all runs?')) return
    await api.clearRuns()
    setRuns([])
    setStats(null)
  }

  const counts = {
    total:     runs.length,
    active:    runs.filter(r => ['planning','pending_plan_approval','executing','pending_approval'].includes(r.status)).length,
    pending:   runs.filter(r => r.status === 'pending_approval' || r.status === 'pending_plan_approval').length,
    completed: runs.filter(r => r.status === 'completed').length,
  }

  return (
    <>
      <div className="topbar">
        <span className="topbar-title">Dashboard</span>
        <span className="topbar-sub">Governed AI execution platform</span>
        <button className="btn btn-primary btn-sm" onClick={() => navigate('/new')}>
          + New Run
        </button>
      </div>

      <div className="page">

        {/* Run stats */}
        <div className="grid-4 mb-20">
          <div className="stat-card">
            <div className="stat-label">Total Runs</div>
            <div className="stat-value">{counts.total}</div>
            <div className="stat-meta">All time</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Active</div>
            <div className="stat-value text-accent">{counts.active}</div>
            <div className="stat-meta">Currently running</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Awaiting Approval</div>
            <div className="stat-value text-warning">{counts.pending}</div>
            <div className="stat-meta">Needs your review</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Completed</div>
            <div className="stat-value text-success">{counts.completed}</div>
            <div className="stat-meta">Successfully finished</div>
          </div>
        </div>

        {/* Governance stats */}
        {stats && (
          <div className="card mb-20">
            <div className="card-header" style={{ marginBottom: 12 }}>
              <div>
                <div className="card-title">⚖️ Governance Engine</div>
                <div className="card-sub">Real-time stats from the Action Wrapper + Evaluator layer</div>
              </div>
            </div>
            <div className="gov-summary">
              <div className="gov-stat">
                <div className="gov-stat-val text-accent">{stats.total_steps_executed}</div>
                <div className="gov-stat-label">Steps Executed</div>
              </div>
              <div className="gov-stat">
                <div className="gov-stat-val text-success">{stats.approvals_granted}</div>
                <div className="gov-stat-label">Approvals Granted</div>
              </div>
              <div className="gov-stat">
                <div className="gov-stat-val text-accent">{stats.governance_events}</div>
                <div className="gov-stat-label">Audit Events</div>
              </div>
              <div className="gov-stat">
                <div className="gov-stat-val" style={{ color: stats.avg_trust_score >= 0.85 ? 'var(--success)' : stats.avg_trust_score >= 0.70 ? 'var(--warning)' : 'var(--danger)' }}>
                  {stats.avg_trust_score ? (stats.avg_trust_score * 100).toFixed(0) + '%' : '—'}
                </div>
                <div className="gov-stat-label">Avg Trust Score</div>
              </div>
              {stats.tools_connected !== undefined && (
                <div className="gov-stat">
                  <div className="gov-stat-val text-success">{stats.tools_connected}</div>
                  <div className="gov-stat-label">Tools Connected</div>
                </div>
              )}
            </div>

            {/* Architecture layer flow */}
            <div style={{ marginTop: 4 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Every tool call flows through
              </div>
              <div className="layer-flow">
                {['Intent Agent', 'Planner', 'Governor', 'Action Wrapper (5 checks)', 'MCP Gateway', 'MCP Server'].map((node, i, arr) => (
                  <React.Fragment key={node}>
                    <div className={`layer-node${node.includes('Action Wrapper') || node.includes('Governor') ? ' active' : ''}`}>{node}</div>
                    {i < arr.length - 1 && <span className="layer-arrow">→</span>}
                  </React.Fragment>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Runs table */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Agent Runs</div>
              <div className="card-sub">Click a run to view plan, governance checks, and audit trail</div>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              {runs.length > 0 && (
                <button className="btn btn-secondary btn-sm" onClick={clearAll}>Clear All</button>
              )}
              <button className="btn btn-secondary btn-sm" onClick={load}>↻ Refresh</button>
            </div>
          </div>

          {loading ? (
            <div style={{ padding: '40px', textAlign: 'center' }}><div className="spinner" /></div>
          ) : runs.length === 0 ? (
            <div className="empty-state">
              <div className="icon">🤖</div>
              <h3>No runs yet</h3>
              <p>Launch a Research Analyst or Portfolio Manager to get started.</p>
              <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => navigate('/new')}>
                + New Run
              </button>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Agent</th>
                  <th>Intent</th>
                  <th>Steps</th>
                  <th>Audit Events</th>
                  <th>Status</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {runs.map(run => {
                  const done = run.steps.filter(s => s.status === 'completed').length
                  const ts = new Date(run.created_at).toLocaleTimeString()
                  const needsAction = run.status === 'pending_plan_approval' || run.status === 'pending_approval'
                  return (
                    <tr key={run.run_id} style={{ cursor: 'pointer' }}
                        onClick={() => navigate(`/runs/${run.run_id}`)}>
                      <td>
                        <span style={{ marginRight: 6 }}>{run.agent_type === 'research' ? '🔬' : '📊'}</span>
                        <span style={{ textTransform: 'capitalize' }}>{run.agent_type}</span>
                      </td>
                      <td style={{ maxWidth: 300 }}>
                        <span style={{ color: 'var(--text-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>
                          {run.intent}
                        </span>
                      </td>
                      <td style={{ fontVariantNumeric: 'tabular-nums' }}>{done}/{run.steps.length}</td>
                      <td style={{ color: 'var(--text-muted)' }}>{run.audit_log?.length ?? 0}</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <StatusBadge status={run.status} />
                          {needsAction && <span style={{ fontSize: 11, color: 'var(--warning)', fontWeight: 600 }}>⚠ Action needed</span>}
                        </div>
                      </td>
                      <td style={{ color: 'var(--text-muted)' }}>{ts}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  )
}
