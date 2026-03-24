# Aura — AI Marketing Automation Platform Demo

Client demo showcasing the core Aura value proposition: AI agents that plan, govern, and execute across your marketing and finance tools — with humans in control of every critical decision.

---

## Quick Start

### 1. Backend
```bash
cd demo/backend
pip3 install -r requirements.txt
python3 -m uvicorn main:app --reload --port 8000
```

### 2. Frontend (separate terminal)
```bash
cd demo/frontend
npm install
npm run dev
```

Open **http://localhost:3000** and sign in with `demo@aura.ai` / `demo`

---

## Login

| Field | Value |
|---|---|
| Email | `demo@aura.ai` |
| Password | `demo` |

All API routes are protected. Sessions are in-memory (reset on server restart). Override the password via `DEMO_PASSWORD` env var.

---

## The Demo Story

Most AI automation tools fall into one of two failure modes:

- **Too autonomous** — agents that execute without oversight, approval trails, or rollback. Enterprises in regulated industries cannot deploy these.
- **Too manual** — tools requiring human input at every step, defeating the purpose of automation.

Aura sits between these extremes. The demo shows exactly how: AI does the heavy lifting, but humans remain in control of everything that matters.

### Governed Execution Flow

Every run goes through this sequence — nothing is skipped:

```
Intent → Planner → PLAN APPROVAL GATE → Action Wrapper (5 checks) → Tool → Evaluator → next step
                                ↑                    ↑
                         Human reviews          Governor blocks
                         full plan first        if trust score critical
```

---

## What the Demo Shows

### 1. Plan Review Gate
Before any action is taken, the AI generates a complete execution plan and pauses. You see every step with its risk score and tool trust score. **Nothing executes until you click Approve.**

This answers the enterprise question: *"How do I know what the AI is going to do before it does it?"*

### 2. Action Wrapper — 5 Governance Checks
Every tool call passes through 5 checks in order before executing:

| Check | What it enforces |
|---|---|
| Session Auth | Valid session token |
| RBAC | Role has permission for this tool |
| Rate Limit | Live per-session request counter |
| Trust Score | Tool reliability ≥ 0.70 — blocks immediately if critical |
| Audit Log | Invocation metadata written before forwarding |

Expand any completed step in the UI to see all 5 checks with their results.

### 3. Mid-Run Approval Gates
High-risk steps (risk score > 0.69) pause execution and require a second human approval before proceeding. The run holds its state indefinitely until you approve or cancel — no timeout, no auto-proceed.

### 4. Audit Trail
Every governance event is logged in real time:
- `intent_received` → `plan_generated` → `plan_approved`
- `step_started` → `step_completed` (with trust score + evaluator verdict)
- `approval_requested` → `approval_granted`

The audit tab shows action type, tool, risk %, trust %, and reason code. It never contains raw content or PII — enforced at schema level.

### 5. Trust Score Registry (live — not hardcoded)
Each tool has a reliability score (0.0–1.0) that starts from observed seed values and updates **live** after every tool execution using an Exponential Moving Average (α=0.15):

```
new_score = 0.85 × old_score + 0.15 × (0.7 × success_rate + 0.3 × (1 − error_rate))
```

The **Trust Registry** page shows every tool's live score, invocation count, success rate, and average latency — updating in real time. A score below 0.70 triggers an immediate block in the Action Wrapper.

### 6. Integrations
The **Integrations** page shows all connected tools: Google Ads, Meta Ads, Google Analytics, HubSpot (connected by default), plus LinkedIn Ads, Mailchimp, Salesforce, and Slack (togglable). The Dashboard governance panel shows a live connected tool count.

### 7. Run Persistence
Completed runs survive server restarts. Run history is saved to `runs_store.json` on every state transition and reloaded on startup. Mid-execution runs interrupted by a restart are marked failed with a clear reason.

---

## Agents

### 📈 Campaign Analyst
Full-funnel brand analysis using live Google Trends and Google News data.

