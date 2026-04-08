# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

"""
Profile summary service: builds user portfolio from Events + Energy Point Log,
generates AI summary via ai_manager, and updates User Metadata.
"""

import asyncio
import json
import frappe
from datetime import datetime
from solve_ninja.services.ai_manager import _load_prompt, run_llm_responses_with_instructor, AIManager
from solve_ninja.models.ai import ProfileSummaryOutput
from solve_ninja.api.profile import _build_user_portfolio

PROFILE_SUMMARY_SYSTEM_PROMPT = _load_prompt("profile_summary.md")

def generate_profile_summary(user_name: str) -> str:
    """
    Generate AI summary for user from their portfolio.
    Returns summary string; raises on error.
    """
    if not user_name or not frappe.db.exists("User", user_name):
        return ""

    profile = _build_user_portfolio(user_name)
    if not profile.actions:
        return ""

    messages = [
        {"role": "system", "content": PROFILE_SUMMARY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"user name: {profile.first_name}\n"
                f"total hours invested: {profile.total_hours_invested}\n"
                f"total number of actions: {profile.total_actions}\n"
                f"today's date: {datetime.now().strftime('%Y-%m-%d')}\n"
                f"all_actions: {json.dumps(profile.model_dump()['actions'])}"
            ),
        },
    ]

    response = asyncio.run(run_llm_responses_with_instructor(
        input=messages,
        response_model=ProfileSummaryOutput,
        temperature=AIManager.TEMPERATURE,
    ))
    return response.summary