"""
Aura — Your AI Workflow Automation Platform
Demo Backend v0.4

Business Workflow Agents:
  1. Sales & CRM      — lead_scorer, crm_lookup, crm_update, slack_notify, email_draft, schedule_followup
  2. Operations       — invoice_analyzer, ticket_classifier, priority_router, approval_workflow, status_updater, notify_team

Intelligence Agents:
  3. Marketing        — search_trend_analysis, competitor_share_of_search, rising_queries, news_sentiment, content_topics
  4. Research Analyst — stock_lookup, news_sentiment, peer_comparison, sector_analysis (live Yahoo Finance)

Governance flow with 4 visible pipeline stages:
  [Intent Agent] → [Tool Router] → [Plan Builder] → [Workflow Engine]
  Each stage is tracked and surfaced in the UI.
  Execution pauses at Plan Approval gate and at high-risk step gates.
"""

import asyncio
import json
import os
import pathlib
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from dotenv import load_dotenv
load_dotenv()

from tools import TOOL_REGISTRY, call_tool
from marketing_tools import MARKETING_TOOL_REGISTRY, call_marketing_tool
from business_tools import BUSINESS_TOOL_REGISTRY, call_business_tool
from llm import (
    llm_available, parse_intent, build_plan, get_tools_for_agent,
)

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

structlog.configure(processors=[structlog.dev.ConsoleRenderer()])
log = structlog.get_logger()

app = FastAPI(title="Aura Demo", version="0.2.0")
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory run store
RUNS: Dict[str, "RunRecord"] = {}

# Run persistence
_RUNS_STORE_PATH = pathlib.Path(os.environ.get("RUNS_STORE_PATH", str(pathlib.Path(__file__).parent / "runs_store.json")))

# ---------------------------------------------------------------------------
# Auth — disabled for demo, all routes public
# ---------------------------------------------------------------------------

_DEMO_USER = {
    "user_id": "user_demo_001",
    "email":   "demo@aura.ai",
    "name":    "Demo User",
}

def _get_current_user() -> Dict:
    return _DEMO_USER

# ---------------------------------------------------------------------------
# Integrations — in-memory list, togglable for demo
# ---------------------------------------------------------------------------

_INTEGRATIONS: List[Dict] = [
    {"id": "slack",            "name": "Slack",            "category": "Messaging",      "connected": True},
    {"id": "hubspot",          "name": "HubSpot",          "category": "CRM",            "connected": True},
    {"id": "gmail",            "name": "Gmail",            "category": "Email",          "connected": True},
    {"id": "stripe",           "name": "Stripe",           "category": "Payments",       "connected": True},
    {"id": "openai",           "name": "OpenAI",           "category": "AI Models",      "connected": True},
    {"id": "claude",           "name": "Claude",           "category": "AI Models",      "connected": True},
    {"id": "salesforce",       "name": "Salesforce",       "category": "CRM",            "connected": False},
    {"id": "notion",           "name": "Notion",           "category": "Productivity",   "connected": False},
    {"id": "jira",             "name": "Jira",             "category": "Project Mgmt",   "connected": False},
    {"id": "zapier",           "name": "Zapier",           "category": "Automation",     "connected": False},
    {"id": "mailchimp",        "name": "Mailchimp",        "category": "Email",          "connected": False},
    {"id": "google_analytics", "name": "Google Analytics", "category": "Analytics",      "connected": False},
]

# ---------------------------------------------------------------------------
# Trust score registry  (EMA-updated after every execution — mirrors production)
# ---------------------------------------------------------------------------

# Seed values — represent prior observed reliability before this session
_TRUST_SEED: Dict[str, float] = {
    # Research tools (live Yahoo Finance + NLP)
    "stock_lookup":        0.94,
    "news_sentiment":      0.89,
    "peer_comparison":     0.91,
    "sector_analysis":     0.87,
    # Marketing tools (live Google Trends + Google News RSS)
    "search_trend_analysis":      0.93,
    "competitor_share_of_search": 0.92,
    "regional_interest":          0.91,
    "rising_queries":             0.90,
    "content_topics":             0.91,
    "keyword_opportunities":      0.90,
    "budget_optimizer":           0.88,
    "ab_test_analyzer":           0.87,
    "publish_campaign":           0.84,
    # Sales & CRM tools
    "lead_scorer":       0.95,
    "crm_lookup":        0.97,
    "crm_update":        0.93,
    "slack_notify":      0.98,
    "email_draft":       0.91,
    "schedule_followup": 0.96,
    # Operations tools
    "invoice_analyzer":  0.94,
    "ticket_classifier": 0.92,
    "priority_router":   0.95,
    "approval_workflow": 0.88,
    "status_updater":    0.96,
    "notify_team":       0.97,
}

# Live trust state — mutated after every tool invocation
_TRUST_STATE: Dict[str, Dict] = {
    tool: {
        "score":           seed,
        "invocations":     0,
        "successes":       0,
        "errors":          0,
        "total_latency_ms": 0.0,
        "last_updated":    datetime.now(timezone.utc).isoformat(),
    }
    for tool, seed in _TRUST_SEED.items()
}

# ---------------------------------------------------------------------------
# Governance thresholds  (env-overridable — never hardcoded in logic below)
# ---------------------------------------------------------------------------

GOVERNANCE_THRESHOLDS = {
    "trust_score": {
        "healthy":      float(os.getenv("TRUST_HEALTHY",      "0.85")),
        "degraded_min": float(os.getenv("TRUST_DEGRADED_MIN", "0.70")),
        "critical_max": float(os.getenv("TRUST_CRITICAL_MAX", "0.70")),
    },
    "risk_score": {
        "low_max":      float(os.getenv("RISK_LOW_MAX",      "0.39")),
        "medium_max":   float(os.getenv("RISK_MEDIUM_MAX",   "0.69")),
        "high_max":     float(os.getenv("RISK_HIGH_MAX",     "0.84")),
        "critical_min": float(os.getenv("RISK_CRITICAL_MIN", "0.85")),
    },
}

_EMA_ALPHA = float(os.getenv("EMA_ALPHA", "0.15"))  # production default: 0.10

def _trust_status(score: float) -> str:
    if score >= GOVERNANCE_THRESHOLDS["trust_score"]["healthy"]:      return "healthy"
    if score >= GOVERNANCE_THRESHOLDS["trust_score"]["degraded_min"]: return "degraded"
    return "critical"

def _get_trust(tool_id: str) -> float:
    return _TRUST_STATE.get(tool_id, {}).get("score", GOVERNANCE_THRESHOLDS["trust_score"]["healthy"])

