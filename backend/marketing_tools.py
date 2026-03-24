"""
Marketing Tool Library — Real Data

Data sources (all free, no API key required):
  - Google Trends via pytrends       → search interest, regional data, rising queries
  - Google News RSS via feedparser   → real news headlines + TextBlob NLP sentiment
  - yfinance                         → public company financials (for comp analysis)

Tools:
  Campaign Analyst: search_trend_analysis, competitor_share_of_search,
                    regional_interest, rising_queries, news_sentiment, content_topics
  Ad Optimizer:     budget_optimizer, keyword_opportunities, ab_test_analyzer,
                    audience_expansion, publish_campaign
"""

import asyncio
import time
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import feedparser
import structlog
from textblob import TextBlob

warnings.filterwarnings("ignore")
log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Async helper — run sync libraries without blocking the event loop
# ---------------------------------------------------------------------------

async def _run_sync(fn, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


def _safe_df(df, preferred_cols, max_rows=8) -> List[Dict]:
    """Convert any pytrends DataFrame to records safely — handles variable column names."""
    if df is None or df.empty:
        return []
    try:
        cols = [c for c in preferred_cols if c in df.columns]
        if not cols:
            cols = list(df.columns)[:3]
        return df[cols].head(max_rows).fillna("").to_dict("records")
    except Exception:
        return []

# ---------------------------------------------------------------------------
# pytrends singleton — reset on error to recover from 400/429 sessions
# ---------------------------------------------------------------------------

_pytrends = None

_RATE_LIMITED = False   # set True when Google 429s us; tools use simulated fallback

def _get_pytrends(reset: bool = False):
    global _pytrends
    if _pytrends is None or reset:
        from pytrends.request import TrendReq
        _pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 30))
    return _pytrends


def _pytrends_build_payload(keywords, timeframe, geo="US", max_attempts=2):
    """Build pytrends payload. Raises _RateLimitedError on any Google error (400/429)."""
    global _RATE_LIMITED
    for attempt in range(max_attempts):
        try:
            pt = _get_pytrends(reset=(attempt > 0))
            pt.build_payload(keywords, timeframe=timeframe, geo=geo)
            _RATE_LIMITED = False
            return pt
        except Exception as e:
            err = str(e)
            # Any Google-side error (400, 429) → use simulated fallback
            if any(x in err for x in ("400", "429", "response with code")):
                if attempt < max_attempts - 1:
                    log.warning("pytrends_reset", attempt=attempt, error=err[:80])
                    time.sleep(1 + attempt)
                    continue
                _RATE_LIMITED = True
                raise _RateLimitedError()
            raise


class _RateLimitedError(Exception):
    pass


def _simulated_trends(keywords: list, seed_base: int = 40) -> dict:
    """Return plausible simulated trend data when Google rate-limits us."""
    import random
    rng = random.Random(abs(hash(tuple(keywords))) % 10000)
    base = seed_base
    scores = {}
    for i, kw in enumerate(keywords):
        scores[kw] = max(5, min(100, base - i * rng.randint(8, 18) + rng.randint(-5, 5)))
    return scores

# ---------------------------------------------------------------------------
# Tool: search_trend_analysis
# Real Google Trends data — 90-day interest over time
# ---------------------------------------------------------------------------

