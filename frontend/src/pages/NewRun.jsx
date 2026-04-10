import React, { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'

const AGENTS = [
  {
    type: 'sales',
    icon: '🤝',
    title: 'Sales & CRM',
    category: 'Business',
    description: 'Route new leads, update CRM records, notify your sales team on Slack, draft follow-up emails, and schedule calls — all in one governed workflow.',
    tools: ['lead_scorer', 'crm_lookup', 'crm_update', 'slack_notify', 'email_draft', 'schedule_followup'],
    examples: [
      'Route new leads to sales and notify the team',
      'Score and assign inbound leads from the website',
      'Draft follow-up emails for leads from last week\'s demo',
    ],
  },
  {
    type: 'ops',
    icon: '⚙️',
    title: 'Operations',
    category: 'Business',
    description: 'Process invoices, classify and route support tickets, trigger approval workflows for high-value items, and keep your team updated automatically.',
    tools: ['invoice_analyzer', 'ticket_classifier', 'priority_router', 'approval_workflow', 'status_updater', 'notify_team'],
    examples: [
      'Process and route invoices over $10,000 for CFO approval',
      'Classify and assign open support tickets by priority',
      'Route P1 tickets to on-call engineer and notify the team',
    ],
  },
  {
    type: 'campaign',
    icon: '📈',
    title: 'Marketing',
    category: 'Intelligence',
    description: 'Analyze brand search trends, track competitor share of search, surface rising content topics, and monitor news sentiment — using live Google Trends data.',
    tools: ['search_trend_analysis', 'competitor_share_of_search', 'rising_queries', 'news_sentiment', 'content_topics'],
    examples: [
      'Analyze Nike brand performance vs Adidas and Puma',
      'Find rising content topics in our market this quarter',
      'Monitor brand sentiment across Google News',
    ],
  },
  {
    type: 'research',
    icon: '🔬',
    title: 'Research Analyst',
    category: 'Intelligence',
    description: 'Real-time equity research using live Yahoo Finance data. Fundamentals, sentiment analysis, peer comparison, and sector trends.',
    tools: ['stock_lookup', 'news_sentiment', 'peer_comparison', 'sector_analysis'],
    examples: [
      'Analyze NVDA vs AMD vs INTC for Q2 2026',
      'Research AAPL and MSFT — buy or hold?',
      'Semiconductor sector outlook and ETF performance',
    ],
  },
]

export default function NewRun() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [selectedAgent, setSelectedAgent] = useState(searchParams.get('agent') || null)
  const [intent, setIntent] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    const a = searchParams.get('agent')
    if (a) setSelectedAgent(a)
  }, [searchParams])

  const submit = async () => {
    if (!selectedAgent) { setError('Select an agent.'); return }
    if (!intent.trim()) { setError('Describe your goal.'); return }
    setError(null)
    setSubmitting(true)
    try {
      const run = await api.submitRun(selectedAgent, intent.trim())
      navigate(`/runs/${run.run_id}`)
    } catch (e) {
      setError(e.message)
      setSubmitting(false)
    }
  }

  const agent = AGENTS.find(a => a.type === selectedAgent)
  const marketing = AGENTS.filter(a => a.category === 'Marketing')
  const finance = AGENTS.filter(a => a.category === 'Finance')

  return (
    <>
      <div className="topbar">
        <span className="topbar-title">New Run</span>
        <span className="topbar-sub">Select an agent · describe your goal · stay in control</span>
      </div>

      <div className="page" style={{ maxWidth: 820 }}>

        {/* Agent selection */}
        <div className="card mb-16">
          <div className="card-header"><div className="card-title">1 — Choose Agent</div></div>

          <div style={{ marginBottom: 8, fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
            Marketing
          </div>
          <div className="grid-2" style={{ marginBottom: 16 }}>
            {marketing.map(a => (
              <div key={a.type} className={`agent-card${selectedAgent === a.type ? ' selected' : ''}`}
                   onClick={() => setSelectedAgent(a.type)}>
                <div className="agent-icon">{a.icon}</div>
                <h3>{a.title}</h3>
                <p>{a.description}</p>
                <div className="tools-list">{a.tools.map(t => <span key={t} className="tool-chip">{t}</span>)}</div>
              </div>
            ))}
          </div>

          <div style={{ marginBottom: 8, fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
            Finance
          </div>
          <div className="grid-2">
            {finance.map(a => (
              <div key={a.type} className={`agent-card${selectedAgent === a.type ? ' selected' : ''}`}
                   onClick={() => setSelectedAgent(a.type)}>
                <div className="agent-icon">{a.icon}</div>
                <h3>{a.title}</h3>
                <p>{a.description}</p>
                <div className="tools-list">{a.tools.map(t => <span key={t} className="tool-chip">{t}</span>)}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Intent */}
        <div className="card mb-16">
          <div className="card-header"><div className="card-title">2 — Describe Your Goal</div></div>

          {agent && (
            <div style={{ marginBottom: 14 }}>
              <div className="form-label">Example intents for {agent.title}:</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {agent.examples.map(ex => (
                  <button key={ex} className="btn btn-secondary btn-sm"
                          style={{ textAlign: 'left', justifyContent: 'flex-start' }}
                          onClick={() => setIntent(ex)}>
                    {ex}
                  </button>
                ))}
              </div>
              <div className="divider" />
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Intent</label>
            <textarea className="form-textarea"
              placeholder={
                selectedAgent === 'campaign' ? 'e.g. Audit all campaigns and find where we\'re wasting budget…'
                : selectedAgent === 'optimizer' ? 'e.g. Optimize budget allocation to maximize ROAS…'
                : selectedAgent === 'research'  ? 'e.g. Analyze NVDA vs AMD vs INTC for Q2 2026…'
                : selectedAgent === 'portfolio' ? 'e.g. Rebalance to 70/20/10 allocation…'
                : 'Describe what you want the agent to do…'
              }
              value={intent}
              onChange={e => setIntent(e.target.value)}
              rows={4}
            />
          </div>

          {error && <div style={{ color: 'var(--danger)', fontSize: 13, marginBottom: 12 }}>⚠ {error}</div>}

          <button className="btn btn-primary" onClick={submit}
                  disabled={submitting || !selectedAgent || !intent.trim()}>
            {submitting ? <><span className="spinner" /> Launching…</> : '▶ Launch Agent'}
          </button>
        </div>

        <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.7 }}>
          The AI generates a governed execution plan. You review and approve it before anything runs.
          High-risk steps pause again mid-execution for a second approval.
          Every action is logged to an append-only audit trail.
        </div>
      </div>
    </>
  )
}
