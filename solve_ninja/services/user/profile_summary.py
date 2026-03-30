# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

"""
Profile summary service: builds user portfolio from Events + Energy Point Log,
generates AI summary via ai_manager, and updates User Metadata.
"""

import asyncio
import frappe
from datetime import datetime
from solve_ninja.services.ai_manager import _load_prompt, run_llm_responses_with_instructor, AIManager
from solve_ninja.models.ai import ProfileSummaryOutput

PROFILE_SUMMARY_SYSTEM_PROMPT = _load_prompt("profile_summary.md")

def get_user_portfolio(user: str) -> dict:
    """
    Build portfolio from profile.get_user_actions (Events) + Energy Point Log (skills).
    Uses same event source as get_user_profile API.
    """
    if not user or not frappe.db.exists("User", user):
        return {"first_name": "", "actions": []}

    from solve_ninja.api.profile import get_user_actions

    user_doc = frappe.db.get_value("User", user, ["first_name"], as_dict=True)
    first_name = (user_doc and user_doc.get("first_name")) or ""

    # Use same events source as profile API (get_user_profile)
    actions_raw, _ = get_user_actions(user)

    # Get Energy Point Logs for skills (badge, reason) per event
    eps = frappe.get_all(
        "Energy Point Log",
        filters={
            "user": user,
            "type": "Auto",
            "reverted": 0,
            "reference_doctype": "Events",
        },
        fields=["reference_name", "badge", "reason"],
    )
    skills_by_event = {}
    for ep in eps:
        ref = ep.get("reference_name")
        if ref not in skills_by_event:
            skills_by_event[ref] = []
        skills_by_event[ref].append({
            "name": ep.get("badge") or "",
            "label": ep.get("badge") or "",
            "relevance": ep.get("reason") or "",
        })

    # Build user_portfolio.actions to match cmp_backend / get_user_profile structure
    actions = []
    total_hours_invested = 0
    for action in actions_raw:
        action_skills = [
            {"name": s["name"], "label": s["label"], "relevance": s["relevance"]}
            for s in skills_by_event.get(action.get("event_id"), [])
        ]
        actions.append({
            "title": action.get("title") or "",
            "description": (action.get("description") or "")[:500],
            "hours_invested": float(action.get("hours_invested") or 0),
            "category": action.get("category") or "",
            "type": action.get("type") or "",
            "skills": action_skills,
        })
        total_hours_invested += actions[-1]["hours_invested"]

    return {
        "first_name": first_name,
        "actions": actions,
        "total_hours_invested": total_hours_invested,
        "total_actions": len(actions),
    }

def generate_profile_summary(user_name: str) -> str:
    """
    Generate AI summary for user from their portfolio.
    Returns summary string; raises on error.
    """
    profile = get_user_portfolio(user_name)
    if not profile.get("actions"):
        return ""

    messages = [
        {"role": "system", "content": PROFILE_SUMMARY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"user name: {profile.get('first_name', '')}\n"
                f"total hours invested: {profile['total_hours_invested']}\n"
                f"total number of actions: {profile['total_actions']}\n"
                f"today's date: {datetime.now().strftime('%Y-%m-%d')}\n"
                f"all_actions: {str(profile['actions'])}"
            ),
        },
    ]

    response = asyncio.run(run_llm_responses_with_instructor(
        input=messages,
        response_model=ProfileSummaryOutput,
        temperature=AIManager.TEMPERATURE,
    ))
    return response.summary