async def search_trend_analysis(
    brand: str = "Nike",
    competitors=None,
    timeframe: str = "today 3-m",
) -> Dict:
    if isinstance(competitors, str):
        competitors = [c.strip() for c in competitors.replace(";", ",").split(",") if c.strip()]
    competitors = (competitors or [])[:3]
    keywords = [brand] + competitors
    keywords = keywords[:5]  # pytrends max 5

    def _fetch():
        try:
            pt = _pytrends_build_payload(keywords, timeframe=timeframe, geo="US")
            df = pt.interest_over_time()
        except _RateLimitedError:
            return "rate_limited", None
        except Exception as e:
            err = str(e)
            if any(x in err for x in ("400", "429", "response with code")) or "TooManyRequests" in type(e).__name__:
                global _RATE_LIMITED; _RATE_LIMITED = True
                return "rate_limited", None
            log.warning("search_trend_build_failed", error=err[:80])
            return None, None
        if df.empty:
            return None, None
        if "isPartial" in df.columns:
            df = df.drop(columns=["isPartial"])
        avg = df.mean().round(1).to_dict()
        trend_7d = df.tail(7).mean().round(1).to_dict()
        trend_30d = df.tail(30).mean().round(1).to_dict()
        recent = df.tail(1).to_dict(orient="records")[0]
        return avg, {"recent": recent, "7d_avg": trend_7d, "30d_avg": trend_30d}

    avg, trends = await _run_sync(_fetch)

    if avg == "rate_limited":
        # Google rate-limited — return realistic simulated data
        avg = _simulated_trends(keywords, seed_base=65)
        total = sum(avg.values()) or 1
        trends = {
            "recent": avg,
            "7d_avg": {k: round(v * 0.97, 1) for k, v in avg.items()},
            "30d_avg": {k: round(v * 0.92, 1) for k, v in avg.items()},
        }
        data_source = "Google Trends (simulated — API rate limit active)"
    elif avg is None:
        return {"error": "No trend data returned — keyword may be too niche"}
    else:
        data_source = "Google Trends (real-time)"

    leader = max(avg, key=avg.get)
    brand_score = avg.get(brand, 0)
    leader_score = avg.get(leader, 0)
    gap = round(leader_score - brand_score, 1) if leader != brand else 0

    return {
        "timeframe": timeframe,
        "keywords_tracked": keywords,
        "avg_interest_0_100": avg,
        "trend_breakdown": trends,
        "leader": leader,
        "brand_score": brand_score,
        "search_gap_vs_leader": gap,
        "insight": (
            f"{brand} leads search interest in this period."
            if leader == brand
            else f"{leader} leads by {gap} points. {brand} at {brand_score}/100."
        ),
        "data_source": data_source,
    }

# ---------------------------------------------------------------------------
# Tool: competitor_share_of_search
# Real SOV from Google Trends
# ---------------------------------------------------------------------------

async def competitor_share_of_search(
    brand: str = "Nike",
    competitors=None,
    timeframe: str = "today 3-m",
) -> Dict:
    if isinstance(competitors, str):
        competitors = [c.strip() for c in competitors.replace(";", ",").split(",") if c.strip()]
    competitors = (competitors or ["Adidas", "Puma"])[:4]
    keywords = [brand] + competitors

    def _fetch():
        try:
            pt = _pytrends_build_payload(keywords, timeframe=timeframe, geo="US")
            df = pt.interest_over_time()
        except _RateLimitedError:
            return "rate_limited"
        except Exception as e:
            err = str(e)
            if any(x in err for x in ("400", "429", "response with code")) or "TooManyRequests" in type(e).__name__:
                return "rate_limited"
            log.warning("competitor_sos_build_failed", error=err[:80])
            return None
        if df.empty:
            return None
        if "isPartial" in df.columns:
            df = df.drop(columns=["isPartial"])
        return df.mean().round(1).to_dict()

    avg = await _run_sync(_fetch)
    if avg == "rate_limited":
        avg = _simulated_trends(keywords, seed_base=70)
        data_source = "Google Trends (simulated — API rate limit active)"
    elif avg is None:
        return {"error": "No data returned"}
    else:
        data_source = "Google Trends (real-time)"

    total = sum(avg.values()) or 1
    sov = {k: round(v / total * 100, 1) for k, v in avg.items()}
    ranked = sorted(sov.items(), key=lambda x: x[1], reverse=True)

    return {
        "timeframe": timeframe,
        "share_of_search_pct": sov,
        "ranking": [{"brand": k, "sov_pct": v} for k, v in ranked],
        "brand_position": next((i + 1 for i, (k, _) in enumerate(ranked) if k == brand), None),
        "brand_sov": sov.get(brand),
        "leader": ranked[0][0],
        "insight": (
            f"{brand} holds {sov.get(brand)}% share of search. "
            f"Leader is {ranked[0][0]} at {ranked[0][1]}%."
        ),
        "data_source": data_source,
    }

# ---------------------------------------------------------------------------
# Tool: regional_interest
# Real geographic breakdown from Google Trends
# ---------------------------------------------------------------------------

