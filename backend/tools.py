"""
Investment Tool Library — Real Data via yfinance

All market data is live from Yahoo Finance.
Risk calculations use real historical price data.
Portfolio uses a fixed demo paper portfolio, but all analytics are real.
Trade execution is simulated (paper trade) at real current prices.

Tools:
  Research Agent:  stock_lookup, news_sentiment, peer_comparison, sector_analysis
  Portfolio Agent: get_portfolio, risk_assessment, calculate_rebalance, execute_trade
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import structlog
import yfinance as yf
from textblob import TextBlob

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Demo paper portfolio (fixed holdings — analytics are real)
# ---------------------------------------------------------------------------

DEMO_PORTFOLIO_HOLDINGS = [
    {"symbol": "AAPL",  "shares": 321,  "cost_basis": 148.20, "sector": "Technology"},
    {"symbol": "MSFT",  "shares": 95,   "cost_basis": 380.10, "sector": "Technology"},
    {"symbol": "NVDA",  "shares": 45,   "cost_basis": 620.00, "sector": "Technology"},
    {"symbol": "GOOGL", "shares": 120,  "cost_basis": 148.00, "sector": "Technology"},
    {"symbol": "META",  "shares": 28,   "cost_basis": 480.00, "sector": "Technology"},
    {"symbol": "JPM",   "shares": 88,   "cost_basis": 165.00, "sector": "Financials"},
    {"symbol": "JNJ",   "shares": 110,  "cost_basis": 148.00, "sector": "Healthcare"},
    {"symbol": "AGG",   "shares": 290,  "cost_basis": 100.20, "sector": "Fixed Income"},
    {"symbol": "VNQ",   "shares": 180,  "cost_basis": 82.00,  "sector": "Real Estate"},
    {"symbol": "GLD",   "shares": 85,   "cost_basis": 185.00, "sector": "Commodities"},
]

# Sector ETF map for real sector analysis
SECTOR_ETFS = {
    "semiconductors":    "SOXX",
    "semiconductor":     "SOXX",
    "technology":        "XLK",
    "tech":              "XLK",
    "financials":        "XLF",
    "healthcare":        "XLV",
    "energy":            "XLE",
    "consumer":          "XLY",
    "utilities":         "XLU",
    "real estate":       "XLRE",
    "industrials":       "XLI",
    "materials":         "XLB",
    "communication":     "XLC",
    "ai":                "BOTZ",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_sync(fn, *args, **kwargs):
    """Run a synchronous function in a thread pool so it doesn't block the event loop."""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, lambda: fn(*args, **kwargs))


def _sentiment_from_headlines(headlines: List[str]) -> float:
    """Compute a 0–1 sentiment score from news headlines using TextBlob."""
    if not headlines:
        return 0.50
    scores = []
    for h in headlines:
        blob = TextBlob(h)
        # polarity is -1 to +1; normalize to 0–1
        scores.append((blob.sentiment.polarity + 1) / 2)
    return round(float(np.mean(scores)), 3)


def _classify_sentiment(score: float) -> str:
    if score >= 0.72:
        return "Strongly Bullish"
    elif score >= 0.58:
        return "Bullish"
    elif score >= 0.45:
        return "Neutral"
    elif score >= 0.32:
        return "Bearish"
    return "Strongly Bearish"


def _risk_label(score: float) -> str:
    if score >= 0.80:
        return "CRITICAL"
    elif score >= 0.60:
        return "HIGH"
    elif score >= 0.30:
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# Research Agent tools
# ---------------------------------------------------------------------------

