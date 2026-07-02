import frappe
from collections import defaultdict
from frappe.utils import cint, flt, format_datetime, get_datetime, add_days, nowdate
from samaaja.api.common import custom_response

from solve_ninja.api.v1.ninja_query_utils import normalize_organization_filter

VIEW_NAME = "vw_ninja_listing"
DEFAULT_PAGE_LENGTH = 20
MAX_PAGE_LENGTH = 100
SKILL_LIMIT = 3
ACTIVE_TIME_OPTIONS = {"", "all", "7d", "30d"}

# Whitelist of sort keys → SQL column expressions (view column names only).
SORT_COLUMNS = {
	"last_active": "last_action_date",
	"hours": "hours_invested",
	"total_actions": "contributions",
	"name": "full_name",
}

# Legacy prefixed sort_by values → (sort_by, sort_order).
LEGACY_SORT_PREFIX = {
	"-hours": ("hours", "asc"),
	"-total_actions": ("total_actions", "asc"),
	"-name": ("name", "desc"),
	"-last_active": ("last_active", "asc"),
}


@frappe.whitelist(allow_guest=True)
def get_ninja_listing(
	page_length=None,
	start=0,
	sort_by="last_active",
	sort_order=None,
	search=None,
	city=None,
	has_actions_only=False,
	skills=None,
	active_time=None,
	organization=None,
):
	"""
	Public ninja directory backed by vw_ninja_listing with server-side filters,
	sorting, pagination, and top skill names loaded per page.
	"""
	try:
		page_length = min(cint(page_length) or DEFAULT_PAGE_LENGTH, MAX_PAGE_LENGTH)
		start = cint(start)
		sort_by, sort_order = _normalize_sort(sort_by, sort_order)
		has_actions_only = _parse_bool(has_actions_only)
		skill_titles = _parse_skills(skills)
		active_time = (active_time or "all").strip().lower()
		if active_time not in ACTIVE_TIME_OPTIONS:
			active_time = "all"
		if active_time == "all":
			active_time = ""

		organization = normalize_organization_filter(organization)

		where_clause, params = _build_filters(
			search=search,
			city=city,
			has_actions_only=has_actions_only,
			skill_titles=skill_titles,
			active_time=active_time,
			organization=organization,
		)
		order_clause = _build_order_clause(sort_by, sort_order)

		rows = frappe.db.sql(
			f"""
			SELECT
				user_id,
				full_name,
				username,
				user_image,
				city,
				contributions,
				hours_invested,
				last_action_date
			FROM `{VIEW_NAME}`
			WHERE {where_clause}
			ORDER BY {order_clause}
			LIMIT %s OFFSET %s
			""",
			[*params, page_length, start],
			as_dict=True,
		)

		stats = frappe.db.sql(
			f"""
			SELECT
				COUNT(*) AS total_count,
				COALESCE(SUM(hours_invested), 0) AS total_hours
			FROM `{VIEW_NAME}`
			WHERE {where_clause}
			""",
			params,
			as_dict=True,
		)[0]
		total_count = cint(stats.total_count)
		total_hours = flt(stats.total_hours)

		user_ids = [row.user_id for row in rows]
		skills_map = _get_top_skills_for_users(user_ids, limit=SKILL_LIMIT)

		result = []
		for row in rows:
			result.append(
				{
					"full_name": row.full_name,
					"username": row.username,
					"profile_url": _profile_url(row.username),
					"user_image": _absolute_url(row.user_image),
					"city": row.city or "",
					"last_active": _format_last_action_date(row.last_action_date),
					"last_active_raw": row.last_action_date,
					"hours_invested": flt(row.hours_invested),
					"total_actions": cint(row.contributions),
					"skills": skills_map.get(row.user_id, []),
				}
			)

		return custom_response(
			message="Ninja listing retrieved successfully",
			data={
				"result": result,
				"pagination": {
					"total_count": total_count,
					"page_length": page_length,
					"start": start,
					"has_next": (start + page_length) < total_count,
					"has_prev": start > 0,
				},
				"aggregates": {
					"total_hours": total_hours,
				},
				"filters": {
					"search": search or "",
					"city": city or "",
					"sort_by": sort_by,
					"sort_order": sort_order,
					"has_actions_only": bool(has_actions_only),
					"skills": skill_titles,
					"active_time": active_time or "all",
					"organization": organization,
				},
			},
			status_code=200,
			error=None,
		)
	except Exception as e:
		frappe.log_error(f"Error in get_ninja_listing: {e}", "Ninja Listing API")
		return custom_response(
			message="Failed to retrieve ninja listing",
			data=None,
			status_code=500,
			error=str(e),
		)


@frappe.whitelist(allow_guest=True)
def get_ninja_listing_skill_options():
	"""Skill badge titles available for directory filtering."""
	try:
		skills = frappe.get_all(
			"Badge",
			filters=[["_user_tags", "like", "%skill%"]],
			fields=["name", "title"],
			order_by="title asc",
		)
		return custom_response(
			message="Skill filter options retrieved successfully",
			data={"skills": skills},
			status_code=200,
			error=None,
		)
	except Exception as e:
		frappe.log_error(f"Error in get_ninja_listing_skill_options: {e}", "Ninja Listing API")
		return custom_response(
			message="Failed to retrieve skill filter options",
			data=None,
			status_code=500,
			error=str(e),
		)


