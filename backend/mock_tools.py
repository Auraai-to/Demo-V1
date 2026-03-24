"""
Mock Investment Tool Library — Demo Backend

Realistic hardcoded responses for all 8 investment tools.
No external API keys required. All data is illustrative, not real-time.

Tools:
  Research Agent:  stock_lookup, news_sentiment, peer_comparison, sector_analysis
  Portfolio Agent: get_portfolio, risk_assessment, calculate_rebalance, execute_trade
"""

import asyncio
import random
from datetime import datetime, timezone
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Stock database (mock market data)
# ---------------------------------------------------------------------------

STOCK_DATA: Dict[str, Dict] = {
    "NVDA": {
        "symbol": "NVDA", "name": "NVIDIA Corporation",
        "price": 875.20, "change": 19.84, "change_pct": 2.32,
        "pe_ratio": 42.5, "forward_pe": 32.1, "market_cap": "2.15T",
        "52w_high": 974.00, "52w_low": 461.00,
        "volume": "42.3M", "avg_volume": "38.1M",
        "revenue_growth_yoy": 122, "gross_margin": 76.3,
        "eps_ttm": 20.58, "dividend_yield": 0.03,
        "sector": "Technology", "industry": "Semiconductors",
        "recommendation": "BUY", "analyst_target": 950.00,
        "analyst_count": 42, "strong_buy": 31, "buy": 8, "hold": 3,
    },
    "AMD": {
        "symbol": "AMD", "name": "Advanced Micro Devices",
        "price": 178.40, "change": -1.43, "change_pct": -0.79,
        "pe_ratio": 38.1, "forward_pe": 28.4, "market_cap": "288B",
        "52w_high": 227.30, "52w_low": 144.50,
        "volume": "28.7M", "avg_volume": "31.2M",
        "revenue_growth_yoy": 18, "gross_margin": 51.2,
        "eps_ttm": 4.68, "dividend_yield": 0.0,
        "sector": "Technology", "industry": "Semiconductors",
        "recommendation": "HOLD", "analyst_target": 195.00,
        "analyst_count": 38, "strong_buy": 14, "buy": 12, "hold": 10,
    },
    "INTC": {
        "symbol": "INTC", "name": "Intel Corporation",
        "price": 31.80, "change": -0.42, "change_pct": -1.3,
        "pe_ratio": 22.4, "forward_pe": 18.2, "market_cap": "135B",
        "52w_high": 51.28, "52w_low": 18.51,
        "volume": "55.1M", "avg_volume": "48.3M",
        "revenue_growth_yoy": -8, "gross_margin": 44.8,
        "eps_ttm": 1.42, "dividend_yield": 1.2,
        "sector": "Technology", "industry": "Semiconductors",
        "recommendation": "HOLD", "analyst_target": 35.00,
        "analyst_count": 35, "strong_buy": 4, "buy": 8, "hold": 18,
    },
    "AAPL": {
        "symbol": "AAPL", "name": "Apple Inc.",
        "price": 194.50, "change": 1.20, "change_pct": 0.62,
        "pe_ratio": 31.2, "forward_pe": 27.8, "market_cap": "3.01T",
        "52w_high": 232.92, "52w_low": 164.08,
        "volume": "51.2M", "avg_volume": "55.8M",
        "revenue_growth_yoy": 6, "gross_margin": 46.2,
        "eps_ttm": 6.24, "dividend_yield": 0.48,
        "sector": "Technology", "industry": "Consumer Electronics",
        "recommendation": "BUY", "analyst_target": 215.00,
        "analyst_count": 40, "strong_buy": 22, "buy": 12, "hold": 6,
    },
    "MSFT": {
        "symbol": "MSFT", "name": "Microsoft Corporation",
        "price": 450.25, "change": 3.75, "change_pct": 0.84,
        "pe_ratio": 36.4, "forward_pe": 30.2, "market_cap": "3.35T",
        "52w_high": 468.35, "52w_low": 362.90,
        "volume": "18.4M", "avg_volume": "19.7M",
        "revenue_growth_yoy": 16, "gross_margin": 69.4,
        "eps_ttm": 12.38, "dividend_yield": 0.72,
        "sector": "Technology", "industry": "Software",
        "recommendation": "BUY", "analyst_target": 490.00,
        "analyst_count": 44, "strong_buy": 30, "buy": 11, "hold": 3,
    },
    "GOOGL": {
        "symbol": "GOOGL", "name": "Alphabet Inc.",
        "price": 175.00, "change": 1.85, "change_pct": 1.07,
        "pe_ratio": 24.8, "forward_pe": 20.1, "market_cap": "2.18T",
        "52w_high": 207.05, "52w_low": 130.67,
        "volume": "22.1M", "avg_volume": "23.4M",
        "revenue_growth_yoy": 14, "gross_margin": 58.1,
        "eps_ttm": 7.04, "dividend_yield": 0.48,
        "sector": "Technology", "industry": "Internet Services",
        "recommendation": "BUY", "analyst_target": 210.00,
        "analyst_count": 45, "strong_buy": 28, "buy": 13, "hold": 4,
    },
    "META": {
        "symbol": "META", "name": "Meta Platforms Inc.",
        "price": 598.40, "change": 8.20, "change_pct": 1.39,
        "pe_ratio": 28.3, "forward_pe": 22.4, "market_cap": "1.52T",
        "52w_high": 638.40, "52w_low": 374.94,
        "volume": "14.8M", "avg_volume": "15.2M",
        "revenue_growth_yoy": 22, "gross_margin": 81.8,
        "eps_ttm": 21.14, "dividend_yield": 0.36,
        "sector": "Technology", "industry": "Social Media",
        "recommendation": "BUY", "analyst_target": 640.00,
        "analyst_count": 43, "strong_buy": 29, "buy": 11, "hold": 3,
    },
    "SPY": {
        "symbol": "SPY", "name": "SPDR S&P 500 ETF Trust",
        "price": 538.20, "change": 4.10, "change_pct": 0.77,
        "pe_ratio": 22.1, "market_cap": "510B",
        "52w_high": 588.74, "52w_low": 491.22,
        "volume": "68.4M", "avg_volume": "72.1M",
        "recommendation": "BUY", "analyst_target": 565.00,
    },
    "AGG": {
        "symbol": "AGG", "name": "iShares Core U.S. Aggregate Bond ETF",
        "price": 98.40, "change": -0.15, "change_pct": -0.15,
        "pe_ratio": None, "market_cap": "89B",
        "52w_high": 101.20, "52w_low": 94.32,
        "volume": "8.4M", "avg_volume": "9.1M",
        "recommendation": "HOLD", "analyst_target": 100.00,
    },
    "ARKK": {
        "symbol": "ARKK", "name": "ARK Innovation ETF",
        "price": 52.80, "change": 1.20, "change_pct": 2.33,
        "pe_ratio": None, "market_cap": "6.8B",
        "52w_high": 68.43, "52w_low": 36.57,
        "volume": "14.2M", "avg_volume": "15.8M",
        "recommendation": "SPECULATIVE", "analyst_target": 58.00,
    },
}