def _update_trust(tool_id: str, success: bool, latency_ms: float) -> None:
    """EMA update: score = 0.7 * success_rate + 0.3 * (1 - error_rate)"""
    if tool_id not in _TRUST_STATE:
        _TRUST_STATE[tool_id] = {
            "score": GOVERNANCE_THRESHOLDS["trust_score"]["healthy"], "invocations": 0, "successes": 0,
            "errors": 0, "total_latency_ms": 0.0,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    s = _TRUST_STATE[tool_id]
    s["invocations"] += 1
    s["total_latency_ms"] += latency_ms
    if success:
        s["successes"] += 1
    else:
        s["errors"] += 1

    n = s["invocations"]
    success_rate = s["successes"] / n
    error_rate   = s["errors"]    / n
    new_obs = 0.7 * success_rate + 0.3 * (1.0 - error_rate)

    # EMA: blend new observation into running score
    s["score"] = round((1 - _EMA_ALPHA) * s["score"] + _EMA_ALPHA * new_obs, 4)
    s["last_updated"] = datetime.now(timezone.utc).isoformat()

    log.info("trust_score_updated", tool_id=tool_id,
             score=s["score"], invocations=n, success=success)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class PipelineStage(BaseModel):
    name: str          # intent_agent | tool_router | plan_builder | workflow_engine
    label: str         # display label
    status: str = "pending"   # pending | active | completed
    detail: Optional[str] = None
    completed_at: Optional[str] = None


class GovernanceCheck(BaseModel):
    name: str
    status: str       # pass | fail | running
    value: Optional[str] = None


class AuditEntry(BaseModel):
    event_id: str
    timestamp: str
    action_type: str
    step_id: Optional[str] = None
    tool_id: Optional[str] = None
    risk_score: Optional[float] = None
    trust_score: Optional[float] = None
    status: str
    reason_code: Optional[str] = None


class StepRecord(BaseModel):
    step_id: str
    name: str
    tool_id: str
    description: Optional[str] = None   # plain-English: what this step does and why
    args: Dict[str, Any] = {}
    risk_score: float
    trust_score: Optional[float] = None
    requires_approval: bool = False
    status: str = "not_started"   # not_started | executing | pending_approval | completed | failed
    governance_checks: List[GovernanceCheck] = []
    result: Optional[Dict[str, Any]] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


def _default_pipeline() -> List[PipelineStage]:
    return [
        PipelineStage(name="intent_agent",    label="Intent Agent",    status="pending"),
        PipelineStage(name="tool_router",     label="Tool Router",     status="pending"),
        PipelineStage(name="plan_builder",    label="Plan Builder",    status="pending"),
        PipelineStage(name="workflow_engine", label="Workflow Engine", status="pending"),
    ]


class RunRecord(BaseModel):
    run_id: str
    agent_type: str
    intent: str
    intent_data: Dict[str, Any] = {}    # structured intent parsed by LLM
    status: str = "planning"   # planning | pending_plan_approval | executing | pending_approval | completed | failed | cancelled
    pipeline: List[PipelineStage] = []
    steps: List[StepRecord] = []
    audit_log: List[AuditEntry] = []
    created_at: str
    completed_at: Optional[str] = None
    result_summary: Optional[str] = None
    error: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


# Runtime gates — keyed by run_id
_plan_approval_events: Dict[str, asyncio.Event] = {}
_approval_events: Dict[str, asyncio.Event] = {}
_cancel_flags: Dict[str, bool] = {}


# ---------------------------------------------------------------------------
# Audit log helper
# ---------------------------------------------------------------------------

def _add_audit(
    run: RunRecord,
    action_type: str,
    status: str,
    step_id: Optional[str] = None,
    tool_id: Optional[str] = None,
    risk_score: Optional[float] = None,
    trust_score: Optional[float] = None,
    reason_code: Optional[str] = None,
) -> None:
    entry = AuditEntry(
        event_id=f"evt_{uuid.uuid4().hex[:10]}",
        timestamp=datetime.now(timezone.utc).isoformat(),
        action_type=action_type,
        step_id=step_id,
        tool_id=tool_id,
        risk_score=risk_score,
        trust_score=trust_score,
        status=status,
        reason_code=reason_code,
    )
    run.audit_log.append(entry)
    log.info(
        action_type,
        run_id=run.run_id,
        step_id=step_id,
        tool_id=tool_id,
        status=status,
    )


# ---------------------------------------------------------------------------
# Run persistence — Upstash Redis (if configured) with file fallback
# ---------------------------------------------------------------------------

_UPSTASH_URL   = os.getenv("UPSTASH_REDIS_REST_URL", "")
_UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
_REDIS_KEY     = "aura_demo_runs"


def _redis_save(data: dict) -> bool:
    if not _UPSTASH_URL or not _UPSTASH_TOKEN:
        return False
    try:
        import requests as _req
        payload = json.dumps(data, default=str)
        resp = _req.post(
            f"{_UPSTASH_URL}/set/{_REDIS_KEY}",
            headers={"Authorization": f"Bearer {_UPSTASH_TOKEN}"},
            json=payload,
            timeout=5,
        )
        return resp.status_code == 200
    except Exception as exc:
        log.warning("redis_save_failed", error=str(exc))
        return False


def _redis_load() -> dict:
    if not _UPSTASH_URL or not _UPSTASH_TOKEN:
        return {}
    try:
        import requests as _req
        resp = _req.get(
            f"{_UPSTASH_URL}/get/{_REDIS_KEY}",
            headers={"Authorization": f"Bearer {_UPSTASH_TOKEN}"},
            timeout=5,
        )
        if resp.status_code != 200:
            return {}
        result = resp.json().get("result")
        if not result:
            return {}
        return json.loads(result)
    except Exception as exc:
        log.warning("redis_load_failed", error=str(exc))
        return {}


async def _save_runs() -> None:
    """Persist RUNS to Redis (primary) and file (fallback)."""
    try:
        data = {run_id: run.model_dump() for run_id, run in RUNS.items()}
        loop = asyncio.get_event_loop()
        saved = await loop.run_in_executor(None, lambda: _redis_save(data))
        if not saved:
            await loop.run_in_executor(
                None,
                lambda: _RUNS_STORE_PATH.write_text(
                    json.dumps(data, default=str), encoding="utf-8"
                ),
            )
    except Exception as exc:
        log.warning("runs_store_write_failed", error=str(exc))

# ---------------------------------------------------------------------------
# Runtime arg resolution
# ---------------------------------------------------------------------------

_PLACEHOLDER_PATTERNS = (
    "calculated", "from step", "see step", "use result", "determined by",
    "output of", "result of", "@", "step s", "previous step",
)

def _is_placeholder(value: Any) -> bool:
    """Return True if a step arg value is an LLM-generated placeholder rather than a real value."""
    if not isinstance(value, str):
        return False
    low = value.lower()
    return any(p in low for p in _PLACEHOLDER_PATTERNS)

def _resolve_args(step: "StepRecord", completed_steps: List["StepRecord"]) -> Dict[str, Any]:
    """
    Substitute placeholder arg values with real data from completed upstream steps.
    Currently handles execute_trade: pulls the first trade from calculate_rebalance output.
    Returns a new args dict (does not mutate step.args).
    """
    if step.tool_id != "execute_trade":
        return step.args

    # Only resolve if any arg looks like a placeholder
    if not any(_is_placeholder(v) for v in step.args.values()):
        return step.args

    # Find the most recent completed calculate_rebalance step
    rebalance = next(
        (s for s in reversed(completed_steps)
         if s.tool_id == "calculate_rebalance" and s.result and not s.result.get("error")),
        None,
    )
    if not rebalance:
        log.warning("arg_resolution_failed", step_id=step.step_id,
                    reason="no completed calculate_rebalance step found")
        return step.args

    trades = rebalance.result.get("trades_required", [])
    if not trades:
        log.warning("arg_resolution_failed", step_id=step.step_id,
                    reason="calculate_rebalance returned no trades")
        return step.args

    # Execute the first trade (highest-priority trade from the rebalance plan)
    trade = trades[0]
    resolved = {
        "symbol": trade.get("symbol", ""),
        "action":  trade.get("action",  ""),
        "shares":  trade.get("shares",  0),
        "amount":  trade.get("estimated_value", 0),
    }
    log.info("args_resolved_from_upstream", step_id=step.step_id,
             tool_id=step.tool_id, resolved=resolved)
    return resolved


# ---------------------------------------------------------------------------
# Action Wrapper simulation (5 checks)
# ---------------------------------------------------------------------------

async def _run_action_wrapper_checks(step: StepRecord) -> bool:
    """
    Simulates the 5 Action Wrapper checks in order.
    Returns True if all pass, False if any fail.
    Updates step.governance_checks in place.
    Trust score is read live from _TRUST_STATE (EMA-updated each execution).
    """
    trust = _get_trust(step.tool_id)
    step.trust_score = trust

    session_invocations = sum(s["invocations"] for s in _TRUST_STATE.values())
    checks_config = [
        ("Session Auth",  True,                      "session_valid"),
        ("RBAC Check",    True,                      "role=analyst:read+write"),
        ("Rate Limit",    True,                      f"{session_invocations}/100 req/min"),
        ("Trust Score",   trust >= GOVERNANCE_THRESHOLDS["trust_score"]["critical_max"],
                                                     f"{trust:.2f} ({_trust_status(trust)})"),
        ("Audit Log",     True,                      "written → append-only store"),
    ]

    step.governance_checks = []
    for name, passing, value in checks_config:
        await asyncio.sleep(0.25)  # stagger so frontend polls catch them
        step.governance_checks.append(GovernanceCheck(
            name=name,
            status="pass" if passing else "fail",
            value=value,
        ))
        if not passing:
            return False

    return True


# ---------------------------------------------------------------------------
# Plan generation
# ---------------------------------------------------------------------------

def _extract_symbols(text: str) -> List[str]:
    known = ["NVDA", "AMD", "INTC", "AAPL", "MSFT", "GOOGL", "META", "SPY", "AGG", "ARKK", "JPM", "JNJ"]
    found = []
    upper = text.upper()
    for sym in known:
        if sym in upper:
            found.append(sym)
    for m in re.findall(r'\b([A-Z]{2,5})\b', upper):
        if m not in found and m not in {"AI", "ETF", "US", "USD", "SP", "YOY", "PE", "EPS", "QQ"}:
            found.append(m)
    return found[:3]


def _generate_research_plan(intent: str) -> List[StepRecord]:
    symbols = _extract_symbols(intent) or ["NVDA"]
    steps = []

    for sym in symbols:
        steps.append(StepRecord(
            step_id=f"s{len(steps)+1}",
            name=f"Fetch {sym} price & fundamentals",
            tool_id="stock_lookup",
            args={"symbol": sym},
            risk_score=0.12,
        ))

    steps.append(StepRecord(
        step_id=f"s{len(steps)+1}",
        name=f"Analyze {symbols[0]} news & market sentiment",
        tool_id="news_sentiment",
        args={"symbol": symbols[0]},
        risk_score=0.15,
    ))

    if len(symbols) >= 2:
        steps.append(StepRecord(
            step_id=f"s{len(steps)+1}",
            name=f"Compare {' vs '.join(symbols)} on key metrics",
            tool_id="peer_comparison",
            args={"symbol": symbols[0], "peers": symbols[1:]},
            risk_score=0.18,
        ))

    sector = "semiconductors" if any(s in ("NVDA", "AMD", "INTC") for s in symbols) else "technology"
    steps.append(StepRecord(
        step_id=f"s{len(steps)+1}",
        name=f"{'Semiconductor' if sector == 'semiconductors' else 'Technology'} sector outlook 2026",
        tool_id="sector_analysis",
        args={"sector": sector},
        risk_score=0.20,
    ))

    return steps


def _generate_portfolio_plan(intent: str) -> List[StepRecord]:
    is_rebalance = any(w in intent.lower() for w in ["rebalance", "rebalancing", "allocation", "weight", "target"])
    target = {"equity": 70, "fixed_income": 20, "alternatives": 10}
    eq_match = re.search(r'(\d+)%?\s*(?:equity|stock)', intent.lower())
    if eq_match:
        eq = int(eq_match.group(1))
        target = {"equity": eq, "fixed_income": max(5, 90 - eq - 10), "alternatives": min(15, 100 - eq - max(5, 90 - eq - 10))}

    steps = [
        StepRecord(step_id="s1", name="Fetch current portfolio holdings",
                   tool_id="get_portfolio", args={}, risk_score=0.08),
        StepRecord(step_id="s2", name="Assess current portfolio risk & concentration",
                   tool_id="risk_assessment", args={}, risk_score=0.15),
        StepRecord(step_id="s3", name=f"Calculate {'rebalancing' if is_rebalance else 'optimization'} trades",
                   tool_id="calculate_rebalance", args={"target_allocation": target}, risk_score=0.28),
    ]

    if is_rebalance:
        steps += [
            StepRecord(step_id="s4", name="Sell 12% AAPL position ($30,148) — reduce concentration",
                       tool_id="execute_trade",
                       args={"symbol": "AAPL", "action": "sell", "shares": 155, "amount": 30148},
                       risk_score=0.78, requires_approval=True),
            StepRecord(step_id="s5", name="Buy SPY ETF — $30,139 broad equity exposure",
                       tool_id="execute_trade",
                       args={"symbol": "SPY", "action": "buy", "shares": 56, "amount": 30139},
                       risk_score=0.62),
            StepRecord(step_id="s6", name="Buy AGG Bond ETF — $28,044 fixed income allocation",
                       tool_id="execute_trade",
                       args={"symbol": "AGG", "action": "buy", "shares": 285, "amount": 28044},
                       risk_score=0.58),
            StepRecord(step_id="s7", name="Buy ARKK — $28,142 alternatives sleeve",
                       tool_id="execute_trade",
                       args={"symbol": "ARKK", "action": "buy", "shares": 533, "amount": 28142},
                       risk_score=0.71),
        ]

    return steps


def _generate_result_summary(run: RunRecord) -> str:
    if run.agent_type == "research":
        symbols_analyzed, recommendations = [], []
        for step in run.steps:
            if step.tool_id == "stock_lookup" and step.result:
                sym = step.result.get("symbol", "")
                rec = step.result.get("recommendation", "")
                target = step.result.get("analyst_target", 0)
                if sym:
                    symbols_analyzed.append(sym)
                    recommendations.append(f"{sym}: {rec} (target ${target})")
        sector_result = next((s.result for s in run.steps if s.tool_id == "sector_analysis" and s.result), {})
        sector_outlook = sector_result.get("outlook", "NEUTRAL")
        sector_name = sector_result.get("sector", "Technology")
        symbols_str = " / ".join(symbols_analyzed) if symbols_analyzed else "analyzed securities"
        recs_str = " | ".join(recommendations) if recommendations else "See individual step results"
        return (
            f"Research complete for {symbols_str}. "
            f"Sector outlook: {sector_name} — {sector_outlook}. "
            f"Analyst recommendations: {recs_str}. "
            f"Full analysis including peer comparison and sentiment data available in step results."
        )

    elif run.agent_type == "portfolio":
        portfolio_result  = next((s.result for s in run.steps if s.tool_id == "get_portfolio"        and s.result), {})
        risk_result       = next((s.result for s in run.steps if s.tool_id == "risk_assessment"      and s.result), {})
        rebalance_result  = next((s.result for s in run.steps if s.tool_id == "calculate_rebalance"  and s.result), {})
        total_value   = rebalance_result.get("portfolio_value") or portfolio_result.get("total_value", 0)
        trade_count   = rebalance_result.get("trade_count", len(rebalance_result.get("trades_required", [])))
        target        = rebalance_result.get("target_allocation", {})
        old_beta      = risk_result.get("portfolio_beta")
        conc_risks    = risk_result.get("concentration_risks", [])
        parts = [f"Portfolio rebalancing completed. {trade_count} trades across ${total_value:,.0f} portfolio."]
        if conc_risks:
            parts.append(conc_risks[0]["detail"] + ".")
        if target:
            eq, fi, alt = target.get("equity","?"), target.get("fixed_income","?"), target.get("alternatives","?")
            parts.append(f"Portfolio aligned to {eq}/{fi}/{alt} equity/bonds/alternatives target.")
        if old_beta is not None:
            parts.append(f"Pre-rebalance portfolio beta: {old_beta}.")
        return " ".join(parts)

    elif run.agent_type == "campaign":
        trends = next((s.result for s in run.steps if s.tool_id == "search_trend_analysis" and s.result), {})
        sov    = next((s.result for s in run.steps if s.tool_id == "competitor_share_of_search" and s.result), {})
        news   = next((s.result for s in run.steps if s.tool_id == "news_sentiment" and s.result), {})
        brand_score = trends.get("brand_score", "N/A")
        leader      = trends.get("leader", "N/A")
        sov_pct     = sov.get("brand_sov", "N/A")
        sentiment   = news.get("overall_sentiment", "neutral")
        insight     = trends.get("insight", "")
        return (
            f"Campaign analysis complete using live Google Trends + Google News data. "
            f"Search interest score: {brand_score}/100. "
            f"{insight} "
            f"Share of search: {sov_pct}%. "
            f"Brand news sentiment: {sentiment}. "
            f"Full regional breakdown and rising content opportunities available in step results."
        )

    elif run.agent_type == "optimizer":
        keywords = next((s.result for s in run.steps if s.tool_id == "keyword_opportunities" and s.result), {})
        budget   = next((s.result for s in run.steps if s.tool_id == "budget_optimizer" and s.result), {})
        publish  = next((s.result for s in run.steps if s.tool_id == "publish_campaign" and s.result), {})
        opp_count = keywords.get("count", 0)
        projected = budget.get("projected_roas_improvement", "+0.6x blended ROAS")
        convs     = budget.get("projected_additional_conversions", "+142/month")
        pub_status = publish.get("status", "published_to_sandbox")
        audit_ref  = publish.get("audit_ref", "AURA-PUB-XXXXX")
        return (
            f"Optimization complete. {opp_count} real rising keyword opportunities identified via Google Trends. "
            f"Budget reallocation {pub_status}. "
            f"Projected: {projected}, {convs} additional conversions. "
            f"Rollback available — audit ref {audit_ref}."
        )

    elif run.agent_type == "sales":
        crm   = next((s.result for s in run.steps if s.tool_id == "crm_update" and s.result), {})
        lead  = next((s.result for s in run.steps if s.tool_id == "lead_scorer" and s.result), {})
        slack = next((s.result for s in run.steps if s.tool_id == "slack_notify" and s.result), {})
        score = lead.get("lead_score", "N/A")
        tier  = lead.get("tier", "B")
        owner = crm.get("owner_assigned", "Sales Rep")
        chan  = slack.get("channel", "#sales-leads")
        return (
            f"Lead successfully routed. Score: {score}/100 (Tier {tier}). "
            f"CRM updated — assigned to {owner}. "
            f"Team notified via {chan}. Follow-up call scheduled in 48h. "
            f"Full lead profile, drafted email, and audit trail available in step results."
        )

    elif run.agent_type == "ops":
        invoice  = next((s.result for s in run.steps if s.tool_id == "invoice_analyzer" and s.result), {})
        ticket   = next((s.result for s in run.steps if s.tool_id == "ticket_classifier" and s.result), {})
        approval = next((s.result for s in run.steps if s.tool_id == "approval_workflow" and s.result), {})
        if invoice:
            amount = invoice.get("amount", "N/A")
            vendor = invoice.get("vendor", "Vendor")
            appr   = approval.get("approver", "CFO")
            wf_id  = approval.get("workflow_id", "APPR-XXXX")
            return (
                f"Invoice processed. ${amount:,} from {vendor} flagged and routed for {appr} approval. "
                f"Approval workflow {wf_id} triggered — deadline 48h. "
                f"Finance team notified via Slack. Full audit trail in step results."
            )
        elif ticket:
            priority  = ticket.get("priority", "P2")
            category  = ticket.get("category", "General")
            wf_id     = approval.get("workflow_id", "APPR-XXXX")
            return (
                f"Ticket classified as {priority} — {category}. "
                f"Routed to on-call engineer with SLA tracking active. "
                f"Escalation workflow {wf_id} triggered. Team notified. "
                f"Full classification report and routing details in step results."
            )

    return "Run completed successfully."


# ---------------------------------------------------------------------------
# Pipeline helper
# ---------------------------------------------------------------------------

def _set_pipeline_stage(run: RunRecord, stage_name: str, status: str, detail: str = None) -> None:
    for stage in run.pipeline:
        if stage.name == stage_name:
            stage.status = status
            if detail:
                stage.detail = detail
            if status == "completed":
                stage.completed_at = datetime.now(timezone.utc).isoformat()
            break


# ---------------------------------------------------------------------------
# Plan generators — marketing
# ---------------------------------------------------------------------------

def _extract_brand(intent: str) -> str:
    """Pull a brand/company name from intent text, or return a generic default."""
    known = ["Nike", "Adidas", "Apple", "Google", "Amazon", "Tesla", "Meta", "Netflix",
             "Spotify", "Airbnb", "Uber", "Shopify", "HubSpot", "Salesforce", "Slack"]
    for brand in known:
        if brand.lower() in intent.lower():
            return brand
    # Capitalised words that look like a brand
    import re
    caps = re.findall(r'\b[A-Z][a-z]{2,}\b', intent)
    return caps[0] if caps else "your brand"


def _extract_competitors(intent: str, brand: str) -> List[str]:
    text = intent.lower()
    comp_map = {
        "nike":      ["Adidas", "Puma", "New Balance"],
        "adidas":    ["Nike", "Puma", "Reebok"],
        "apple":     ["Samsung", "Google", "Microsoft"],
        "tesla":     ["Ford", "GM", "Rivian"],
        "spotify":   ["Apple Music", "YouTube Music", "Tidal"],
        "netflix":   ["Disney+", "HBO Max", "Amazon Prime"],
        "hubspot":   ["Salesforce", "Marketo", "Pardot"],
        "salesforce":["HubSpot", "Microsoft Dynamics", "Oracle"],
    }
    return comp_map.get(brand.lower(), ["Competitor A", "Competitor B"])


def _extract_category(intent: str, brand: str) -> str:
    text = intent.lower()
    if any(w in text for w in ["shoe", "sneaker", "apparel", "clothing"]):  return "sneakers"
    if any(w in text for w in ["software", "saas", "crm", "marketing"]):    return "marketing software"
    if any(w in text for w in ["phone", "device", "tech", "electronics"]):  return "smartphones"
    if any(w in text for w in ["streaming", "video", "music"]):             return "streaming services"
    return "digital marketing"


def _generate_campaign_analyst_plan(intent: str) -> List[StepRecord]:
    text = intent.lower()
    brand = _extract_brand(intent)
    competitors = _extract_competitors(intent, brand)
    category = _extract_category(intent, brand)

    steps = [
        StepRecord(step_id="s1",
                   name=f"Google Trends: '{brand}' search interest (90d)",
                   tool_id="search_trend_analysis",
                   args={"brand": brand, "competitors": competitors, "timeframe": "today 3-m"},
                   risk_score=0.10),
        StepRecord(step_id="s2",
                   name=f"Share-of-search: {brand} vs {', '.join(competitors[:2])}",
                   tool_id="competitor_share_of_search",
                   args={"brand": brand, "competitors": competitors, "timeframe": "today 3-m"},
                   risk_score=0.12),
        StepRecord(step_id="s3",
                   name=f"News sentiment analysis for '{brand}'",
                   tool_id="news_sentiment",
                   args={"brand": brand},
                   risk_score=0.14),
        StepRecord(step_id="s4",
                   name=f"Regional search interest breakdown for '{brand}'",
                   tool_id="regional_interest",
                   args={"keyword": brand, "timeframe": "today 3-m"},
                   risk_score=0.12),
        StepRecord(step_id="s5",
                   name=f"Rising queries & content opportunities in '{category}'",
                   tool_id="content_topics",
                   args={"keyword": category, "timeframe": "today 3-m"},
                   risk_score=0.12),
    ]
    return steps


def _generate_ad_optimizer_plan(intent: str) -> List[StepRecord]:
    text = intent.lower()
    brand = _extract_brand(intent)
    category = _extract_category(intent, brand)

    steps = [
        StepRecord(step_id="s1",
                   name=f"Rising keyword opportunities in '{category}'",
                   tool_id="keyword_opportunities",
                   args={"brand": brand, "category": category},
                   risk_score=0.12),
        StepRecord(step_id="s2",
                   name=f"Rising queries for '{brand}' — find search demand",
                   tool_id="rising_queries",
                   args={"keyword": brand, "timeframe": "today 3-m"},
                   risk_score=0.12),
        StepRecord(step_id="s3",
                   name="Budget optimizer — reallocate to maximize ROAS",
                   tool_id="budget_optimizer",
                   args={"total_budget": 85000, "objective": "maximize_roas", "brand": brand},
                   risk_score=0.22),
    ]
    if any(w in text for w in ["ab", "a/b", "test", "creative", "variant", "copy"]):
        steps.append(StepRecord(
            step_id=f"s{len(steps)+1}",
            name="A/B test analysis — find statistical winner",
            tool_id="ab_test_analyzer",
            args={"test_name": "CTA button copy"},
            risk_score=0.15,
        ))
    steps.append(StepRecord(
        step_id=f"s{len(steps)+1}",
        name="Publish optimized budget allocation (Google Ads + Meta sandbox)",
        tool_id="publish_campaign",
        args={"changes": {"budget_shift": "meta -$8k → email +$4k, google +$3k"}},
        risk_score=0.82,
        requires_approval=True,
    ))
    return steps


# ---------------------------------------------------------------------------
# Plan generators — business workflows
# ---------------------------------------------------------------------------

def _generate_sales_plan(intent: str) -> List[StepRecord]:
    text = intent.lower()
    company = "Acme Corp"
    for word in intent.split():
        if word[0].isupper() and len(word) > 3 and word.lower() not in ("route", "lead", "leads", "sales", "team", "notify", "assign", "create", "send", "draft"):
            company = word
            break

    steps = [
        StepRecord(step_id="s1", name=f"Score and qualify lead — {company}",
                   tool_id="lead_scorer",
                   args={"company": company, "source": "website"},
                   risk_score=0.12),
        StepRecord(step_id="s2", name=f"Look up {company} in CRM",
                   tool_id="crm_lookup",
                   args={"company": company, "email": f"contact@{company.lower().replace(' ','')}.com"},
                   risk_score=0.10),
        StepRecord(step_id="s3", name="Update CRM record — assign to sales rep",
                   tool_id="crm_update",
                   args={"company": company, "stage": "SQL", "owner": "Sarah Chen"},
                   risk_score=0.35),
        StepRecord(step_id="s4", name="Notify #sales-leads channel on Slack",
                   tool_id="slack_notify",
                   args={"channel": "#sales-leads",
                         "message": f"🔥 New high-value lead: {company} — assigned to Sarah Chen"},
                   risk_score=0.20),
        StepRecord(step_id="s5", name="Draft personalized follow-up email",
                   tool_id="email_draft",
                   args={"company": company, "to": f"contact@{company.lower().replace(' ','')}.com"},
                   risk_score=0.22),
        StepRecord(step_id="s6", name="Schedule follow-up call in 48h",
                   tool_id="schedule_followup",
                   args={"task_type": "Discovery call", "owner": "Sarah Chen"},
                   risk_score=0.12),
    ]
    return steps


def _generate_ops_plan(intent: str) -> List[StepRecord]:
    text = intent.lower()
    is_invoice = any(w in text for w in ["invoice", "payment", "bill", "vendor", "expense"])
    is_ticket  = any(w in text for w in ["ticket", "support", "issue", "bug", "request"])

    if is_invoice:
        return [
            StepRecord(step_id="s1", name="Analyze and extract invoice details",
                       tool_id="invoice_analyzer",
                       args={"vendor": "Cloudtech Solutions", "amount": 18500},
                       risk_score=0.12),
            StepRecord(step_id="s2", name="Route to appropriate approval owner",
                       tool_id="priority_router",
                       args={"priority": "High", "team": "Finance"},
                       risk_score=0.22),
            StepRecord(step_id="s3", name="Trigger CFO approval workflow — $18,500",
                       tool_id="approval_workflow",
                       args={"amount": 18500, "approver": "CFO"},
                       risk_score=0.75, requires_approval=True),
            StepRecord(step_id="s4", name="Update invoice status in system",
                       tool_id="status_updater",
                       args={"system": "Stripe", "status": "Pending Approval"},
                       risk_score=0.18),
            StepRecord(step_id="s5", name="Notify Finance team via Slack",
                       tool_id="notify_team",
                       args={"team": "Finance", "message": "Invoice INV-18500 from Cloudtech routed for CFO approval"},
                       risk_score=0.15),
        ]
    else:
        return [
            StepRecord(step_id="s1", name="Classify support ticket by priority and type",
                       tool_id="ticket_classifier",
                       args={"text": intent},
                       risk_score=0.12),
            StepRecord(step_id="s2", name="Route ticket to right engineer",
                       tool_id="priority_router",
                       args={"priority": "P2 — High", "team": "Platform Engineering"},
                       risk_score=0.22),
            StepRecord(step_id="s3", name="Trigger escalation approval for P1 tickets",
                       tool_id="approval_workflow",
                       args={"amount": 0, "approver": "Engineering Lead"},
                       risk_score=0.72, requires_approval=True),
            StepRecord(step_id="s4", name="Update ticket status to In Review",
                       tool_id="status_updater",
                       args={"system": "Jira", "status": "In Review"},
                       risk_score=0.15),
            StepRecord(step_id="s5", name="Notify team with ticket summary",
                       tool_id="notify_team",
                       args={"team": "Platform Engineering",
                             "message": "P2 ticket assigned to Marcus Webb — SLA: 4h"},
                       risk_score=0.12),
        ]


# ---------------------------------------------------------------------------
# Execution engine
# ---------------------------------------------------------------------------

async def run_execution_engine(run_id: str) -> None:
    run = RUNS[run_id]
    plan_approval_event = _plan_approval_events[run_id]
    approval_event = _approval_events[run_id]

    # Determine tool dispatcher
    def _call_tool(tool_id: str, args: dict):
        if tool_id in BUSINESS_TOOL_REGISTRY:
            return call_business_tool(tool_id, args)
        if tool_id in MARKETING_TOOL_REGISTRY:
            return call_marketing_tool(tool_id, args)
        return call_tool(tool_id, args)

    try:
        # ── Stage 1: Intent Agent ──────────────────────────────────────────
        using_llm = llm_available()
        _set_pipeline_stage(run, "intent_agent", "active",
                            "Parsing intent with LLM…" if using_llm else "Parsing intent (rule-based)…")
        _add_audit(run, "intent_received", status="processing")

        intent_data: Dict = {}
        if using_llm:
            intent_data = await asyncio.get_event_loop().run_in_executor(
                None, lambda: parse_intent(run.intent)
            )
            # LLM may correct the agent_type
            if intent_data.get("agent_type") and intent_data["agent_type"] != run.agent_type:
                log.info("agent_type_corrected",
                         original=run.agent_type, corrected=intent_data["agent_type"])
                run.agent_type = intent_data["agent_type"]
        else:
            await asyncio.sleep(0.6)

        objective = intent_data.get("objective") or run.intent
        _set_pipeline_stage(run, "intent_agent", "completed",
                            f"{'LLM' if using_llm else 'Rule-based'}: {objective[:80]}")
        _add_audit(run, "intent_parsed", status="success", reason_code=f"agent={run.agent_type}")

        # ── Stage 2: Tool Router ───────────────────────────────────────────
        _set_pipeline_stage(run, "tool_router", "active", "Selecting minimal required tool set…")

        available_tools = get_tools_for_agent(run.agent_type)
        tool_ids_str = ", ".join(t.split("(")[0] for t in available_tools)
        await asyncio.sleep(0.3)
        _set_pipeline_stage(run, "tool_router", "completed",
                            f"Available: {tool_ids_str}")

        # ── Stage 3: Plan Builder ──────────────────────────────────────────
        _set_pipeline_stage(run, "plan_builder", "active",
                            "LLM generating execution plan…" if using_llm else "Building execution plan…")

        raw_steps: Optional[List[Dict]] = None
        if using_llm:
            raw_steps = await asyncio.get_event_loop().run_in_executor(
                None, lambda: build_plan(run.agent_type, intent_data, available_tools)
            )

        # Store structured intent on the run for the frontend approval UI
        run.intent_data = intent_data

        if raw_steps:
            # Build StepRecords from LLM output
            run.steps = []
            for s in raw_steps:
                step = StepRecord(
                    step_id=s.get("step_id", f"s{len(run.steps)+1}"),
                    name=s.get("name", s.get("tool_id", "Step")),
                    description=s.get("description"),
                    tool_id=s.get("tool_id", ""),
                    args=s.get("args", {}),
                    risk_score=float(s.get("risk_score", 0.15)),
                    requires_approval=bool(s.get("requires_approval", False)),
                )
                if step.risk_score > GOVERNANCE_THRESHOLDS["risk_score"]["medium_max"]:
                    step.requires_approval = True
                run.steps.append(step)
        else:
            # Fallback to rule-based
            if run.agent_type == "research":
                run.steps = _generate_research_plan(run.intent)
            elif run.agent_type == "campaign":
                run.steps = _generate_campaign_analyst_plan(run.intent)
            elif run.agent_type == "sales":
                run.steps = _generate_sales_plan(run.intent)
            elif run.agent_type == "ops":
                run.steps = _generate_ops_plan(run.intent)
            else:
                run.status = "failed"
                run.error = f"Unknown agent_type: {run.agent_type}"
                return

        if not run.steps:
            run.status = "failed"
            run.error = "Planner returned no steps."
            return

        tool_ids = list(dict.fromkeys(s.tool_id for s in run.steps))
        _set_pipeline_stage(run, "plan_builder", "completed",
                            f"{len(run.steps)} steps · {sum(1 for s in run.steps if s.requires_approval)} approval gates · {'LLM' if raw_steps else 'rule-based'}")
        _add_audit(run, "plan_generated", status="pending_approval", reason_code=f"{len(run.steps)}_steps")

        # ── 2. Plan approval gate ──────────────────────────────────────────
        run.status = "pending_plan_approval"
        log.info("run_awaiting_plan_approval", run_id=run_id, steps=len(run.steps))

        plan_approval_event.clear()
        await plan_approval_event.wait()

        if _cancel_flags.get(run_id):
            run.status = "cancelled"
            _add_audit(run, "run_cancelled", status="cancelled", reason_code="user_cancelled")
            await _save_runs()
            return

        _add_audit(run, "plan_approved", status="approved", reason_code="human_approval")
        run.status = "executing"
        await _save_runs()

        # ── Stage 4: Workflow Engine ───────────────────────────────────────
        _set_pipeline_stage(run, "workflow_engine", "active", "Executing governed step DAG…")
        log.info("run_executing", run_id=run_id)

        # ── 3. Step execution loop ─────────────────────────────────────────
        for step in run.steps:
            if _cancel_flags.get(run_id):
                run.status = "cancelled"
                _add_audit(run, "run_cancelled", status="cancelled", reason_code="user_cancelled")
                return

            # Human approval gate for high-risk steps
            if step.requires_approval:
                step.status = "pending_approval"
                run.status = "pending_approval"
                _add_audit(run, "approval_requested", status="pending",
                           step_id=step.step_id, tool_id=step.tool_id,
                           risk_score=step.risk_score)
                await _save_runs()
                log.info("step_awaiting_approval", run_id=run_id, step_id=step.step_id)

                approval_event.clear()
                await approval_event.wait()

                if _cancel_flags.get(run_id):
                    run.status = "cancelled"
                    _add_audit(run, "run_cancelled", status="cancelled", reason_code="user_cancelled")
                    return

                _add_audit(run, "approval_granted", status="approved",
                           step_id=step.step_id, tool_id=step.tool_id,
                           risk_score=step.risk_score)
                run.status = "executing"
                log.info("step_approval_granted", run_id=run_id, step_id=step.step_id)

            # Begin step execution
            step.status = "executing"
            step.started_at = datetime.now(timezone.utc).isoformat()
            _add_audit(run, "step_started", status="executing",
                       step_id=step.step_id, tool_id=step.tool_id,
                       risk_score=step.risk_score)

            # ── Action Wrapper: 5 checks ───────────────────────────────────
            checks_passed = await _run_action_wrapper_checks(step)

            if not checks_passed:
                step.status = "failed"
                step.result = {"error": "Blocked by Action Wrapper — trust score critical"}
                step.completed_at = datetime.now(timezone.utc).isoformat()
                run.status = "failed"
                run.error = f"Step {step.step_id} blocked by governance (trust score critical)"
                _add_audit(run, "step_blocked", status="blocked",
                           step_id=step.step_id, tool_id=step.tool_id,
                           risk_score=step.risk_score, trust_score=step.trust_score,
                           reason_code="trust_score_critical")
                await _save_runs()
                return

            # ── Tool execution ─────────────────────────────────────────────
            resolved_args = _resolve_args(step, [s for s in run.steps if s.status == "completed"])
            t0 = time.monotonic()
            try:
                result = await _call_tool(step.tool_id, resolved_args)
                latency_ms = (time.monotonic() - t0) * 1000
                _update_trust(step.tool_id, success=True, latency_ms=latency_ms)
                # Refresh trust score on step after EMA update
                step.trust_score = _get_trust(step.tool_id)
                step.result = result
                step.status = "completed"
                _add_audit(run, "step_completed", status="accept",
                           step_id=step.step_id, tool_id=step.tool_id,
                           risk_score=step.risk_score, trust_score=step.trust_score,
                           reason_code="evaluator_accept")
            except Exception as e:
                latency_ms = (time.monotonic() - t0) * 1000
                _update_trust(step.tool_id, success=False, latency_ms=latency_ms)
                step.trust_score = _get_trust(step.tool_id)
                step.status = "failed"
                step.result = {"error": str(e)}
                run.status = "failed"
                run.error = f"Step {step.step_id} ({step.tool_id}) failed: {e}"
                _add_audit(run, "step_failed", status="error",
                           step_id=step.step_id, tool_id=step.tool_id,
                           risk_score=step.risk_score, trust_score=step.trust_score,
                           reason_code="tool_error")
                log.error("step_failed", run_id=run_id, step_id=step.step_id, error=str(e))
                await _save_runs()
                return
            finally:
                step.completed_at = datetime.now(timezone.utc).isoformat()

            await _save_runs()
            log.info("step_completed", run_id=run_id, step_id=step.step_id)

        # ── 4. Run complete ────────────────────────────────────────────────
        _set_pipeline_stage(run, "workflow_engine", "completed",
                            f"{len(run.steps)} steps executed")
        run.result_summary = _generate_result_summary(run)
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc).isoformat()
        _add_audit(run, "run_completed", status="success",
                   reason_code=f"{len(run.steps)}_steps_executed")
        await _save_runs()
        log.info("run_completed", run_id=run_id, steps=len(run.steps))

    except asyncio.CancelledError:
        run.status = "cancelled"
        await _save_runs()
    except Exception as e:
        run.status = "failed"
        run.error = str(e)
        await _save_runs()
        log.error("run_failed", run_id=run_id, error=str(e))


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class SubmitRunRequest(BaseModel):
    agent_type: str
    intent: str


