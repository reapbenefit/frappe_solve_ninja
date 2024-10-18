import frappe
from solve_ninja.api.user import get_ninjas
from solve_ninja.api.leaderboard import get_active_ninja_count, get_total_invested_hours
from solve_ninja.utils import human_format


sitemap = 1
no_cache = 1

def get_context(context):
	context.whatsapp_bot_url = frappe.db.get_single_value("Solve Ninja Settings", "whatsapp_bot_url")
	context.total_invested_hours = human_format(get_total_invested_hours())
	context.active_ninja_count = human_format(get_active_ninja_count())
	context.users = []