# Mock portfolio
PORTFOLIO = {
    "portfolio_id": "PORT-001-GROWTH",
    "total_value": 284_000,
    "cash": 5_200,
    "last_updated": "2026-03-17T08:00:00Z",
    "holdings": [
        {"symbol": "AAPL", "shares": 321,  "value": 62_434, "pct": 22.0, "cost_basis": 148.20, "gain_loss_pct": 31.2,  "sector": "Technology"},
        {"symbol": "MSFT", "shares": 95,   "value": 42_774, "pct": 15.1, "cost_basis": 380.10, "gain_loss_pct": 18.4,  "sector": "Technology"},
        {"symbol": "NVDA", "shares": 45,   "value": 39_384, "pct": 13.9, "cost_basis": 620.00, "gain_loss_pct": 41.2,  "sector": "Technology"},
        {"symbol": "GOOGL", "shares": 120, "value": 21_000, "pct": 7.4,  "cost_basis": 148.00, "gain_loss_pct": 18.2,  "sector": "Technology"},
        {"symbol": "META", "shares": 28,   "value": 16_755, "pct": 5.9,  "cost_basis": 480.00, "gain_loss_pct": 24.7,  "sector": "Technology"},
        {"symbol": "JPM",  "shares": 88,   "value": 16_632, "pct": 5.9,  "cost_basis": 165.00, "gain_loss_pct": 14.3,  "sector": "Financials"},
        {"symbol": "JNJ",  "shares": 110,  "value": 15_378, "pct": 5.4,  "cost_basis": 148.00, "gain_loss_pct": -5.6,  "sector": "Healthcare"},
        {"symbol": "AGG",  "shares": 290,  "value": 28_536, "pct": 10.1, "cost_basis": 100.20, "gain_loss_pct": -1.8,  "sector": "Fixed Income"},
        {"symbol": "VNQ",  "shares": 180,  "value": 14_166, "pct": 5.0,  "cost_basis": 82.00,  "gain_loss_pct": 5.8,   "sector": "Real Estate"},
        {"symbol": "GLD",  "shares": 85,   "value": 17_527, "pct": 6.2,  "cost_basis": 185.00, "gain_loss_pct": 11.4,  "sector": "Commodities"},
    ],
    "allocation": {"equity": 85, "fixed_income": 10, "alternatives": 5},
    "target_allocation": {"equity": 70, "fixed_income": 20, "alternatives": 10},
    "sector_concentration": {"Technology": 70.2, "Financials": 5.9, "Healthcare": 5.4, "Fixed Income": 10.1, "Real Estate": 5.0, "Commodities": 6.2},
}


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def stock_lookup(symbol: str, **kwargs) -> Dict[str, Any]:
    """Fetch price, fundamentals, and analyst ratings for a stock."""
    await asyncio.sleep(0.8)
    sym = symbol.upper().strip()
    data = STOCK_DATA.get(sym)
    if not data:
        # Generic response for unknown symbols
        return {
            "symbol": sym,
            "price": round(100 + random.uniform(-20, 80), 2),
            "change_pct": round(random.uniform(-3, 4), 2),
            "recommendation": "HOLD",
            "note": "Limited data available for this symbol",
        }
    return {
        "symbol": data["symbol"],
        "name": data["name"],
        "price": data["price"],
        "change_pct": data["change_pct"],
        "pe_ratio": data.get("pe_ratio"),
        "forward_pe": data.get("forward_pe"),
        "market_cap": data["market_cap"],
        "52w_high": data.get("52w_high"),
        "52w_low": data.get("52w_low"),
        "revenue_growth_yoy": data.get("revenue_growth_yoy"),
        "gross_margin": data.get("gross_margin"),
        "recommendation": data["recommendation"],
        "analyst_target": data.get("analyst_target"),
        "analyst_count": data.get("analyst_count"),
    }