class RunResponse(BaseModel):
    run_id: str
    agent_type: str
    intent: str
    intent_data: Dict[str, Any] = {}
    status: str
    pipeline: List[PipelineStage] = []
    steps: List[StepRecord]
    audit_log: List[AuditEntry] = []
    created_at: str
    completed_at: Optional[str] = None
    result_summary: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

# ── Startup: load persisted runs ──────────────────────────────────────────

@app.on_event("startup")
async def load_runs_store() -> None:
    try:
        # Try Redis first, fall back to file
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, _redis_load)
        if not data and _RUNS_STORE_PATH.exists():
            data = json.loads(_RUNS_STORE_PATH.read_text(encoding="utf-8"))
        for run_id, run_dict in data.items():
            run = RunRecord(**run_dict)
            RUNS[run_id] = run
            _plan_approval_events[run_id] = asyncio.Event()
            _approval_events[run_id] = asyncio.Event()
            _cancel_flags[run_id] = False
            if run.status in ("planning", "pending_plan_approval", "executing", "pending_approval"):
                run.status = "failed"
                run.error = "Server restarted during execution"
        log.info("runs_store_loaded", count=len(RUNS), source="redis" if _UPSTASH_URL else "file")
    except Exception as exc:
        log.warning("runs_store_load_failed", error=str(exc))


