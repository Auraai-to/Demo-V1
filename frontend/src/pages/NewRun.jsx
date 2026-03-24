import React, { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'

const AGENTS = [
  {
    type: 'campaign',
    icon: '📈',
    title: 'Campaign Analyst',
    category: 'Marketing',
    description: 'Full-funnel campaign audit across Google, Meta, LinkedIn and email. Surfaces ROAS gaps, creative fatigue, and channel efficiency.',
    tools: ['campaign_analytics', 'audience_insights', 'ad_performance', 'competitor_analysis', 'channel_comparison'],
    examples: [
      'Audit all campaigns and find where we\'re wasting budget',
      'Analyze Q1 performance vs competitors',
      'Full channel efficiency breakdown with content insights',
    ],
  },
  {
    type: 'optimizer',
    icon: '🎯',
    title: 'Ad Optimizer',
    category: 'Marketing',
    description: 'AI-driven budget reallocation and campaign optimization. Finds keyword waste, A/B test winners, and publishes changes with your approval.',
    tools: ['budget_optimizer', 'keyword_analysis', 'ab_test_analyzer', 'publish_campaign'],
    examples: [
      'Optimize budget allocation to maximize ROAS',
      'Find keyword waste and ship A/B test winner',
      'Rebalance spend — move budget from Meta to email and search',
    ],
  },
  {
    type: 'research',
    icon: '🔬',
    title: 'Research Analyst',
    category: 'Finance',
    description: 'Real-time equity research using live Yahoo Finance data. Fundamentals, sentiment, peer comparison, sector trends.',
    tools: ['stock_lookup', 'news_sentiment', 'peer_comparison', 'sector_analysis'],
    examples: [
      'Analyze NVDA vs AMD vs INTC for Q2 2026',
      'Research AAPL and MSFT — buy or hold?',
    ],
  },
  {
    type: 'portfolio',
    icon: '📊',
    title: 'Portfolio Manager',
    category: 'Finance',
    description: 'Portfolio risk analysis and governed rebalancing. High-risk trades pause for your approval before executing.',
    tools: ['get_portfolio', 'risk_assessment', 'calculate_rebalance', 'execute_trade'],
    examples: [
      'Rebalance to 70/20/10 equity/bonds/alternatives',
      'Assess risk and reduce AAPL concentration',
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