async def news_sentiment(symbol: str, **kwargs) -> Dict[str, Any]:
    """Analyze recent news sentiment and headline summary for a symbol."""
    await asyncio.sleep(1.0)
    sym = symbol.upper().strip()

    sentiment_map = {
        "NVDA": {"score": 0.84, "classification": "Strongly Bullish", "article_count": 52,
                 "headlines": [
                     "NVIDIA Blackwell GPU demand far exceeds supply through 2026 — analysts raise targets",
                     "Microsoft, Google confirm $12B+ NVDA chip orders for AI infrastructure",
                     "NVIDIA data center revenue surges 409% YoY in Q4 — beats all estimates",
                 ]},
        "AMD": {"score": 0.58, "classification": "Moderately Bullish", "article_count": 31,
                "headlines": [
                    "AMD MI300X GPU gains traction with cloud hyperscalers, taking share from NVDA",
                    "AMD Q4 2025 revenue misses estimates but guidance raised — mixed reaction",
                    "New AMD Instinct chips show competitive benchmarks against NVDA H100",
                ]},
        "AAPL": {"score": 0.61, "classification": "Moderately Bullish", "article_count": 44,
                 "headlines": [
                     "Apple Intelligence features drive iPhone 17 upgrade cycle expectations",
                     "Apple services revenue hits record $26B — investors cheer diversification",
                     "Concerns remain over Apple's China exposure amid tariff uncertainty",
                 ]},
        "MSFT": {"score": 0.77, "classification": "Bullish", "article_count": 38,
                 "headlines": [
                     "Microsoft Copilot adoption accelerates — 85M+ enterprise seats activated",
                     "Azure AI revenue grows 157% YoY, widening lead vs AWS and GCP",
                     "Microsoft raises FY2026 guidance on AI productivity tailwinds",
                 ]},
    }

    data = sentiment_map.get(sym, {
        "score": round(random.uniform(0.40, 0.75), 2),
        "classification": "Neutral",
        "article_count": random.randint(8, 30),
        "headlines": [f"Analyst coverage for {sym} remains mixed amid market uncertainty"],
    })

    return {
        "symbol": sym,
        "sentiment_score": data["score"],
        "classification": data["classification"],
        "article_count": data["article_count"],
        "top_headlines": data["headlines"],
        "data_window": "Last 30 days",
    }


