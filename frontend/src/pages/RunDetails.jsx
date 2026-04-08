import React, { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function StatusBadge({ status }) {
  return <span className={`badge badge-${status}`}>{status.replace(/_/g, ' ')}</span>
}

function RiskBar({ score }) {
  const pct = Math.round(score * 100)
  const color = score < 0.4 ? 'var(--success)' : score < 0.7 ? 'var(--warning)' : 'var(--danger)'
  const label = score < 0.4 ? 'low' : score < 0.7 ? 'med' : 'high'
  return (
    <div className="risk-bar" style={{ minWidth: 120 }}>
      <div className="risk-bar-track">
        <div className="risk-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className={`step-risk ${label}`}>{pct}%</span>
    </div>
  )
}

function TrustBadge({ score }) {
  if (score == null) return null
  const cls = score >= 0.85 ? 'trust-healthy' : score >= 0.70 ? 'trust-degraded' : 'trust-critical'
  const label = score >= 0.85 ? 'healthy' : score >= 0.70 ? 'degraded' : 'critical'
  return (
    <span className={`trust-badge ${cls}`}>
      ◆ {(score * 100).toFixed(0)}% {label}
    </span>
  )
}

function StepIcon({ status }) {
  return { not_started: '○', executing: '⟳', pending_approval: '⚠', completed: '✓', failed: '✕' }[status] || '○'
}

function GovernanceChecks({ checks }) {
  if (!checks || checks.length === 0) return null
  return (
    <div className="governance-checks">
      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Action Wrapper — 5 Checks
      </div>
      {checks.map((c, i) => (
        <div key={i} className={`gov-check ${c.status}`}>
          <span className="check-icon">{c.status === 'pass' ? '✓' : c.status === 'fail' ? '✕' : '…'}</span>
          <span className="check-name">{c.name}</span>
          <span className="check-value">{c.value}</span>
        </div>
      ))}
    </div>
  )
}

function formatValue(v, indent = '') {
  if (v === null || v === undefined) return '—'
  if (Array.isArray(v)) {
    if (v.length === 0) return '(none)'
    if (typeof v[0] === 'object') {
      return '\n' + v.map(item => indent + '  ' + formatValue(item, indent + '  ')).join('\n')
    }
    return v.join(', ')
  }
  if (typeof v === 'object') {
    return '\n' + Object.entries(v)
      .map(([k2, v2]) => `${indent}  ${k2.replace(/_/g, ' ')}: ${formatValue(v2, indent + '  ')}`)
      .join('\n')
  }
  return String(v)
}

function ResultView({ result }) {
  if (!result) return null
  if (result.error) {
    return (
      <div className="step-result" style={{ borderColor: 'rgba(239,68,68,0.3)', color: 'var(--danger)' }}>
        Error: {result.error}
      </div>
    )
  }
  const lines = Object.entries(result)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => {
      const key = k.replace(/_/g, ' ')
      return `${key}: ${formatValue(v)}`
    })
    .join('\n')
  return <div className="step-result">{lines}</div>
}

// ---------------------------------------------------------------------------
// Pipeline flow — 4 stages
// ---------------------------------------------------------------------------

const STAGE_ICONS = {
  intent_agent:    '🧠',
  tool_router:     '🔀',
  plan_builder:    '📋',
  workflow_engine: '⚙️',
}