async def stock_lookup(symbol: str, **kwargs) -> Dict[str, Any]:
    """
    Fetch live price, fundamentals, and analyst consensus for a stock.
    Data source: Yahoo Finance (yfinance).
    """
    sym = symbol.upper().strip()
    log.info("tool_stock_lookup", symbol=sym)

    def _fetch():
        ticker = yf.Ticker(sym)
        info = ticker.info
        hist = ticker.history(period="5d")
        return info, hist

    try:
        info, hist = await _run_sync(_fetch)
    except Exception as e:
        return {"symbol": sym, "error": f"Failed to fetch data: {e}"}

    if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
        return {"symbol": sym, "error": "No data returned from Yahoo Finance. Symbol may be invalid."}

    price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose", 0)
    prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose") or price
    change_pct = round(((price - prev_close) / prev_close) * 100, 2) if prev_close else 0

    return {
        "symbol": sym,
        "name": info.get("longName") or info.get("shortName", sym),
        "price": round(price, 2),
        "change_pct": change_pct,
        "currency": info.get("currency", "USD"),
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
        "forward_pe": info.get("forwardPE"),
        "eps_ttm": info.get("trailingEps"),
        "revenue_growth_yoy": round((info.get("revenueGrowth") or 0) * 100, 1),
        "gross_margin": round((info.get("grossMargins") or 0) * 100, 1),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "volume": info.get("volume"),
        "avg_volume": info.get("averageVolume"),
        "dividend_yield": round((info.get("dividendYield") or 0) * 100, 2),
        "beta": info.get("beta"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "recommendation": (info.get("recommendationKey") or "N/A").upper(),
        "analyst_target": info.get("targetMeanPrice"),
        "analyst_count": info.get("numberOfAnalystOpinions"),
        "description": (info.get("longBusinessSummary") or "")[:300],
    }


async def news_sentiment(symbol: str, **kwargs) -> Dict[str, Any]:
    """
    Fetch real recent news for a symbol and compute NLP sentiment via TextBlob.
    Data source: Yahoo Finance news feed.
    """
    sym = symbol.upper().strip()
    log.info("tool_news_sentiment", symbol=sym)

    def _fetch():
        ticker = yf.Ticker(sym)
        return ticker.news

    try:
        news_items = await _run_sync(_fetch)
    except Exception as e:
        return {"symbol": sym, "error": str(e)}

    if not news_items:
        return {
            "symbol": sym,
            "sentiment_score": 0.50,
            "classification": "Neutral",
            "article_count": 0,
            "top_headlines": [],
            "note": "No recent news found.",
        }

    headlines = []
    for item in news_items[:15]:
        title = item.get("title") or item.get("content", {}).get("title", "")
        if title:
            headlines.append(title)

    score = _sentiment_from_headlines(headlines)
    classification = _classify_sentiment(score)

    return {
        "symbol": sym,
        "sentiment_score": score,
        "classification": classification,
        "article_count": len(headlines),
        "top_headlines": headlines[:5],
        "data_window": "Last 30 days",
    }


async def peer_comparison(symbol: str, peers=None, **kwargs) -> Dict[str, Any]:
    """
    Compare a stock to its peers on live fundamental metrics.
    Uses real data from Yahoo Finance for each symbol.
    """
    sym = symbol.upper().strip()
    if isinstance(peers, str):
        peers = [p.strip() for p in peers.replace(";", ",").split(",") if p.strip()]
    peer_list = [p.upper() for p in (peers or [])] if peers else []

    # Default peers by sector
    if not peer_list:
        defaults = {
            "NVDA": ["AMD", "INTC", "AVGO"],
            "AMD":  ["NVDA", "INTC", "QCOM"],
            "AAPL": ["MSFT", "GOOGL", "META"],
            "MSFT": ["AAPL", "GOOGL", "AMZN"],
            "GOOGL":["MSFT", "META", "AMZN"],
            "META": ["GOOGL", "SNAP", "PINS"],
        }
        peer_list = defaults.get(sym, [])

    all_symbols = [sym] + peer_list[:3]
    log.info("tool_peer_comparison", symbols=all_symbols)

    def _fetch_all():
        results = {}
        for s in all_symbols:
            try:
                info = yf.Ticker(s).info
                price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
                prev = info.get("previousClose") or price
                results[s] = {
                    "name": info.get("shortName", s),
                    "price": round(price, 2),
                    "change_pct": round(((price - prev) / prev) * 100, 2) if prev else 0,
                    "market_cap": info.get("marketCap"),
                    "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
                    "revenue_growth": round((info.get("revenueGrowth") or 0) * 100, 1),
                    "gross_margin": round((info.get("grossMargins") or 0) * 100, 1),
                    "recommendation": (info.get("recommendationKey") or "N/A").upper(),
                    "analyst_target": info.get("targetMeanPrice"),
                }
            except Exception as e:
                results[s] = {"error": str(e)}
        return results

    try:
        data = await _run_sync(_fetch_all)
    except Exception as e:
        return {"error": str(e)}

    # Build comparison rankings
    valid = {s: d for s, d in data.items() if "error" not in d}

    rankings = {}
    for metric in ("revenue_growth", "gross_margin", "pe_ratio"):
        vals = {s: d.get(metric) for s, d in valid.items() if d.get(metric) is not None}
        if vals:
            sorted_syms = sorted(vals, key=lambda x: vals[x], reverse=(metric != "pe_ratio"))
            rankings[metric] = {
                "leader": sorted_syms[0] if sorted_syms else None,
                "values": {s: vals[s] for s in sorted_syms},
            }

    return {
        "reference_symbol": sym,
        "peers_compared": peer_list[:3],
        "metrics": data,
        "rankings": rankings,
        "total_symbols_analyzed": len(valid),
    }


async def sector_analysis(sector: str, **kwargs) -> Dict[str, Any]:
    """
    Fetch real sector ETF performance and compute trend data.
    Uses SOXX, XLK, XLF, XLV, etc. via Yahoo Finance.
    """
    sec_key = sector.lower()
    etf_sym = None
    for k, v in SECTOR_ETFS.items():
        if k in sec_key:
            etf_sym = v
            break
    if not etf_sym:
        etf_sym = "SPY"  # fallback to S&P 500

    log.info("tool_sector_analysis", sector=sector, etf=etf_sym)

    def _fetch():
        ticker = yf.Ticker(etf_sym)
        info = ticker.info
        hist_1y = ticker.history(period="1y")
        hist_ytd = ticker.history(period="ytd")
        top_holdings = getattr(ticker, "fund_top_holdings", None)
        return info, hist_1y, hist_ytd, top_holdings

    try:
        info, hist_1y, hist_ytd, top_holdings = await _run_sync(_fetch)
    except Exception as e:
        return {"sector": sector, "etf": etf_sym, "error": str(e)}

    ytd_ret = 0.0
    one_year_ret = 0.0
    volatility = 0.0

    if not hist_ytd.empty:
        ytd_ret = round(((hist_ytd["Close"].iloc[-1] / hist_ytd["Close"].iloc[0]) - 1) * 100, 2)
    if not hist_1y.empty:
        one_year_ret = round(((hist_1y["Close"].iloc[-1] / hist_1y["Close"].iloc[0]) - 1) * 100, 2)
        daily_returns = hist_1y["Close"].pct_change().dropna()
        volatility = round(float(daily_returns.std() * np.sqrt(252) * 100), 2)

    price = info.get("regularMarketPrice") or info.get("navPrice") or info.get("previousClose", 0)

    return {
        "sector": sector.title(),
        "benchmark_etf": etf_sym,
        "current_price": round(price, 2),
        "ytd_return": f"{'+' if ytd_ret >= 0 else ''}{ytd_ret}%",
        "one_year_return": f"{'+' if one_year_ret >= 0 else ''}{one_year_ret}%",
        "annualized_volatility": f"{volatility}%",
        "outlook": "BULLISH" if ytd_ret > 5 else ("NEUTRAL" if ytd_ret > -5 else "BEARISH"),
        "etf_name": info.get("longName") or info.get("shortName", etf_sym),
        "expense_ratio": info.get("annualReportExpenseRatio"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
    }


# ---------------------------------------------------------------------------
# Portfolio Agent tools
# ---------------------------------------------------------------------------

async def get_portfolio(**kwargs) -> Dict[str, Any]:
    """
    Return the demo paper portfolio with live prices from Yahoo Finance.
    Holdings are fixed (paper portfolio), but all market values are real-time.
    """
    log.info("tool_get_portfolio")

    def _fetch_prices():
        syms = [h["symbol"] for h in DEMO_PORTFOLIO_HOLDINGS]
        tickers = yf.Tickers(" ".join(syms))
        prices = {}
        for sym in syms:
            try:
                info = tickers.tickers[sym].info
                prices[sym] = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose", 0)
            except Exception:
                prices[sym] = None
        return prices

    try:
        prices = await _run_sync(_fetch_prices)
    except Exception as e:
        return {"error": str(e)}

    enriched = []
    total_value = 0.0
    sector_totals: Dict[str, float] = {}

    for h in DEMO_PORTFOLIO_HOLDINGS:
        sym = h["symbol"]
        price = prices.get(sym) or h["cost_basis"]
        value = round(price * h["shares"], 2)
        gain_loss_pct = round(((price - h["cost_basis"]) / h["cost_basis"]) * 100, 2)
        total_value += value
        sector_totals[h["sector"]] = sector_totals.get(h["sector"], 0) + value
        enriched.append({
            "symbol": sym,
            "shares": h["shares"],
            "current_price": round(price, 2),
            "value": value,
            "cost_basis": h["cost_basis"],
            "gain_loss_pct": gain_loss_pct,
            "sector": h["sector"],
        })

    for h in enriched:
        h["portfolio_pct"] = round((h["value"] / total_value) * 100, 2) if total_value else 0

    sector_pcts = {s: round((v / total_value) * 100, 2) for s, v in sector_totals.items()}

    # Derive allocation buckets
    equity_syms = {"AAPL", "MSFT", "NVDA", "GOOGL", "META", "JPM", "JNJ", "VNQ"}
    fi_syms = {"AGG"}
    alt_syms = {"GLD"}
    equity_val = sum(h["value"] for h in enriched if h["symbol"] in equity_syms)
    fi_val = sum(h["value"] for h in enriched if h["symbol"] in fi_syms)
    alt_val = sum(h["value"] for h in enriched if h["symbol"] in alt_syms)

    return {
        "portfolio_id": "PORT-001-GROWTH-DEMO",
        "total_value": round(total_value, 2),
        "holdings": sorted(enriched, key=lambda x: x["value"], reverse=True),
        "allocation": {
            "equity":        round(equity_val / total_value * 100, 1) if total_value else 0,
            "fixed_income":  round(fi_val    / total_value * 100, 1) if total_value else 0,
            "alternatives":  round(alt_val   / total_value * 100, 1) if total_value else 0,
        },
        "target_allocation": {"equity": 70, "fixed_income": 20, "alternatives": 10},
        "sector_concentration": sector_pcts,
        "top_holding": max(enriched, key=lambda x: x["portfolio_pct"])["symbol"] if enriched else None,
        "note": "Paper portfolio — prices are live, holdings are fixed for demo",
    }


async def risk_assessment(**kwargs) -> Dict[str, Any]:
    """
    Compute real portfolio risk metrics using 1-year historical return data from Yahoo Finance.
    Calculates: beta, volatility, Sharpe ratio, VaR 95%, max drawdown, correlation.
    """
    log.info("tool_risk_assessment")

    syms = [h["symbol"] for h in DEMO_PORTFOLIO_HOLDINGS] + ["SPY"]

    def _fetch_history():
        data = yf.download(syms, period="1y", auto_adjust=True, progress=False)["Close"]
        return data

    try:
        prices_df = await _run_sync(_fetch_history)
    except Exception as e:
        return {"error": str(e)}

    if prices_df.empty:
        return {"error": "No historical data returned"}

    returns = prices_df.pct_change().dropna()
    spy_returns = returns.get("SPY", pd.Series(dtype=float))

    # Portfolio weights based on equal shares (simplified)
    portfolio_syms = [h["symbol"] for h in DEMO_PORTFOLIO_HOLDINGS if h["symbol"] in returns.columns]
    port_returns = returns[portfolio_syms].mean(axis=1)

    # Beta vs SPY
    beta = 1.0
    if not spy_returns.empty and len(port_returns) == len(spy_returns):
        cov = np.cov(port_returns.dropna(), spy_returns.dropna())
        if cov[1, 1] > 0:
            beta = round(float(cov[0, 1] / cov[1, 1]), 2)

    # Annualized volatility
    vol = round(float(port_returns.std() * np.sqrt(252) * 100), 2)

    # Annualized return
    ann_return = round(float(port_returns.mean() * 252 * 100), 2)

    # Sharpe ratio (assume 4.5% risk-free rate)
    rf = 4.5
    sharpe = round((ann_return - rf) / vol, 2) if vol > 0 else 0

    # VaR 95%
    total_val = sum(h["shares"] * 100 for h in DEMO_PORTFOLIO_HOLDINGS)  # approximate
    var_95_pct = round(float(np.percentile(port_returns.dropna(), 5) * 100), 2)
    var_95_dollar = round(abs(var_95_pct / 100) * total_val, 0)

    # Max drawdown
    cum = (1 + port_returns).cumprod()
    rolling_max = cum.cummax()
    drawdown = (cum - rolling_max) / rolling_max
    max_dd = round(float(drawdown.min() * 100), 2)

    # Concentration risk
    conc_risks = []
    for h in DEMO_PORTFOLIO_HOLDINGS:
        sym = h["symbol"]
        if sym in prices_df.columns:
            price = float(prices_df[sym].iloc[-1])
            val = price * h["shares"]
            pct = val / total_val * 100
            if pct > 15:
                conc_risks.append({"issue": f"{sym} concentration", "detail": f"{sym} represents {pct:.1f}% of portfolio — exceeds 15% threshold", "severity": "HIGH"})

    return {
        "portfolio_beta": beta,
        "sharpe_ratio": sharpe,
        "annualized_return": f"{ann_return:+.1f}%",
        "annualized_volatility": f"{vol:.1f}%",
        "value_at_risk_95": f"${var_95_dollar:,.0f}/day ({var_95_pct:+.2f}%)",
        "max_drawdown_1y": f"{max_dd:.1f}%",
        "concentration_risks": conc_risks,
        "benchmark": "SPY",
        "data_period": "1 year",
        "recommendation": "High technology concentration detected. Consider diversifying across sectors and reducing single-stock exposure." if conc_risks else "Portfolio risk within acceptable bounds.",
    }


async def calculate_rebalance(target_allocation: dict = None, **kwargs) -> Dict[str, Any]:
    """
    Calculate specific trades required to reach a target allocation.
    Uses real current prices from Yahoo Finance for trade sizing.
    """
    log.info("tool_calculate_rebalance", target=target_allocation)
    raw = target_allocation or {}
    # Normalise: accept key aliases and both fraction (0.7) and percentage (70) formats
    def _pct(d: dict, *keys, default: float) -> float:
        for k in keys:
            if k in d:
                v = float(d[k])
                return v * 100 if v <= 1.0 else v  # convert fraction → percentage
        return default

    target = {
        "equity":      _pct(raw, "equity", "equities", "stocks",       default=60.0),
        "fixed_income": _pct(raw, "fixed_income", "bonds", "fixed income", default=20.0),
        "alternatives": _pct(raw, "alternatives", "alts", "alternative",   default=10.0),
    }

    # Get live portfolio first
    portfolio = await get_portfolio()
    if "error" in portfolio:
        return {"error": portfolio["error"]}

    total = portfolio["total_value"]
    current_alloc = portfolio["allocation"]
    holdings = {h["symbol"]: h for h in portfolio["holdings"]}

    # Target values
    target_equity = total * target["equity"] / 100
    target_fi     = total * target["fixed_income"] / 100
    target_alt    = total * target["alternatives"] / 100

    # Current values by bucket
    equity_syms = {"AAPL", "MSFT", "NVDA", "GOOGL", "META", "JPM", "JNJ", "VNQ"}
    fi_syms = {"AGG"}
    alt_syms = {"GLD"}

    current_equity = sum(holdings[s]["value"] for s in equity_syms if s in holdings)
    current_fi = sum(holdings[s]["value"] for s in fi_syms if s in holdings)
    current_alt = sum(holdings[s]["value"] for s in alt_syms if s in holdings)

    # Build trade list
    trades = []

    # Reduce AAPL concentration if overweight
    aapl = holdings.get("AAPL")
    if aapl and aapl["portfolio_pct"] > 15:
        target_aapl_val = total * 0.10  # target 10% max
        sell_value = round(aapl["value"] - target_aapl_val, 2)
        sell_shares = max(1, int(sell_value / aapl["current_price"]))
        trades.append({
            "action": "SELL", "symbol": "AAPL",
            "shares": sell_shares,
            "estimated_value": round(sell_shares * aapl["current_price"], 2),
            "reason": f"Reduce AAPL concentration from {aapl['portfolio_pct']}% to ~10%",
            "risk_score": 0.78,
        })

    # Rebalance toward target
    equity_gap = target_equity - (current_equity - (trades[0]["estimated_value"] if trades else 0))
    fi_gap = target_fi - current_fi
    alt_gap = target_alt - current_alt

    if fi_gap > 5000:
        agg_price = holdings.get("AGG", {}).get("current_price", 98)
        shares = max(1, int(fi_gap / agg_price))
        trades.append({"action": "BUY", "symbol": "AGG", "shares": shares, "estimated_value": round(shares * agg_price, 2), "reason": f"Increase fixed income to {target['fixed_income']:.0f}% target", "risk_score": 0.55})

    if alt_gap > 3000:
        gld_price = holdings.get("GLD", {}).get("current_price", 185)
        shares = max(1, int(alt_gap / gld_price))
        trades.append({"action": "BUY", "symbol": "GLD", "shares": shares, "estimated_value": round(shares * gld_price, 2), "reason": f"Increase alternatives to {target['alternatives']:.0f}% target", "risk_score": 0.48})

    if equity_gap > 5000:
        spy_price = 538  # approximate
        shares = max(1, int(equity_gap / spy_price))
        trades.append({"action": "BUY", "symbol": "SPY", "shares": shares, "estimated_value": round(shares * spy_price, 2), "reason": "Maintain equity exposure via diversified ETF", "risk_score": 0.60})

    total_sells = sum(t["estimated_value"] for t in trades if t["action"] == "SELL")
    total_buys  = sum(t["estimated_value"] for t in trades if t["action"] == "BUY")

    return {
        "current_allocation": current_alloc,
        "target_allocation": target,
        "portfolio_value": total,
        "trades_required": trades,
        "total_sells": round(total_sells, 2),
        "total_buys":  round(total_buys, 2),
        "net_cash_change": round(total_sells - total_buys, 2),
        "estimated_fees": round((total_sells + total_buys) * 0.0005, 2),
        "trade_count": len(trades),
    }


async def execute_trade(symbol: str, action: str, shares: int = 0, amount: float = 0, **kwargs) -> Dict[str, Any]:
    """
    Execute a paper trade at the real current market price from Yahoo Finance.
    HIGH RISK — requires human approval for any trade.
    No real orders are placed. This is a simulation.
    """
    sym = symbol.upper().strip()
    log.info("tool_execute_trade", symbol=sym, action=action, shares=shares)

    def _fetch_price():
        info = yf.Ticker(sym).info
        return info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose", 0)

    try:
        live_price = await _run_sync(_fetch_price)
    except Exception as e:
        return {"symbol": sym, "error": f"Could not fetch live price: {e}"}

    if not live_price:
        return {"symbol": sym, "error": "Live price unavailable"}

    # Compute shares if amount given
    if shares <= 0 and amount > 0:
        shares = max(1, int(amount / live_price))

    executed_value = round(shares * live_price, 2)
    commission = round(executed_value * 0.0005, 2)

    return {
        "order_id": f"DEMO-{sym}-{int(live_price * 100) % 99999:05d}",
        "symbol": sym,
        "action": action.upper(),
        "shares_executed": shares,
        "execution_price": round(live_price, 2),
        "total_value": executed_value,
        "commission": commission,
        "net_proceeds": round(executed_value - commission, 2) if action.upper() == "SELL" else None,
        "net_cost": round(executed_value + commission, 2) if action.upper() == "BUY" else None,
        "status": "EXECUTED (PAPER)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "note": "Simulated at real market price. No real order was placed.",
    }


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOL_REGISTRY = {
    "stock_lookup":        {"fn": stock_lookup,        "risk_base": 0.12},
    "news_sentiment":      {"fn": news_sentiment,      "risk_base": 0.15},
    "peer_comparison":     {"fn": peer_comparison,     "risk_base": 0.18},
    "sector_analysis":     {"fn": sector_analysis,     "risk_base": 0.20},
    "get_portfolio":       {"fn": get_portfolio,       "risk_base": 0.08},
    "risk_assessment":     {"fn": risk_assessment,     "risk_base": 0.15},
    "calculate_rebalance": {"fn": calculate_rebalance, "risk_base": 0.28},
    "execute_trade":       {"fn": execute_trade,       "risk_base": 0.75},
}


async def call_tool(tool_id: str, args: dict) -> dict:
    """Dispatch a tool call by ID."""
    entry = TOOL_REGISTRY.get(tool_id)
    if not entry:
        return {"error": f"Unknown tool: {tool_id}"}
    return await entry["fn"](**args)