# ── Auth ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/auth/login")
async def login(req: LoginRequest):
    if req.email != _DEMO_USER["email"] or req.password != _DEMO_USER["password"]:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _make_token(req.password)
    log.info("user_login", email=req.email)
    return {"token": token, "user": {"email": _DEMO_USER["email"], "name": _DEMO_USER["name"]}}


@app.get("/auth/me")
async def me(current_user: Dict = Depends(_get_current_user)):
    return {"email": current_user["email"], "name": current_user["name"]}


# ── Integrations ──────────────────────────────────────────────────────────

@app.get("/integrations")
async def get_integrations(current_user: Dict = Depends(_get_current_user)):
    return _INTEGRATIONS


@app.post("/integrations/{integration_id}/toggle")
async def toggle_integration(
    integration_id: str,
    current_user: Dict = Depends(_get_current_user),
):
    for item in _INTEGRATIONS:
        if item["id"] == integration_id:
            item["connected"] = not item["connected"]
            log.info("integration_toggled", id=integration_id, connected=item["connected"])
            return item
    raise HTTPException(404, detail=f"Integration '{integration_id}' not found.")


@app.get("/trust-scores")
async def get_trust_scores(current_user: Dict = Depends(_get_current_user)):
    """Live trust scores — EMA-updated after every tool execution."""
    result = {}
    for tool_id, s in _TRUST_STATE.items():
        n = s["invocations"]
        result[tool_id] = {
            "score":          s["score"],
            "status":         _trust_status(s["score"]),
            "invocations":    n,
            "success_rate":   round(s["successes"] / n, 3) if n else None,
            "error_rate":     round(s["errors"] / n, 3) if n else None,
            "avg_latency_ms": round(s["total_latency_ms"] / n, 1) if n else None,
            "last_updated":   s["last_updated"],
        }
    return result


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "aura-demo",
        "version": "0.3.0",
        "llm": "groq/" + os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile") if llm_available() else "not_configured",
        "agents": ["sales", "ops", "campaign", "research"],
        "runs_in_memory": len(RUNS),
    }