async def peer_comparison(symbol: str, peers: list = None, **kwargs) -> Dict[str, Any]:
    """Compare a stock against its sector peers on key metrics."""
    await asyncio.sleep(1.2)
    sym = symbol.upper().strip()

    # Semiconductor peer comparison
    if sym in ("NVDA", "AMD", "INTC"):
        return {
            "reference_symbol": sym,
            "peers_compared": ["NVDA", "AMD", "INTC"],
            "rankings": {
                "revenue_growth": {"rank": 1 if sym == "NVDA" else (2 if sym == "AMD" else 3), "winner": "NVDA", "values": {"NVDA": "+122%", "AMD": "+18%", "INTC": "-8%"}},
                "gross_margin":   {"rank": 1 if sym == "NVDA" else (2 if sym == "AMD" else 3), "winner": "NVDA", "values": {"NVDA": "76.3%", "AMD": "51.2%", "INTC": "44.8%"}},
                "pe_ratio":       {"rank": 3 if sym == "NVDA" else (2 if sym == "AMD" else 1), "lowest": "INTC", "values": {"NVDA": "42.5x", "AMD": "38.1x", "INTC": "22.4x"}},
                "ytd_performance": {"rank": 1 if sym == "NVDA" else (2 if sym == "AMD" else 3), "winner": "NVDA", "values": {"NVDA": "+18.4%", "AMD": "+4.2%", "INTC": "-12.3%"}},
            },
            "summary": f"{'NVDA dominates on growth and margins. AMD shows competitive AI positioning. INTC faces structural headwinds.' if sym in ('NVDA', 'AMD') else 'INTC lags peers significantly on growth metrics. Turnaround timeline remains uncertain.'}",
        }

    # Tech mega-cap comparison
    if sym in ("AAPL", "MSFT", "GOOGL", "META"):
        return {
            "reference_symbol": sym,
            "peers_compared": ["AAPL", "MSFT", "GOOGL", "META"],
            "rankings": {
                "revenue_growth": {"winner": "META", "values": {"META": "+22%", "MSFT": "+16%", "GOOGL": "+14%", "AAPL": "+6%"}},
                "gross_margin":   {"winner": "META", "values": {"META": "81.8%", "MSFT": "69.4%", "GOOGL": "58.1%", "AAPL": "46.2%"}},
                "ai_positioning": {"ranking": ["MSFT", "GOOGL", "META", "AAPL"], "note": "MSFT leads via Azure+Copilot; GOOGL strong via Gemini+Cloud"},
                "valuation":      {"cheapest": "GOOGL", "values": {"GOOGL": "20.1x fwd P/E", "META": "22.4x", "AAPL": "27.8x", "MSFT": "30.2x"}},
            },
            "summary": "All four companies show strong AI integration. META leads on margins and growth. MSFT strongest AI monetization. GOOGL most attractive on valuation.",
        }

    return {
        "reference_symbol": sym,
        "peers_compared": peers or [],
        "summary": f"Peer analysis for {sym} — limited comparable data available",
    }