async def regional_interest(keyword: str = "Nike", timeframe: str = "today 3-m") -> Dict:
    _SIMULATED_REGIONS = {
        "Texas": 87, "California": 84, "Florida": 79, "New York": 76,
        "Georgia": 71, "Illinois": 68, "North Carolina": 65, "Ohio": 61,
        "Pennsylvania": 58, "Michigan": 54,
    }

    def _fetch():
        try:
            pt = _pytrends_build_payload([keyword], timeframe=timeframe, geo="US")
            df = pt.interest_by_region(resolution="REGION", inc_low_vol=False)
        except _RateLimitedError:
            return "rate_limited"
        except Exception as e:
            err = str(e)
            if any(x in err for x in ("400", "429", "response with code")) or "TooManyRequests" in type(e).__name__:
                return "rate_limited"
            log.warning("regional_interest_build_failed", error=err[:80])
            return None
        if df.empty:
            return None
        df = df.sort_values(keyword, ascending=False)
        return df.head(10)[keyword].to_dict()

    top_regions = await _run_sync(_fetch)
    if top_regions == "rate_limited":
        top_regions = _SIMULATED_REGIONS
        data_source = "Google Trends (simulated — API rate limit active)"
    elif top_regions is None:
        return {"error": "No regional data"}
    else:
        data_source = "Google Trends (real-time)"

    total = sum(top_regions.values()) or 1
    regions_pct = {k: round(v / total * 100, 1) for k, v in top_regions.items()}

    return {
        "keyword": keyword,
        "timeframe": timeframe,
        "top_regions_raw_interest": top_regions,
        "top_regions_share_pct": regions_pct,
        "top_region": next(iter(top_regions), None),
        "insight": f"Highest search interest for '{keyword}' in {next(iter(top_regions), 'N/A')}.",
        "data_source": data_source,
    }

# ---------------------------------------------------------------------------
# Tool: rising_queries
# Real rising + top queries from Google Trends
# ---------------------------------------------------------------------------

async def rising_queries(keyword: str = "Nike", timeframe: str = "today 3-m") -> Dict:
    def _fetch():
        try:
            pt = _pytrends_build_payload([keyword], timeframe=timeframe, geo="US")
            related = pt.related_queries()
        except _RateLimitedError:
            return "rate_limited", []
        except Exception as e:
            err = str(e)
            if any(x in err for x in ("400", "429", "response with code")) or "TooManyRequests" in type(e).__name__:
                return "rate_limited", []
            log.warning("rising_queries_build_failed", error=err[:80])
            return [], []
        result = related.get(keyword, {})
        rising = result.get("rising")
        top    = result.get("top")
        rising_list = _safe_df(rising, ["query", "value"], max_rows=8)
        top_list    = _safe_df(top,    ["query", "value"], max_rows=8)
        return rising_list, top_list

    rising, top = await _run_sync(_fetch)

    if rising == "rate_limited":
        kw_lower = keyword.lower()
        rising = [
            {"query": f"{kw_lower} sale 2025", "value": 250},
            {"query": f"best {kw_lower} deals", "value": 190},
            {"query": f"{kw_lower} new collection", "value": 160},
            {"query": f"{kw_lower} vs competitors", "value": 130},
        ]
        top = [
            {"query": kw_lower, "value": 100},
            {"query": f"buy {kw_lower}", "value": 72},
            {"query": f"{kw_lower} online", "value": 65},
        ]
        data_source = "Google Trends (simulated — API rate limit active)"
    else:
        data_source = "Google Trends (real-time)"

    return {
        "keyword": keyword,
        "timeframe": timeframe,
        "rising_queries": rising,
        "top_queries": top,
        "opportunity_count": len(rising),
        "insight": (
            f"{len(rising)} rising queries found for '{keyword}'. "
            + (f"Top rising: '{rising[0]['query']}'" if rising else "No rising queries.")
        ),
        "data_source": data_source,
    }

# ---------------------------------------------------------------------------
# Tool: news_sentiment
# Real headlines from Google News RSS + TextBlob NLP
# ---------------------------------------------------------------------------

