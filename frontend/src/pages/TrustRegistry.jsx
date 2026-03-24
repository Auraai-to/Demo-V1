import React, { useEffect, useState, useCallback } from 'react'
import { api } from '../api'

function TrustBar({ score }) {
  const pct = Math.round(score * 100)
  const color = score >= 0.85 ? 'var(--success)' : score >= 0.70 ? 'var(--warning)' : 'var(--danger)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div style={{ flex: 1, height: 6, background: 'var(--border)', borderRadius: 3 }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.4s' }} />
      </div>
      <span style={{ fontSize: 13, fontWeight: 700, color, minWidth: 38, textAlign: 'right' }}>{pct}%</span>
    </div>
  )
}

function StatusBadge({ status }) {
  const colors = { healthy: 'trust-healthy', degraded: 'trust-degraded', critical: 'trust-critical' }
  return <span className={`trust-badge ${colors[status] || 'trust-degraded'}`}>◆ {status}</span>
}

export default function TrustRegistry() {
  const [scores, setScores] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)

  const load = useCallback(async () => {
    try {
      const [trust] = await Promise.all([
        api.getTrustScores(),
        api.getStats(),
      ])
      setScores(trust)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const interval = setInterval(() => { load(); setTick(t => t + 1) }, 2000)
    return () => clearInterval(interval)
  }, [load])

  const entries = scores ? Object.entries(scores).sort((a, b) => b[1].score - a[1].score) : []

  return (
    <>
      <div className="topbar">
        <span className="topbar-title">Trust Registry</span>
        <span className="topbar-sub">Live EMA-updated scores — refreshes every 2s</span>
      </div>

      <div className="page">
        <div className="card mb-16" style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.7 }}>
            Every tool has a pre-computed reliability score (0.0–1.0) read at sub-5ms before each invocation.
            Scores update continuously using an <strong>Exponential Moving Average</strong> (α=0.15) after every execution.
            A score below <strong>0.70</strong> immediately blocks the tool — the Action Wrapper rejects the call.
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 20, fontSize: 12 }}>
            <span><span style={{ color: 'var(--success)', fontWeight: 700 }}>■</span> Healthy ≥ 0.85</span>
            <span><span style={{ color: 'var(--warning)', fontWeight: 700 }}>■</span> Degraded 0.70–0.85</span>
            <span><span style={{ color: 'var(--danger)', fontWeight: 700 }}>■</span> Critical &lt; 0.70 — blocked</span>
          </div>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: 60 }}><div className="spinner" /></div>
        ) : (
          <div className="card">
            <div className="card-header">
              <div className="card-title">Tool Trust Scores</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Live · EMA(α=0.15) · score = 0.7×success_rate + 0.3×(1−error_rate)
              </div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Tool</th>
                  <th>Score</th>
                  <th style={{ minWidth: 160 }}>Trust Bar</th>
                  <th>Status</th>
                  <th>Invocations</th>
                  <th>Success Rate</th>
                  <th>Avg Latency</th>
                  <th>Last Updated</th>
                </tr>
              </thead>
              <tbody>
                {entries.map(([tool, s]) => (
                  <tr key={tool}>
                    <td><code style={{ fontSize: 12 }}>{tool}</code></td>
                    <td style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                      {(s.score * 100).toFixed(1)}%
                    </td>
                    <td><TrustBar score={s.score} /></td>
                    <td><StatusBadge status={s.status} /></td>
                    <td style={{ color: 'var(--text-muted)' }}>{s.invocations}</td>
                    <td style={{ color: s.success_rate === null ? 'var(--text-muted)' : 'var(--text)' }}>
                      {s.success_rate !== null ? `${(s.success_rate * 100).toFixed(0)}%` : '—'}
                    </td>
                    <td style={{ color: 'var(--text-muted)' }}>
                      {s.avg_latency_ms !== null ? `${s.avg_latency_ms.toFixed(0)} ms` : '—'}
                    </td>
                    <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                      {new Date(s.last_updated).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {entries.every(([, s]) => s.invocations === 0) && (
              <div style={{ textAlign: 'center', padding: '20px 0', fontSize: 12, color: 'var(--text-muted)' }}>
                Scores currently at seed values. Run an agent to see scores update live.
              </div>
            )}
          </div>
        )}
      </div>
    </>
  )
}