async def sector_analysis(sector: str, **kwargs) -> Dict[str, Any]:
    """Return sector performance, trends, and outlook."""
    await asyncio.sleep(1.0)
    sec = sector.lower()

    if "semi" in sec or "chip" in sec:
        return {
            "sector": "Semiconductors (SOXX)",
            "ytd_performance": "+18.4%",
            "vs_sp500": "+9.8% outperformance",
            "outlook": "BULLISH",
            "outlook_horizon": "12 months",
            "key_drivers": [
                "AI infrastructure buildout — $500B+ hyperscaler capex projected for 2026",
                "Data center GPU demand growing 85% YoY, supply constrained through 2026",
                "Automotive chip cycle recovery adds incremental demand layer",
            ],
            "key_risks": [
                "US export restrictions on advanced chips to China",
                "Potential correction if AI capex growth decelerates in H2 2026",
                "Memory oversupply (DRAM/NAND) creating drag on diversified players",
            ],
            "top_holdings_performance": {"NVDA": "+18.4%", "AMD": "+4.2%", "AVGO": "+22.1%", "INTC": "-12.3%"},
            "recommended_exposure": "Overweight — 8–12% of technology allocation",
        }

    if "tech" in sec:
        return {
            "sector": "Technology (XLK)",
            "ytd_performance": "+12.1%",
            "vs_sp500": "+3.5% outperformance",
            "outlook": "BULLISH",
            "key_drivers": ["AI integration across enterprise software", "Cloud migration acceleration", "Strong free cash flow generation"],
            "key_risks": ["High valuations (avg 28x fwd P/E)", "Interest rate sensitivity", "Regulatory scrutiny on big tech"],
            "recommended_exposure": "Overweight — up to 30% of equity allocation",
        }

    return {
        "sector": sector,
        "outlook": "NEUTRAL",
        "ytd_performance": f"+{round(random.uniform(2, 15), 1)}%",
        "note": "Sector data in progress — using estimate",
    }


async def get_portfolio(**kwargs) -> Dict[str, Any]:
    """Retrieve current portfolio holdings and allocation."""
    await asyncio.sleep(0.7)
    return {
        "portfolio_id": PORTFOLIO["portfolio_id"],
        "total_value": PORTFOLIO["total_value"],
        "cash": PORTFOLIO["cash"],
        "holding_count": len(PORTFOLIO["holdings"]),
        "top_holdings": [
            {"symbol": h["symbol"], "value": h["value"], "pct": h["pct"], "gain_loss_pct": h["gain_loss_pct"]}
            for h in PORTFOLIO["holdings"][:5]
        ],
        "allocation": PORTFOLIO["allocation"],
        "target_allocation": PORTFOLIO["target_allocation"],
        "drift_from_target": {
            "equity": PORTFOLIO["allocation"]["equity"] - PORTFOLIO["target_allocation"]["equity"],
            "fixed_income": PORTFOLIO["allocation"]["fixed_income"] - PORTFOLIO["target_allocation"]["fixed_income"],
            "alternatives": PORTFOLIO["allocation"]["alternatives"] - PORTFOLIO["target_allocation"]["alternatives"],
        },
        "sector_concentration": PORTFOLIO["sector_concentration"],
        "last_updated": PORTFOLIO["last_updated"],
    }


async def risk_assessment(**kwargs) -> Dict[str, Any]:
    """Compute portfolio risk metrics."""
    await asyncio.sleep(1.0)
    return {
        "portfolio_beta": 1.34,
        "sharpe_ratio": 1.82,
        "annualized_volatility": "18.4%",
        "value_at_risk_95": "$8,200 per day",
        "max_drawdown_ytd": "-6.8%",
        "concentration_risks": [
            {"issue": "Single-stock concentration", "detail": "AAPL represents 22.0% of portfolio — exceeds 15% threshold", "severity": "HIGH"},
            {"issue": "Sector concentration", "detail": "Technology sector at 70.2% — significantly above 40% guideline", "severity": "HIGH"},
            {"issue": "Fixed income underweight", "detail": "Fixed income at 10% vs 20% target — portfolio over-exposed to equity risk", "severity": "MEDIUM"},
        ],
        "correlation": {"equity_bond": -0.12, "equity_equity": 0.71},
        "stress_test": {
            "2008_scenario": "-42.3% estimated",
            "2020_covid": "-31.8% estimated",
            "2022_rate_hike": "-24.1% estimated",
        },
        "recommendation": "Reduce single-stock and technology sector concentration. Increase fixed income allocation to target.",
    }