async def news_sentiment(brand: str = "Nike", max_articles: int = 15) -> Dict:
    def _fetch():
        url = f"https://news.google.com/rss/search?q={quote_plus(brand)}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        articles = []
        scores = []
        for entry in feed.entries[:max_articles]:
            title = entry.get("title", "")
            blob = TextBlob(title)
            polarity = round(blob.sentiment.polarity, 3)
            subjectivity = round(blob.sentiment.subjectivity, 3)
            label = "positive" if polarity > 0.05 else "negative" if polarity < -0.05 else "neutral"
            articles.append({
                "headline": title,
                "source": entry.get("source", {}).get("title", "Unknown"),
                "published": entry.get("published", ""),
                "sentiment": label,
                "polarity": polarity,
            })
            scores.append(polarity)
        return articles, scores

    articles, scores = await _run_sync(_fetch)

    if not articles:
        return {"error": f"No news found for '{brand}'"}

    avg_score = round(sum(scores) / len(scores), 3) if scores else 0
    overall = "positive" if avg_score > 0.05 else "negative" if avg_score < -0.05 else "neutral"
    breakdown = {
        "positive": sum(1 for a in articles if a["sentiment"] == "positive"),
        "neutral":  sum(1 for a in articles if a["sentiment"] == "neutral"),
        "negative": sum(1 for a in articles if a["sentiment"] == "negative"),
    }

    return {
        "brand": brand,
        "articles_analyzed": len(articles),
        "avg_sentiment_score": avg_score,
        "overall_sentiment": overall,
        "breakdown": breakdown,
        "recent_headlines": articles[:6],
        "insight": (
            f"{brand} news sentiment is {overall} (score {avg_score:+.2f}) "
            f"across {len(articles)} recent articles. "
            f"{breakdown['positive']} positive, {breakdown['negative']} negative."
        ),
        "data_source": "Google News RSS + TextBlob NLP (real-time)",
    }

# ---------------------------------------------------------------------------
# Tool: content_topics  (rising topics for content strategy)
# Real data from Google Trends related topics
# ---------------------------------------------------------------------------

async def content_topics(keyword: str = "Nike", timeframe: str = "today 3-m") -> Dict:
    def _fetch():
        try:
            pt = _pytrends_build_payload([keyword], timeframe=timeframe, geo="US")
            topics = pt.related_topics()
            result = (topics or {}).get(keyword) or {}
            rising_df = result.get("rising")
            top_df    = result.get("top")
            return (
                _safe_df(rising_df, ["topic_title", "topic_type", "value"]),
                _safe_df(top_df,    ["topic_title", "topic_type", "value"]),
            )
        except _RateLimitedError:
            return "rate_limited", []
        except Exception as e:
            err = str(e)
            if any(x in err for x in ("400", "429", "response with code")) or "TooManyRequests" in type(e).__name__:
                return "rate_limited", []
            return [], []

    rising, top = await _run_sync(_fetch)

    if rising == "rate_limited":
        kw = keyword
        rising = [
            {"topic_title": f"{kw} sustainability", "topic_type": "Topic", "value": 220},
            {"topic_title": f"{kw} collaboration", "topic_type": "Topic", "value": 175},
            {"topic_title": f"{kw} limited edition", "topic_type": "Topic", "value": 140},
        ]
        top = [
            {"topic_title": kw, "topic_type": "Brand", "value": 100},
            {"topic_title": f"{kw} store", "topic_type": "Topic", "value": 68},
        ]
        data_source = "Google Trends (simulated — API rate limit active)"
    else:
        data_source = "Google Trends (real-time)"

    first = rising[0].get("topic_title", list(rising[0].values())[0]) if rising else None
    return {
        "keyword": keyword,
        "rising_topics": rising,
        "top_topics": top,
        "content_opportunities": len(rising),
        "insight": (
            f"{len(rising)} rising topic opportunities for content around '{keyword}'. "
            + (f"Top rising: '{first}'" if first else "No rising topics found.")
        ),
        "data_source": data_source,
    }

# ---------------------------------------------------------------------------
# Tool: budget_optimizer  (simulation — ad spend data requires API credentials)
# ---------------------------------------------------------------------------

async def budget_optimizer(
    total_budget: float = 85000,
    objective: str = "maximize_roas",
    brand: str = "your brand",
) -> Dict:
    await asyncio.sleep(0.5)
    current  = {"google_search": 32000, "meta": 28000, "linkedin": 15000, "email": 5000, "retargeting": 5000}
    optimized = {"google_search": 35000, "meta": 20000, "linkedin": 16000, "email": 9000, "retargeting": 5000}
    return {
        "note": "Budget allocation model — connect Google Ads + Meta APIs for live spend data",
        "objective": objective,
        "total_budget": total_budget,
        "current_allocation": current,
        "optimized_allocation": optimized,
        "changes": {
            "google_search":  "+$3,000 — best efficiency at scale",
            "meta":           "-$8,000 — declining ROAS, reallocate",
            "linkedin":       "+$1,000 — B2B pipeline growth",
            "email":          "+$4,000 — highest ROAS channel",
            "retargeting":    "no change",
        },
        "projected_roas_improvement": "+0.6x blended ROAS",
        "projected_additional_conversions": "+142/month",
    }

