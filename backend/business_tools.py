"""
Business workflow tools — Sales & CRM and Operations agents.

All tools are simulated with realistic mock data for demo purposes.
Each tool mirrors a real integration action: Slack, HubSpot CRM, Stripe, Jira, etc.
"""

import asyncio
import os
import random
from datetime import datetime, timezone
from typing import Any, Dict

import requests

_SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")


def _post_slack(text: str) -> bool:
    """POST to Slack webhook. Returns True on success, False on failure."""
    if not _SLACK_WEBHOOK:
        return False
    try:
        resp = requests.post(_SLACK_WEBHOOK, json={"text": text}, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False

# ---------------------------------------------------------------------------
# Sales & CRM tools
# ---------------------------------------------------------------------------

async def lead_scorer(args: Dict[str, Any]) -> Dict[str, Any]:
    await asyncio.sleep(0.9)
    company  = args.get("company", "Acme Corp")
    source   = args.get("source", "website")
    score    = random.randint(72, 94)
    tier     = "A" if score >= 85 else "B" if score >= 70 else "C"
    return {
        "lead_score": score,
        "tier": tier,
        "company": company,
        "source": source,
        "employees": random.choice([120, 340, 850, 2400]),
        "annual_revenue": random.choice(["$5M–$20M", "$20M–$100M", "$100M+"]),
        "intent_signals": ["pricing page visited 3×", "demo page visited", "case study downloaded"],
        "recommended_action": "Assign to senior AE — high-value prospect",
        "similar_won_deals": random.randint(4, 12),
    }


async def crm_lookup(args: Dict[str, Any]) -> Dict[str, Any]:
    await asyncio.sleep(0.7)
    company = args.get("company", "Acme Corp")
    email   = args.get("email", "contact@acme.com")
    return {
        "found": True,
        "company": company,
        "contact_email": email,
        "existing_stage": "MQL",
        "last_activity": "Email opened 3 days ago",
        "open_opportunities": 0,
        "lifetime_value": "$0 (new prospect)",
        "notes": "Attended webinar in Q1 2026",
        "owner": "Unassigned",
    }


async def crm_update(args: Dict[str, Any]) -> Dict[str, Any]:
    await asyncio.sleep(1.1)
    return {
        "updated": True,
        "record_id": f"HB-{random.randint(10000, 99999)}",
        "stage": args.get("stage", "SQL"),
        "owner_assigned": args.get("owner", "Sarah Chen"),
        "fields_updated": ["stage", "owner", "lead_score", "last_activity"],
        "audit_ref": f"CRM-{random.randint(1000, 9999)}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def slack_notify(args: Dict[str, Any]) -> Dict[str, Any]:
    channel = args.get("channel", "#sales-leads")
    message = args.get("message", "New high-value lead routed to sales")
    text    = f"*Aura Agent* | {channel}\n{message}"
    sent    = await asyncio.get_event_loop().run_in_executor(None, lambda: _post_slack(text))
    if not sent:
        await asyncio.sleep(0.6)  # fallback mock delay
    return {
        "sent": True,
        "real_slack": sent,
        "channel": channel,
        "message_preview": message[:80],
        "recipients_notified": random.randint(3, 8),
        "message_id": f"slack_{random.randint(100000, 999999)}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def email_draft(args: Dict[str, Any]) -> Dict[str, Any]:
    await asyncio.sleep(1.2)
    to      = args.get("to", "contact@acme.com")
    company = args.get("company", "Acme Corp")
    return {
        "draft_created": True,
        "to": to,
        "subject": f"Following up — how Aura can help {company}",
        "preview": (
            f"Hi there, I noticed {company} has been exploring Aura's workflow automation platform. "
            "Based on your team size and the challenges you're facing, I'd love to show you "
            "how we've helped similar companies reduce manual ops by 60%..."
        ),
        "personalization_tokens_used": ["company_name", "intent_signals", "similar_case_study"],
        "estimated_open_rate": "38% (above segment avg)",
        "saved_to": "HubSpot Drafts",
    }


async def schedule_followup(args: Dict[str, Any]) -> Dict[str, Any]:
    await asyncio.sleep(0.5)
    return {
        "scheduled": True,
        "task_type": args.get("task_type", "Follow-up call"),
        "assigned_to": args.get("owner", "Sarah Chen"),
        "due_date": "2026-04-14T10:00:00Z",
        "reminder": "24h before",
        "task_id": f"TASK-{random.randint(1000, 9999)}",
        "calendar_invite_sent": True,
    }


# ---------------------------------------------------------------------------
# Operations tools
# ---------------------------------------------------------------------------

async def invoice_analyzer(args: Dict[str, Any]) -> Dict[str, Any]:
    await asyncio.sleep(1.0)
    amount   = args.get("amount", random.randint(8000, 45000))
    vendor   = args.get("vendor", "Cloudtech Solutions")
    category = "Software & Subscriptions" if "tech" in vendor.lower() else "Professional Services"
    flagged  = amount > 10000
    return {
        "invoice_id": f"INV-{random.randint(10000, 99999)}",
        "vendor": vendor,
        "amount": amount,
        "currency": "USD",
        "category": category,
        "due_date": "2026-04-30",
        "flagged_for_review": flagged,
        "flag_reason": "Exceeds $10,000 auto-approval threshold" if flagged else None,
        "duplicate_check": "No duplicate found",
        "budget_line": "Q2 Engineering Budget — 68% utilized",
        "recommended_action": "Route to CFO approval" if flagged else "Auto-approve",
    }


async def ticket_classifier(args: Dict[str, Any]) -> Dict[str, Any]:
    await asyncio.sleep(0.8)
    ticket_text = args.get("text", "Login not working, urgent customer demo in 2 hours")
    priority    = random.choice(["P1 — Critical", "P2 — High", "P2 — High"])
    return {
        "ticket_id": f"JIRA-{random.randint(1000, 9999)}",
        "priority": priority,
        "category": "Authentication / Access",
        "sentiment": "Frustrated",
        "keywords_detected": ["login", "urgent", "customer demo"],
        "similar_past_tickets": 14,
        "avg_resolution_time": "1.8 hours",
        "suggested_team": "Platform Engineering",
        "auto_reply_drafted": True,
    }


async def priority_router(args: Dict[str, Any]) -> Dict[str, Any]:
    await asyncio.sleep(0.6)
    priority = args.get("priority", "P2 — High")
    team     = args.get("team", "Platform Engineering")
    return {
        "routed": True,
        "assigned_to": "Marcus Webb",
        "team": team,
        "escalation_path": "Marcus Webb → Team Lead → VP Engineering" if "P1" in priority else f"Marcus Webb → {team} Lead",
        "sla_deadline": "2026-04-09T18:00:00Z",
        "routing_reason": f"On-call engineer for {team} with lowest current queue",
        "notification_sent": True,
    }


async def approval_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
    await asyncio.sleep(1.3)
    amount   = args.get("amount", 18500)
    approver = args.get("approver", "CFO")
    return {
        "workflow_id": f"APPR-{random.randint(1000, 9999)}",
        "status": "pending_approval",
        "approver": approver,
        "amount": amount,
        "approval_request_sent": True,
        "channels": ["Email", "Slack DM"],
        "deadline": "2026-04-11T17:00:00Z",
        "auto_reminder": "24h before deadline",
        "audit_trail": f"AUDIT-{random.randint(10000, 99999)}",
    }


async def status_updater(args: Dict[str, Any]) -> Dict[str, Any]:
    await asyncio.sleep(0.5)
    system     = args.get("system", "Jira")
    new_status = args.get("status", "In Review")
    return {
        "updated": True,
        "system": system,
        "record_id": args.get("record_id", f"JIRA-{random.randint(1000, 9999)}"),
        "previous_status": "Open",
        "new_status": new_status,
        "updated_by": "Aura Automation",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "webhook_triggered": True,
    }


async def notify_team(args: Dict[str, Any]) -> Dict[str, Any]:
    team    = args.get("team", "Operations")
    message = args.get("message", "Action completed — see details in dashboard")
    channel = f"#{team.lower().replace(' ', '-')}"
    text    = f"*Aura Agent* | {channel}\n{message}"
    sent    = await asyncio.get_event_loop().run_in_executor(None, lambda: _post_slack(text))
    if not sent:
        await asyncio.sleep(0.5)
    return {
        "sent": True,
        "real_slack": sent,
        "team": team,
        "channel": channel,
        "message_preview": message[:80],
        "recipients": random.randint(4, 12),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

BUSINESS_TOOL_REGISTRY: Dict[str, Any] = {
    # Sales & CRM
    "lead_scorer":      lead_scorer,
    "crm_lookup":       crm_lookup,
    "crm_update":       crm_update,
    "slack_notify":     slack_notify,
    "email_draft":      email_draft,
    "schedule_followup": schedule_followup,
    # Operations
    "invoice_analyzer": invoice_analyzer,
    "ticket_classifier": ticket_classifier,
    "priority_router":  priority_router,
    "approval_workflow": approval_workflow,
    "status_updater":   status_updater,
    "notify_team":      notify_team,
}


async def call_business_tool(tool_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    fn = BUSINESS_TOOL_REGISTRY.get(tool_id)
    if not fn:
        raise ValueError(f"Unknown business tool: {tool_id}")
    return await fn(args)