def _normalize_sort(sort_by, sort_order):
	"""Normalize sort_by / sort_order, including legacy prefixed sort_by values."""
	sort_by = (sort_by or "last_active").strip()
	sort_order = (sort_order or "").strip().lower()

	if sort_by in LEGACY_SORT_PREFIX:
		sort_by, sort_order = LEGACY_SORT_PREFIX[sort_by]

	if sort_by not in SORT_COLUMNS:
		sort_by = "last_active"

	if sort_order not in ("asc", "desc"):
		sort_order = "desc" if sort_by != "name" else "asc"

	return sort_by, sort_order


def _build_order_clause(sort_by, sort_order):
	"""
	Build a SQL ORDER BY clause from whitelisted columns only.

	NULL last_active: NULLs are always sorted last (both asc and desc) via
	``column IS NULL`` as the first sort key.
	"""
	column = SORT_COLUMNS[sort_by]
	direction = sort_order.upper()

	if sort_by == "last_active":
		# NULLs last regardless of asc/desc.
		return f"{column} IS NULL, {column} {direction}, full_name ASC"

	if sort_by == "name":
		return f"{column} {direction}"

	return f"{column} {direction}, full_name ASC"


def _parse_bool(value):
	value = frappe.parse_json(value)
	if isinstance(value, str):
		return value.lower() in ("1", "true", "yes")
	return bool(value)


def _parse_skills(skills):
	if not skills:
		return []
	if isinstance(skills, str):
		return [item.strip() for item in skills.split(",") if item.strip()]
	if isinstance(skills, (list, tuple)):
		return [str(item).strip() for item in skills if str(item).strip()]
	return []


def _build_filters(
	search=None,
	city=None,
	has_actions_only=False,
	skill_titles=None,
	active_time=None,
	organization=None,
):
	conditions = ["1=1"]
	params = []
	skill_titles = skill_titles or []

	if organization:
		# Same scope as get_organization_dashboard: User Metadata.org_id.
		conditions.append("org_id = %s")
		params.append(organization)

	if search:
		term = f"%{search.strip().lower()}%"
		conditions.append("(LOWER(full_name) LIKE %s OR LOWER(username) LIKE %s)")
		params.extend([term, term])

	if city:
		conditions.append("city = %s")
		params.append(city.strip())

	if has_actions_only:
		conditions.append("contributions > 0")

	if active_time in ("7d", "30d"):
		days = 7 if active_time == "7d" else 30
		conditions.append("last_action_date >= %s")
		params.append(add_days(nowdate(), -days))

	if skill_titles:
		placeholders = ", ".join(["%s"] * len(skill_titles))
		conditions.append(
			f"""
			user_id IN (
				SELECT DISTINCT ub.user
				FROM `tabUser badge` ub
				INNER JOIN `tabBadge` b ON b.name = ub.badge
				WHERE ub.active = 1
					AND b._user_tags LIKE %s
					AND b.title IN ({placeholders})
			)
			"""
		)
		params.append("%skill%")
		params.extend(skill_titles)

	return " AND ".join(conditions), params


def _profile_url(username):
	if not username:
		return ""
	if frappe.conf.get("cmp_base_url"):
		return f"{frappe.conf.get('cmp_base_url')}/user-profile/{username}"
	return frappe.utils.get_url(f"/user-profile/{username}")


def _absolute_url(path):
	if not path:
		return None
	if path.startswith(("http://", "https://")):
		return path
	return frappe.utils.get_url(path)


def _format_last_action_date(value):
	if not value:
		return ""
	return format_datetime(get_datetime(value), "d MMM yyyy, h:mm a")


def _get_top_skills_for_users(user_ids, limit=SKILL_LIMIT):
	if not user_ids:
		return {}

	skill_badge_names = frappe.get_all(
		"Badge",
		filters=[["_user_tags", "like", "%skill%"]],
		pluck="name",
	)
	if not skill_badge_names:
		return {user_id: [] for user_id in user_ids}

	user_badges = frappe.get_all(
		"User badge",
		filters={
			"user": ["in", user_ids],
			"active": 1,
			"badge": ["in", skill_badge_names],
		},
		fields=["user", "badge", "badge_count"],
	)

	if not user_badges:
		return {user_id: [] for user_id in user_ids}

	badge_names = list({row.badge for row in user_badges})
	badge_titles = {
		row.name: row.title
		for row in frappe.get_all(
			"Badge",
			filters={"name": ["in", badge_names]},
			fields=["name", "title"],
		)
	}

	grouped = defaultdict(list)
	for row in sorted(
		user_badges,
		key=lambda item: (-cint(item.badge_count), item.badge or ""),
	):
		if len(grouped[row.user]) >= limit:
			continue
		title = badge_titles.get(row.badge)
		if title:
			grouped[row.user].append(title)

	return {user_id: grouped.get(user_id, []) for user_id in user_ids}