function PipelineFlow({ pipeline }) {
  if (!pipeline || pipeline.length === 0) return null
  return (
    <div className="pipeline-flow">
      {pipeline.map(stage => (
        <div key={stage.name} className={`pipeline-stage ${stage.status}`}>
          <div className="pipeline-stage-icon">{STAGE_ICONS[stage.name] || '●'}</div>
          <div className="pipeline-stage-name">{stage.label}</div>
          <div className="pipeline-stage-detail">
            {stage.detail || (stage.status === 'pending' ? 'Waiting…' : '')}
          </div>
          <div className="pipeline-stage-status">
            {stage.status === 'active' && <><span className="spinner" style={{ width: 8, height: 8, borderWidth: 1.5, marginRight: 4 }} />Running</>}
            {stage.status === 'completed' && '✓ Done'}
            {stage.status === 'pending' && '○ Pending'}
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Plan Review panel
// ---------------------------------------------------------------------------

function PlanReview({ run, onApprove, onCancel, approving, cancelling, liveTrust = TOOL_TRUST_SCORES_FE }) {
  const d = run.intent_data || {}
  const requiresApproval = run.steps.filter(s => s.requires_approval)
  const highRisk = run.steps.filter(s => s.risk_score >= 0.70)

  return (
    <>
      <div className="plan-banner">
        <h3>🔍 Plan Ready — Review Before Execution</h3>
        <p>
          The AI has analysed your goal and built a {run.steps.length}-step plan.
          <strong> Nothing will execute until you approve.</strong>
          {requiresApproval.length > 0 && (
            <> {requiresApproval.length} step{requiresApproval.length > 1 ? 's' : ''} will pause again mid-run for a second approval.</>
          )}
        </p>
      </div>

      {/* What the AI understood */}
      {Object.keys(d).length > 0 && (
        <div className="card mb-16">
          <div className="card-header" style={{ marginBottom: 12 }}>
            <div className="card-title">🧠 What the AI Understood</div>
            <div className="card-sub">Parsed by Intent Agent · confirm this matches your goal before approving</div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 24px' }}>
            {d.objective && (
              <div style={{ gridColumn: '1 / -1', background: 'var(--surface2)', borderRadius: 8, padding: '10px 14px', marginBottom: 4 }}>
                <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', marginBottom: 4 }}>Objective</div>
                <div style={{ fontSize: 13.5, color: 'var(--text)' }}>{d.objective}</div>
              </div>
            )}
            {d.brand && <IntentField label="Brand" value={d.brand} />}
            {d.symbols?.length > 0 && <IntentField label="Symbols" value={d.symbols.join(', ')} />}
            {d.competitors?.length > 0 && <IntentField label="Competitors" value={d.competitors.join(', ')} />}
            {d.category && <IntentField label="Category" value={d.category} />}
            {d.key_entities?.length > 0 && <IntentField label="Key Entities" value={d.key_entities.join(', ')} />}
            <IntentField label="Agent" value={run.agent_type} />
          </div>
        </div>
      )}

      {/* Plan steps */}
      <div className="card mb-16">
        <div className="card-header">
          <div>
            <div className="card-title">📋 Execution Plan</div>
            <div className="card-sub">
              {run.steps.length} steps · {highRisk.length} high-risk · {requiresApproval.length} mid-run approval{requiresApproval.length !== 1 ? 's' : ''}
            </div>
          </div>
        </div>

        <div>
          {run.steps.map((step, idx) => {
            const trust = liveTrust[step.tool_id] ?? TOOL_TRUST_SCORES_FE[step.tool_id] ?? 0.88
            const riskColor = step.risk_score < 0.4 ? 'var(--success)' : step.risk_score < 0.7 ? 'var(--warning)' : 'var(--danger)'
            return (
              <div key={step.step_id} className="plan-review-step">
                <div className="plan-step-num">{idx + 1}</div>
                <div className="plan-step-body">
                  <div className="plan-step-name">
                    {step.name}
                    {step.requires_approval && (
                      <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--warning)', fontWeight: 600, background: 'rgba(245,158,11,0.12)', padding: '1px 6px', borderRadius: 4 }}>
                        ⚠ APPROVAL GATE
                      </span>
                    )}
                  </div>
                  {step.description && (
                    <div style={{ fontSize: 12.5, color: 'var(--text-dim)', margin: '5px 0 6px', lineHeight: 1.6 }}>
                      {step.description}
                    </div>
                  )}
                  <div className="plan-step-meta">
                    <span style={{ fontFamily: 'monospace', fontSize: 11, background: 'var(--surface2)', padding: '1px 7px', borderRadius: 4 }}>{step.tool_id}</span>
                    <TrustBadge score={trust} />
                    <span style={{ fontSize: 11, color: riskColor, fontWeight: 600 }}>
                      Risk {Math.round(step.risk_score * 100)}%
                    </span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        <div className="divider" />
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={onApprove} disabled={approving}>
            {approving ? <><span className="spinner" /> Approving…</> : '✓ Approve Plan & Execute'}
          </button>
          <button className="btn btn-danger btn-sm" onClick={onCancel} disabled={cancelling}>
            ✕ Cancel
          </button>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Your approval will be recorded in the audit trail.
          </span>
        </div>
      </div>
    </>
  )
}

function IntentField({ label, value }) {
  return (
    <div style={{ padding: '6px 0' }}>
      <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>{value}</div>
    </div>
  )
}

// Seed trust scores for plan review display (before execution updates them)
const TOOL_TRUST_SCORES_FE = {
  stock_lookup: 0.94, news_sentiment: 0.89, peer_comparison: 0.91,
  sector_analysis: 0.87, get_portfolio: 0.96, risk_assessment: 0.93,
  calculate_rebalance: 0.88, execute_trade: 0.82,
}

async function fetchLiveTrustScores() {
  try {
    return await fetch((import.meta.env.VITE_API_URL || '') + '/api/trust-scores').then(r => r.json())
  } catch { return {} }
}

// ---------------------------------------------------------------------------
// Audit Trail panel
// ---------------------------------------------------------------------------

function AuditTrail({ entries }) {
  if (!entries || entries.length === 0) {
    return (
      <div className="empty-state" style={{ padding: '32px 0' }}>
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No audit events yet.</div>
      </div>
    )
  }

  return (
    <div className="audit-log">
      {entries.map(e => {
        const t = new Date(e.timestamp).toLocaleTimeString()
        return (
          <div key={e.event_id} className="audit-entry">
            <span className="audit-time">{t}</span>
            <span className={`audit-action ${e.status}`}>{e.action_type}</span>
            <div className="audit-meta">
              {e.tool_id   && <span>tool={e.tool_id}</span>}
              {e.step_id   && <span>step={e.step_id}</span>}
              {e.risk_score  != null && <span>risk={Math.round(e.risk_score * 100)}%</span>}
              {e.trust_score != null && <span>trust={(e.trust_score * 100).toFixed(0)}%</span>}
              {e.reason_code && <span style={{ color: 'var(--text-dim)' }}>{e.reason_code}</span>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Steps panel
// ---------------------------------------------------------------------------

function StepsPanel({ run, onApproveStep, onCancel, approving, cancelling }) {
  const [expandedSteps, setExpandedSteps] = useState(new Set())

  useEffect(() => {
    setExpandedSteps(prev => {
      const next = new Set(prev)
      run.steps.forEach(s => {
        if (['executing', 'completed', 'failed'].includes(s.status)) next.add(s.step_id)
      })
      return next
    })
  }, [run.steps])

  const toggleStep = (id) => setExpandedSteps(prev => {
    const next = new Set(prev)
    next.has(id) ? next.delete(id) : next.add(id)
    return next
  })

  const pendingStep = run.steps.find(s => s.status === 'pending_approval')

  return (
    <>
      {run.status === 'pending_approval' && pendingStep && (
        <div className="approval-banner">
          <div className="icon">⚠️</div>
          <div>
            <h3>Human Approval Required — Step {pendingStep.step_id}</h3>
            <p>
              <strong>{pendingStep.name}</strong> has risk score{' '}
              <strong>{Math.round(pendingStep.risk_score * 100)}%</strong>.
              This step is paused. Review and approve to continue execution.
            </p>
          </div>
          <div className="approval-actions">
            <button className="btn btn-danger btn-sm" onClick={onCancel} disabled={cancelling}>✕ Reject</button>
            <button className="btn btn-success" onClick={onApproveStep} disabled={approving}>
              {approving ? <><span className="spinner" /> Approving…</> : '✓ Approve & Continue'}
            </button>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <div className="card-title">Execution Steps</div>
          <div className="text-muted" style={{ fontSize: 12 }}>Click a step to expand results + governance checks</div>
        </div>

        <div className="steps-list">
          {run.steps.map(step => {
            const expanded = expandedSteps.has(step.step_id)
            const hasData = (step.result && Object.keys(step.result).length > 0) || step.governance_checks?.length > 0

            return (
              <div key={step.step_id} className="step-item">
                <div className={`step-dot ${step.status}`}>
                  <StepIcon status={step.status} />
                </div>

                <div className="step-body">
                  <div
                    className="step-name"
                    style={{ cursor: hasData ? 'pointer' : 'default' }}
                    onClick={() => hasData && toggleStep(step.step_id)}
                  >
                    {step.name}
                    {step.requires_approval && (
                      <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--warning)', fontWeight: 600 }}>
                        [APPROVAL GATE]
                      </span>
                    )}
                    {hasData && (
                      <span style={{ marginLeft: 6, fontSize: 11, color: 'var(--text-muted)' }}>
                        {expanded ? '▲' : '▼'}
                      </span>
                    )}
                  </div>

                  <div className="step-meta">
                    <span>Tool: <code style={{ fontSize: 11 }}>{step.tool_id}</code></span>
                    {step.trust_score != null && <TrustBadge score={step.trust_score} />}
                    <RiskBar score={step.risk_score} />
                    {step.started_at && <span>{new Date(step.started_at).toLocaleTimeString()}</span>}
                    {step.status === 'executing' && (
                      <span className="text-accent">
                        <span className="spinner" style={{ width: 10, height: 10, marginRight: 4 }} />
                        Running…
                      </span>
                    )}
                  </div>

                  {expanded && (
                    <>
                      <GovernanceChecks checks={step.governance_checks} />
                      {step.result && Object.keys(step.result).length > 0 && (
                        <ResultView result={step.result} />
                      )}
                    </>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function RunDetails() {
  const { runId } = useParams()
  const navigate = useNavigate()
  const [run, setRun] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('steps')
  const [approving, setApproving] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [liveTrust, setLiveTrust] = useState(TOOL_TRUST_SCORES_FE)

  const load = useCallback(async () => {
    try {
      const [data, trust] = await Promise.all([api.getRun(runId), fetchLiveTrustScores()])
      setRun(data)
      if (trust && Object.keys(trust).length > 0) {
        setLiveTrust(Object.fromEntries(Object.entries(trust).map(([k, v]) => [k, v.score])))
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [runId])

  useEffect(() => {
    load()
    const interval = setInterval(() => load(), 1500)
    return () => clearInterval(interval)
  }, [load])

  const approvePlan = async () => {
    setApproving(true)
    try { await api.approvePlan(runId); await load() }
    catch (e) { alert(e.message) }
    finally { setApproving(false) }
  }

  const approveStep = async () => {
    setApproving(true)
    try { await api.approveStep(runId); await load() }
    catch (e) { alert(e.message) }
    finally { setApproving(false) }
  }

  const cancel = async () => {
    if (!confirm('Cancel this run?')) return
    setCancelling(true)
    try { await api.cancelRun(runId); await load() }
    catch (e) { alert(e.message) }
    finally { setCancelling(false) }
  }

  if (loading) {
    return (
      <>
        <div className="topbar"><span className="topbar-title">Loading…</span></div>
        <div className="page" style={{ textAlign: 'center', paddingTop: 80 }}><div className="spinner" /></div>
      </>
    )
  }

  if (!run) {
    return (
      <>
        <div className="topbar"><span className="topbar-title">Not Found</span></div>
        <div className="page">
          <p className="text-muted">Run not found.</p>
          <button className="btn btn-secondary mt-12" onClick={() => navigate('/dashboard')}>← Back</button>
        </div>
      </>
    )
  }

  const isTerminal = ['completed', 'failed', 'cancelled'].includes(run.status)
  const completedCount = run.steps.filter(s => s.status === 'completed').length
  const needsAction = run.status === 'pending_plan_approval' || run.status === 'pending_approval'

  return (
    <>
      <div className="topbar">
        <button className="btn btn-secondary btn-sm" style={{ marginRight: 8 }} onClick={() => navigate('/dashboard')}>
          ← Back
        </button>
        <span className="topbar-title">
          {{ research: '🔬', portfolio: '📊', campaign: '📈', optimizer: '🎯' }[run.agent_type] || '🤖'}{' '}
          {run.agent_type.charAt(0).toUpperCase() + run.agent_type.slice(1)} Agent
        </span>
        <StatusBadge status={run.status} />
        {needsAction && (
          <span style={{ fontSize: 11, color: 'var(--warning)', fontWeight: 600, marginLeft: 8 }}>
            ⚠ Action Required
          </span>
        )}
        <span style={{ flex: 1 }} />
        {!isTerminal && (
          <button className="btn btn-danger btn-sm" onClick={cancel} disabled={cancelling}>
            {cancelling ? 'Cancelling…' : 'Cancel Run'}
          </button>
        )}
      </div>

      <div className="page">
        {/* Run header card */}
        <div className="card mb-16">
          <div className="flex-between">
            <div>
              <div className="card-sub" style={{ marginBottom: 4 }}>{run.run_id}</div>
              <div style={{ fontSize: 15, fontWeight: 500 }}>{run.intent}</div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div className="stat-value" style={{ fontSize: 22 }}>{completedCount}/{run.steps.length}</div>
              <div className="text-muted" style={{ fontSize: 12 }}>steps done</div>
            </div>
          </div>

          {run.steps.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <div className="risk-bar-track" style={{ height: 6, borderRadius: 3 }}>
                <div className="risk-bar-fill" style={{
                  width: `${Math.round((completedCount / run.steps.length) * 100)}%`,
                  background: run.status === 'failed' ? 'var(--danger)' : 'var(--accent)',
                  height: '100%', borderRadius: 3, transition: 'width 0.5s',
                }} />
              </div>
            </div>
          )}
        </div>

        {/* Pipeline stages */}
        <PipelineFlow pipeline={run.pipeline} />

        {/* Result / error banners */}
        {run.status === 'completed' && run.result_summary && (
          <div className="result-box">
            <h3>✓ Run Completed</h3>
            <p>{run.result_summary}</p>
          </div>
        )}

        {run.status === 'failed' && run.error && (
          <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: 'var(--radius)', padding: '16px 20px', marginBottom: 20 }}>
            <div style={{ color: 'var(--danger)', fontWeight: 600, marginBottom: 4 }}>Run Failed</div>
            <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>{run.error}</div>
          </div>
        )}

        {/* Planning spinner */}
        {run.status === 'planning' && (
          <div className="card mb-16" style={{ textAlign: 'center', padding: '40px 20px' }}>
            <div className="spinner" style={{ width: 28, height: 28, borderWidth: 3 }} />
            <div style={{ marginTop: 14, color: 'var(--text-dim)' }}>
              Intent Agent is parsing your goal. Planner is building execution steps…
            </div>
          </div>
        )}

        {/* Plan approval gate */}
        {run.status === 'pending_plan_approval' && run.steps.length > 0 && (
          <PlanReview
            run={run}
            onApprove={approvePlan}
            onCancel={cancel}
            approving={approving}
            cancelling={cancelling}
            liveTrust={liveTrust}
          />
        )}

        {/* Step approval gate — always visible above tabs regardless of active tab */}
        {run.status === 'pending_approval' && (() => {
          const pendingStep = run.steps.find(s => s.status === 'pending_approval')
          return pendingStep ? (
            <div className="approval-banner">
              <div className="icon">⚠️</div>
              <div>
                <h3>Human Approval Required — Step {pendingStep.step_id}</h3>
                <p>
                  <strong>{pendingStep.name}</strong> has risk score{' '}
                  <strong>{Math.round(pendingStep.risk_score * 100)}%</strong> and requires your explicit approval before executing.
                </p>
              </div>
              <div className="approval-actions">
                <button className="btn btn-danger btn-sm" onClick={cancel} disabled={cancelling}>
                  ✕ Reject
                </button>
                <button className="btn btn-success" onClick={approveStep} disabled={approving}>
                  {approving ? <><span className="spinner" /> Approving…</> : '✓ Approve & Continue'}
                </button>
              </div>
            </div>
          ) : null
        })()}

        {/* Tabs: Steps | Audit Trail */}
        {run.status !== 'planning' && run.status !== 'pending_plan_approval' && (
          <>
            <div className="tabs">
              <button className={`tab${activeTab === 'steps' ? ' active' : ''}`} onClick={() => setActiveTab('steps')}>
                Execution Steps {run.steps.length > 0 && `(${completedCount}/${run.steps.length})`}
              </button>
              <button className={`tab${activeTab === 'audit' ? ' active' : ''}`} onClick={() => setActiveTab('audit')}>
                Audit Trail {run.audit_log?.length > 0 && `(${run.audit_log.length})`}
              </button>
            </div>

            {activeTab === 'steps' && (
              <StepsPanel
                run={run}
                onApproveStep={approveStep}
                onCancel={cancel}
                approving={approving}
                cancelling={cancelling}
              />
            )}

            {activeTab === 'audit' && (
              <div className="card">
                <div className="card-header">
                  <div>
                    <div className="card-title">Audit Trail</div>
                    <div className="card-sub">
                      Append-only log. Contains tenant_id, action_type, risk scores, trust scores — never raw content or PII.
                    </div>
                  </div>
                </div>
                <AuditTrail entries={run.audit_log} />
              </div>
            )}
          </>
        )}
      </div>
    </>
  )
}