async def calculate_rebalance(target_allocation: dict = None, **kwargs) -> Dict[str, Any]:
    """Calculate specific trades required to reach target allocation."""
    await asyncio.sleep(1.2)
    target = target_allocation or {"equity": 70, "fixed_income": 20, "alternatives": 10}
    return {
        "current_allocation": PORTFOLIO["allocation"],
        "target_allocation": target,
        "trades_required": [
            {"action": "SELL", "symbol": "AAPL",  "shares": 155,  "estimated_value": 30_148, "reason": "Reduce single-stock from 22% to 11%"},
            {"action": "BUY",  "symbol": "SPY",   "shares": 56,   "estimated_value": 30_139, "reason": "Increase broad equity exposure"},
            {"action": "BUY",  "symbol": "AGG",   "shares": 285,  "estimated_value": 28_044, "reason": "Bring fixed income to 20% target"},
            {"action": "BUY",  "symbol": "ARKK",  "shares": 533,  "estimated_value": 28_142, "reason": "Increase alternatives to 10% target"},
        ],
        "total_proceeds": 30_148,
        "total_purchases": 86_325,
        "net_cash_needed": 56_177,
        "estimated_fees": 127,
        "estimated_tax_impact": "~$4,200 long-term capital gains (AAPL held >1 year)",
        "rebalancing_summary": "4 trades required. Sell AAPL to reduce concentration, deploy proceeds into diversified equity ETF, bonds, and alternatives.",
    }


async def execute_trade(symbol: str, action: str, amount: float = 0, shares: int = 0, **kwargs) -> Dict[str, Any]:
    """Execute a trade order. HIGH RISK — requires human approval for amounts > $10,000."""
    await asyncio.sleep(1.5)
    sym = symbol.upper().strip()
    stock = STOCK_DATA.get(sym, {"price": 100.0})
    execution_price = round(stock["price"] * random.uniform(0.998, 1.002), 2)
    executed_shares = shares if shares else int(amount / execution_price)
    executed_value = round(executed_shares * execution_price, 2)

    return {
        "order_id": f"ORD-{sym}-{int(execution_price*100)}",
        "symbol": sym,
        "action": action.upper(),
        "shares_executed": executed_shares,
        "execution_price": execution_price,
        "total_value": executed_value,
        "status": "EXECUTED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "venue": "NYSE (simulated)",
        "commission": round(executed_value * 0.0005, 2),
        "note": "Demo execution — no real orders placed",
    }


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOL_REGISTRY = {
    "stock_lookup":       {"fn": stock_lookup,        "risk_base": 0.12, "requires_approval_threshold": 999},
    "news_sentiment":     {"fn": news_sentiment,      "risk_base": 0.15, "requires_approval_threshold": 999},
    "peer_comparison":    {"fn": peer_comparison,     "risk_base": 0.18, "requires_approval_threshold": 999},
    "sector_analysis":    {"fn": sector_analysis,     "risk_base": 0.20, "requires_approval_threshold": 999},
    "get_portfolio":      {"fn": get_portfolio,       "risk_base": 0.08, "requires_approval_threshold": 999},
    "risk_assessment":    {"fn": risk_assessment,     "risk_base": 0.15, "requires_approval_threshold": 999},
    "calculate_rebalance":{"fn": calculate_rebalance, "risk_base": 0.28, "requires_approval_threshold": 999},
    "execute_trade":      {"fn": execute_trade,       "risk_base": 0.72, "requires_approval_threshold": 0.70},
}


async def call_tool(tool_id: str, args: dict) -> dict:
    """Dispatch a tool call by ID."""
    entry = TOOL_REGISTRY.get(tool_id)
    if not entry:
        return {"error": f"Unknown tool: {tool_id}"}
    return await entry["fn"](**args)