@app.get("/stats")
async def get_stats(current_user: Dict = Depends(_get_current_user)):
    all_runs = list(RUNS.values())
    all_steps = [s for r in all_runs for s in r.steps]
    completed_steps = [s for s in all_steps if s.status == "completed"]
    approvals = [s for s in all_steps if s.requires_approval and s.status == "completed"]
    live_scores = [s["score"] for s in _TRUST_STATE.values()]
    avg_trust = round(sum(live_scores) / len(live_scores), 3) if live_scores else None

    return {
        "total_runs": len(all_runs),
        "completed_runs": sum(1 for r in all_runs if r.status == "completed"),
        "active_runs": sum(1 for r in all_runs if r.status in ("planning", "pending_plan_approval", "executing", "pending_approval")),
        "total_steps_executed": len(completed_steps),
        "approvals_granted": len(approvals),
        "avg_trust_score": avg_trust,
        "governance_events": sum(len(r.audit_log) for r in all_runs),
        "tools_connected": sum(1 for i in _INTEGRATIONS if i["connected"]),
    }


@app.post("/runs", response_model=RunResponse)
async def submit_run(req: SubmitRunRequest, background_tasks: BackgroundTasks, current_user: Dict = Depends(_get_current_user)):
    if req.agent_type not in ("research", "campaign", "sales", "ops"):
        raise HTTPException(400, detail=f"Invalid agent_type '{req.agent_type}'.")
    if not req.intent.strip():
        raise HTTPException(400, detail="Intent must not be empty.")

    run_id = f"run_{req.agent_type[:4]}_{uuid.uuid4().hex[:8]}"
    run = RunRecord(
        run_id=run_id,
        agent_type=req.agent_type,
        intent=req.intent.strip(),
        pipeline=_default_pipeline(),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    RUNS[run_id] = run
    _plan_approval_events[run_id] = asyncio.Event()
    _approval_events[run_id] = asyncio.Event()
    _cancel_flags[run_id] = False

    background_tasks.add_task(run_execution_engine, run_id)
    log.info("run_created", run_id=run_id, agent=req.agent_type)
    return run


@app.get("/runs", response_model=List[RunResponse])
async def list_runs(current_user: Dict = Depends(_get_current_user)):
    return sorted(RUNS.values(), key=lambda r: r.created_at, reverse=True)


@app.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: str, current_user: Dict = Depends(_get_current_user)):
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(404, detail=f"Run '{run_id}' not found.")
    return run


