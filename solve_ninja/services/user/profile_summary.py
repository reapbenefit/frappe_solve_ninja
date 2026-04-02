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

def generate_profile_summary(user_name: str) -> str:
    """
    Generate AI summary for user from their portfolio.
    Returns summary string; raises on error.
    """
    if not user_name or not frappe.db.exists("User", user_name):
        return ""

    from solve_ninja.api.profile import get_user_actions, get_skill_assignment_log

    user_doc = frappe.db.get_value("User", user_name, ["first_name"], as_dict=True)
    first_name = (user_doc and user_doc.get("first_name")) or ""

    actions_raw, _ = get_user_actions(user_name)

    skills_by_event = {}
    for log in get_skill_assignment_log(user_name):
        ref = log.get("reference_name")
        if ref not in skills_by_event:
            skills_by_event[ref] = []
        skills_by_event[ref].append({
            "name": log.get("badge") or "",
            "label": log.get("badge") or "",
            "relevance": log.get("reason") or "",
        })

    actions = []
    total_hours_invested = 0
    for action in actions_raw:
        actions.append({
            "title": action.get("title") or "",
            "description": (action.get("description") or "")[:500],
            "hours_invested": float(action.get("hours_invested") or 0),
            "category": action.get("category") or "",
            "type": action.get("type") or "",
            "skills": skills_by_event.get(action.get("event_id"), []),
        })
        total_hours_invested += actions[-1]["hours_invested"]

    if not actions:
        return ""

    messages = [
        {"role": "system", "content": PROFILE_SUMMARY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"user name: {first_name}\n"
                f"total hours invested: {total_hours_invested}\n"
                f"total number of actions: {len(actions)}\n"
                f"today's date: {datetime.now().strftime('%Y-%m-%d')}\n"
                f"all_actions: {str(actions)}"
            ),
        },
    ]

    response = asyncio.run(run_llm_responses_with_instructor(
        input=messages,
        response_model=ProfileSummaryOutput,
        temperature=AIManager.TEMPERATURE,
    ))
    return response.summary