# ---------------------------------------------------------------------------
# Tool: keyword_opportunities  (real rising queries from Google Trends)
# ---------------------------------------------------------------------------

async def keyword_opportunities(brand: str = "Nike", category: str = "shoes") -> Dict:
    def _fetch():
        try:
            pt = _pytrends_build_payload([category], timeframe="today 3-m", geo="US")
            related = pt.related_queries()
        except _RateLimitedError:
            return "rate_limited"
        except Exception as e:
            err = str(e)
            if any(x in err for x in ("400", "429", "response with code")) or "TooManyRequests" in type(e).__name__:
                return "rate_limited"
            log.warning("keyword_opps_build_failed", error=err[:80])
            return []
        result = related.get(category, {})
        rising = result.get("rising")
        rising_list = rising[["query", "value"]].head(10).to_dict("records") if rising is not None and not rising.empty else []
        return rising_list

    rising = await _run_sync(_fetch)

    if rising == "rate_limited":
        rising = [
            {"query": f"best {category} 2025", "value": 300},
            {"query": f"{category} deals near me", "value": 240},
            {"query": f"affordable {category}", "value": 180},
            {"query": f"{category} reviews", "value": 150},
            {"query": f"top {category} brands", "value": 120},
        ]
        data_source = "Google Trends (simulated — API rate limit active)"
    else:
        data_source = "Google Trends (real-time)"

    return {
        "brand": brand,
        "category": category,
        "rising_keyword_opportunities": rising,
        "count": len(rising),
        "insight": (
            f"{len(rising)} rising keyword opportunities in '{category}'. "
            + (f"Highest momentum: '{rising[0]['query']}' (+{rising[0]['value']}%)" if rising else "")
        ),
        "recommendation": f"Target top 3 rising queries in Google Search campaigns for {brand}.",
        "data_source": data_source,
    }

# ---------------------------------------------------------------------------
# Tool: ab_test_analyzer  (simulation — needs ad platform API for real data)
# ---------------------------------------------------------------------------

async def ab_test_analyzer(test_name: str = "CTA button copy") -> Dict:
    await asyncio.sleep(0.4)
    return {
        "note": "A/B test analysis — connect Google Optimize or Meta API for live test data",
        "test_name": test_name,
        "variant_a": {"name": "Shop Now (blue)", "impressions": 48200, "clicks": 1591, "conversions": 127, "cvr": 7.98},
        "variant_b": {"name": "Get Yours (green)", "impressions": 48100, "clicks": 1877, "conversions": 164, "cvr": 8.74},
        "winner": "Variant B",
        "uplift": "+18.2% CVR",
        "statistical_significance": "97.4%",
        "recommendation": "Ship Variant B. Projected +$4,200/month incremental revenue.",
    }

# ---------------------------------------------------------------------------
# Tool: publish_campaign  (simulation — requires ad account write access)
# ---------------------------------------------------------------------------

async def publish_campaign(changes: Dict = None) -> Dict:
    await asyncio.sleep(0.8)
    import random
    if changes is None:
        changes = {"budget_shift": "meta -$8k → email +$4k, google +$3k"}
    return {
        "note": "Connect Google Ads + Meta APIs with write credentials to execute live",
        "status": "published_to_sandbox",
        "changes_applied": changes,
        "platforms": ["Google Ads (sandbox)", "Meta Business Manager (sandbox)"],
        "confirmation_ids": {
            "google": f"GADS-{random.randint(100000,999999)}",
            "meta":   f"META-{random.randint(100000,999999)}",
        },
        "audit_ref": f"AURA-PUB-{random.randint(10000,99999)}",
        "rollback_available": True,
    }

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

MARKETING_TOOL_REGISTRY = {
    "search_trend_analysis":      search_trend_analysis,
    "competitor_share_of_search": competitor_share_of_search,
    "regional_interest":          regional_interest,
    "rising_queries":             rising_queries,
    "news_sentiment":             news_sentiment,
    "content_topics":             content_topics,
    "budget_optimizer":           budget_optimizer,
    "keyword_opportunities":      keyword_opportunities,
    "ab_test_analyzer":           ab_test_analyzer,
    "publish_campaign":           publish_campaign,
}

async def call_marketing_tool(tool_id: str, args: Dict) -> Dict:
    fn = MARKETING_TOOL_REGISTRY.get(tool_id)
    if not fn:
        raise ValueError(f"Unknown marketing tool: {tool_id}")
    return await fn(**args)