| Tool | What it does |
|---|---|
| `search_trend_analysis` | Real Google Trends interest over time |
| `competitor_share_of_search` | Share of search vs competitors |
| `regional_interest` | Geographic breakdown of search interest |
| `rising_queries` | Rising search queries from Google Trends |
| `news_sentiment` | Real headline sentiment via Google News RSS + NLP |
| `content_topics` | Rising content topics from Google Trends |

**Try:** *"Analyze Nike brand performance vs Adidas and Puma"*

### 🎯 Ad Optimizer
AI-driven budget reallocation and campaign optimization. Publishing changes requires approval.

| Tool | What it does |
|---|---|
| `keyword_opportunities` | Rising keyword opportunities from Google Trends |
| `budget_optimizer` | Budget reallocation model |
| `ab_test_analyzer` | A/B test statistical significance |
| `publish_campaign` | Publish changes to ad platforms [HIGH RISK — requires approval] |

**Try:** *"Optimize budget allocation to maximize ROAS"*

### 🔬 Research Analyst
Real-time equity research using live Yahoo Finance data.

| Tool | What it does |
|---|---|
| `stock_lookup` | Live price, P/E, market cap, analyst target |
| `news_sentiment` | NLP sentiment on real Yahoo Finance headlines (TextBlob) |
| `peer_comparison` | Side-by-side multi-symbol comparison |
| `sector_analysis` | ETF-based sector performance — YTD, 1Y return, volatility |

**Try:** *"Analyze NVDA vs AMD vs INTC for Q2 2026"*

### 📊 Portfolio Manager
Portfolio risk analysis and governed rebalancing. High-risk trades require mid-run approval.

| Tool | What it does |
|---|---|
| `get_portfolio` | Demo paper portfolio with live current prices |
| `risk_assessment` | Beta, Sharpe ratio, VaR 95%, max drawdown from 1yr price history |
| `calculate_rebalance` | Optimal trade list to reach target allocation |
| `execute_trade` | Paper trade executed at real current market price |

**Try:** *"Rebalance to 70/20/10 equity/bonds/alternatives"*

---

## Configuration

All thresholds are env-overridable — no hardcoded values in logic:

| Env Var | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | Groq API key for LLM intent parsing + planning |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Groq model to use |
| `DEMO_PASSWORD` | `demo` | Login password for `demo@aura.ai` |
| `ALLOWED_ORIGINS` | `http://localhost:3000,...` | CORS allowed origins (comma-separated) |
| `VITE_BACKEND_URL` | `http://localhost:8000` | Backend URL for Vite proxy |
| `VITE_PORT` | `3000` | Frontend dev server port |
| `EMA_ALPHA` | `0.15` | Trust score EMA weight (production: 0.10) |
| `TRUST_HEALTHY` | `0.85` | Trust score threshold for healthy status |
| `TRUST_DEGRADED_MIN` | `0.70` | Trust score threshold for degraded status |
| `RISK_MEDIUM_MAX` | `0.69` | Risk score threshold for requiring approval |

---

## Architecture

```
Layer 2  →  LangGraph Agent Layer  (Intent Agent → Planner → Governor → Executor)
Layer 3  →  Governance Engine      (Evaluator + Governor + Trust Registry)
Layer 4  →  Tool Invocation Stack  (Action Wrapper → MCP Gateway → MCP Server)
Layer 5  →  Storage                (Postgres+RLS / S3 / Qdrant / Audit Logs)
Layer 6  →  Workflow Engine        (Temporal — durable checkpoint resume)
```

The demo runs Layer 2–4 in a self-contained FastAPI process. Layer 5–6 are the production infrastructure (not required to run the demo).

---

## Data Sources

- Market prices and fundamentals: **Yahoo Finance via yfinance** (no API key required)
- News sentiment: **TextBlob NLP** on real Yahoo Finance headlines
- Search trends: **Google Trends via pytrends** (no API key required)
- Brand news: **Google News RSS via feedparser** (no API key required)
- Risk calculations: **numpy** on 1-year historical price data (beta vs SPY, Sharpe, VaR, max drawdown)
- Portfolio: fixed paper holdings, all analytics and prices are live
- Trades: paper execution (simulated) at real current market prices