@app.post("/runs/{run_id}/approve-plan")
async def approve_plan(run_id: str, current_user: Dict = Depends(_get_current_user)):
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(404, detail=f"Run '{run_id}' not found.")
    if run.status != "pending_plan_approval":
        raise HTTPException(400, detail=f"Run is in status '{run.status}', not 'pending_plan_approval'.")
    event = _plan_approval_events.get(run_id)
    if event:
        event.set()
    log.info("plan_approved", run_id=run_id)
    return {"message": "Plan approved. Execution starting.", "run_id": run_id}


@app.post("/runs/{run_id}/approve")
async def approve_run(run_id: str, current_user: Dict = Depends(_get_current_user)):
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(404, detail=f"Run '{run_id}' not found.")
    if run.status != "pending_approval":
        raise HTTPException(400, detail=f"Run is in status '{run.status}', not 'pending_approval'.")
    event = _approval_events.get(run_id)
    if event:
        event.set()
    log.info("step_approval_granted", run_id=run_id)
    return {"message": "Approval granted. Execution resuming.", "run_id": run_id}


@app.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str, current_user: Dict = Depends(_get_current_user)):
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(404, detail=f"Run '{run_id}' not found.")
    if run.status in ("completed", "failed", "cancelled"):
        raise HTTPException(400, detail=f"Run already in terminal state '{run.status}'.")
    _cancel_flags[run_id] = True
    for ev in [_plan_approval_events.get(run_id), _approval_events.get(run_id)]:
        if ev:
            ev.set()
    log.info("run_cancelled", run_id=run_id)
    await _save_runs()
    return {"message": "Run cancelled.", "run_id": run_id}


@app.delete("/runs")
async def clear_runs(current_user: Dict = Depends(_get_current_user)):
    RUNS.clear()
    _plan_approval_events.clear()
    _approval_events.clear()
    _cancel_flags.clear()
    await _save_runs()
    return {"message": "All runs cleared."}
