"""
LLM layer — Groq-backed Intent Agent and Planner.

Intent Agent:  Parses free-form user goal → structured intent
               (agent_type, brand/symbols, objective, extracted_entities)

Planner:       Takes structured intent → generates a real execution plan
               as a list of steps with tool_id, args, risk_score, name

Falls back to rule-based logic if GROQ_API_KEY is not set.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

import structlog
from dotenv import load_dotenv

load_dotenv()
log = structlog.get_logger()

_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
_GROQ_MODEL   = os.getenv("LLM_MODEL", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
_client = None


def _get_client():
    global _client
    if _client is None:
        if not _GROQ_API_KEY or _GROQ_API_KEY == "your_groq_api_key_here":
            return None
        from groq import Groq
        _client = Groq(api_key=_GROQ_API_KEY)
    return _client


def llm_available() -> bool:
    return bool(_GROQ_API_KEY and _GROQ_API_KEY != "your_groq_api_key_here")


def _chat(system: str, user: str, temperature: float = 0.3) -> Optional[str]:
    client = _get_client()
    if not client:
        return None
    try:
        resp = client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            temperature=temperature,
            max_tokens=1024,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        log.warning("groq_error", error=str(e))
        return None


# ---------------------------------------------------------------------------
# Intent Agent
# ---------------------------------------------------------------------------

_INTENT_SYSTEM = """You are the Intent Agent for Aura, an AI command center.
Your job is to parse the user's goal and return a JSON object with:

{
  "agent_type": "campaign" | "optimizer" | "research" | "portfolio",
  "brand": "<brand or company name, or null>",
  "symbols": ["TICKER", ...],
  "competitors": ["CompetitorA", ...],
  "category": "<product/market category or null>",
  "objective": "<one sentence: what the user actually wants to achieve>",
  "key_entities": ["entity1", "entity2"],
  "clarification_needed": false
}

Rules:
- campaign = analyze marketing performance, brand search, sentiment, competitors
- optimizer = improve/optimize campaigns, budgets, keywords, A/B tests, publish changes
- research  = analyze stocks, equities, financials, earnings
- portfolio = manage/rebalance an investment portfolio, execute trades

Return ONLY the JSON object, no explanation.
"""


def parse_intent(intent_text: str) -> Dict:
    """Call Groq to parse intent. Returns structured dict."""
    raw = _chat(_INTENT_SYSTEM, intent_text)
    if not raw:
        return {}
    try:
        # Strip markdown code fences if present
        raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`")
        return json.loads(raw)
    except Exception:
        log.warning("intent_parse_failed", raw=raw[:200])
        return {}


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

_MARKETING_TOOLS = {
    "campaign": [
        "search_trend_analysis(brand, competitors, timeframe) — real Google Trends interest over time",
        "competitor_share_of_search(brand, competitors, timeframe) — share of search vs competitors",
        "regional_interest(keyword, timeframe) — geographic breakdown of search interest",
        "rising_queries(keyword, timeframe) — rising search queries from Google Trends",
        "news_sentiment(brand) — real headline sentiment via Google News RSS + NLP",
        "content_topics(keyword, timeframe) — rising content topics from Google Trends",
    ],
    "optimizer": [
        "keyword_opportunities(brand, category) — rising keyword opportunities from Google Trends",
        "rising_queries(keyword, timeframe) — rising search queries from Google Trends",
        "budget_optimizer(total_budget, objective, brand) — budget reallocation model",
        "ab_test_analyzer(test_name) — A/B test statistical significance",
        "publish_campaign(changes) — publish changes to ad platforms [HIGH RISK — requires approval]",
    ],
    "research": [
        "stock_lookup(symbol) — live price, P/E, market cap, analyst target",
        "news_sentiment(symbol) — real news sentiment via Yahoo Finance + NLP",
        "peer_comparison(symbol, peers) — multi-symbol comparison",
        "sector_analysis(sector) — ETF-based sector performance",
    ],
    "portfolio": [
        "get_portfolio() — current holdings with live prices",
        "risk_assessment() — beta, Sharpe, VaR 95%, max drawdown",
        "calculate_rebalance(target_allocation) — returns trades_required list with symbol/action/shares for each trade",
        "execute_trade(symbol, action, shares, amount) — executes the first trade from calculate_rebalance output [HIGH RISK — requires approval]. Use symbol='AAPL', action='SELL', shares=50, amount=0 as placeholder args; the engine resolves real values at runtime from the calculate_rebalance result.",
    ],
}

_PLANNER_SYSTEM = """You are the Planner for Aura, an AI command center.
Given a parsed user intent and available tools, generate an execution plan.

Return a JSON array of steps:
[
  {
    "step_id": "s1",
    "name": "<short action title, max 60 chars>",
    "description": "<2-3 sentences: what this step does, what data it fetches or calculates, and why it's needed to answer the user's goal>",
    "tool_id": "<exact tool name>",
    "args": { <tool arguments as key-value pairs> },
    "risk_score": <0.0-1.0 float>,
    "requires_approval": <true only if risk_score > 0.69>
  }
]

Risk score guidelines:
- Read-only data fetching: 0.08–0.20
- Analysis / comparison: 0.15–0.30
- Budget / allocation changes: 0.40–0.60
- Publishing / executing trades: 0.75–0.85

Use only the tools listed. Choose the minimal set needed to fully answer the objective.
The description must be plain English — assume the reader is a business stakeholder, not an engineer.

IMPORTANT — portfolio plans only: execute_trade args cannot be known at planning time because they come from
calculate_rebalance output. Always use these exact placeholder args for execute_trade:
  "symbol": "AAPL", "action": "SELL", "shares": 50, "amount": 0
The execution engine will replace them with the real first trade from calculate_rebalance at runtime.

Return ONLY the JSON array, no explanation.
"""


def build_plan(agent_type: str, intent_data: Dict, available_tools: List[str]) -> Optional[List[Dict]]:
    """Call Groq to generate a step plan. Returns list of step dicts or None."""
    tools_desc = "\n".join(f"- {t}" for t in available_tools)
    user_msg = f"""Intent data: {json.dumps(intent_data, indent=2)}

Available tools:
{tools_desc}

Generate the execution plan."""

    raw = _chat(_PLANNER_SYSTEM, user_msg)
    if not raw:
        return None
    try:
        raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`")
        steps = json.loads(raw)
        if not isinstance(steps, list):
            return None
        return steps
    except Exception:
        log.warning("planner_parse_failed", raw=raw[:200])
        return None


def get_tools_for_agent(agent_type: str) -> List[str]:
    return _MARKETING_TOOLS.get(agent_type, [])
