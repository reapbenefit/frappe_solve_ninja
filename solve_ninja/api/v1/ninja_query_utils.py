import json
from collections import defaultdict
from datetime import timedelta

import frappe
from frappe.query_builder import Case, DocType, Order
from frappe.query_builder.functions import Coalesce, Count, Sum
from frappe.utils import cint, now_datetime

EXCLUDED_ORGS = ["RBINT", "Reap Benefit Team", "Reap Benefit SNLA program"]
DEFAULT_DAYS = 30
TOP_NINJAS_LIMIT = 10
DASHBOARD_SKILLS_LIMIT = 5
DASHBOARD_ACTION_TYPES_LIMIT = 10

SKILL_BAR_COLORS = {
	"Data orientation": "#1A56DB",
	"Communication": "#7C3AED",
	"Critical thinking": "#0F766E",
	"Leadership": "#D97706",
	"Problem solving": "#DC2626",
}
DEFAULT_SKILL_BAR_COLOR = "#6B7280"

ORGANISATION_MANAGER_ROLE = "Organisation Manager"
SYSTEM_MANAGER_ROLE = "System Manager"


def get_ninja_doctypes():
	User = DocType("User")
	NinjaProfile = DocType("Ninja Profile")
	UserMetadata = DocType("User Metadata")
	UserOrganization = DocType("User Organization")
	Events = DocType("Events")
	EnergyPointLog = DocType("Energy Point Log")
	Badge = DocType("Badge")
	return User, NinjaProfile, UserMetadata, UserOrganization, Events, EnergyPointLog, Badge


def parse_list_params(page_length=10, start=0, days=DEFAULT_DAYS, filters=None):
	if isinstance(filters, dict):
		parsed_filters = filters
	elif filters:
		parsed_filters = json.loads(filters)
	else:
		parsed_filters = {}
	return (
		cint(page_length),
		cint(start),
		cint(days),
		parsed_filters,
	)


def parse_organization_request(defaults=None, **kwargs):
	"""
	Merge POST JSON body with function kwargs / form_dict.
	POST body wins when the same key is present in both.
	"""
	params = dict(defaults or {})

	for key, value in kwargs.items():
		if value is not None:
			params[key] = value

	if getattr(frappe, "request", None) and frappe.request.method == "POST" and frappe.request.data:
		body = json.loads(frappe.request.data)
		if isinstance(body, dict):
			for key, value in body.items():
				if value is not None:
					params[key] = value

	if "filters" in params:
		filters = params["filters"]
		if isinstance(filters, dict):
			pass
		elif isinstance(filters, str) and filters.strip():
			params["filters"] = json.loads(filters)
		else:
			params["filters"] = {}

	for key in ("sort_by", "sort_order"):
		if key in params and isinstance(params[key], str):
			params[key] = params[key].strip()

	return params


def get_action_date_threshold(days):
	time_condition = now_datetime() - timedelta(days=cint(days))
	return frappe.utils.format_datetime(time_condition, "yyyy-MM-dd HH:mm:ss")


def normalize_organization_filter(organization):
	"""
	Normalize organization scope for listing/dashboard APIs.

	Matches User Organization name stored on User Metadata.org_id (same value as
	filters.organization on get_organization_dashboard).
	"""
	if organization is None:
		return ""
	return str(organization).strip()


def resolve_organization_filters(filters=None, require_organization=False):
	"""
	Enforce role-based organization access for organization APIs.

	- System Manager: any org; optional filters.organization unless require_organization
	- Organisation Manager: forced to User Metadata.org_id for session user
	- Guest / other roles: denied
	"""
	from frappe import _

	if frappe.session.user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	filters = dict(filters or {})
	roles = set(frappe.get_roles(frappe.session.user))

	if SYSTEM_MANAGER_ROLE in roles:
		if require_organization and not normalize_organization_filter(filters.get("organization")):
			frappe.throw(_("Organization filter is required"), frappe.ValidationError)
		return filters

	if ORGANISATION_MANAGER_ROLE in roles:
		user_org = frappe.db.get_value("User Metadata", frappe.session.user, "org_id")
		if not user_org:
			frappe.throw(_("No organization assigned to your account"), frappe.PermissionError)

		requested = normalize_organization_filter(filters.get("organization"))
		if requested and requested != user_org:
			frappe.throw(_("Not permitted to access other organization data"), frappe.PermissionError)

		filters["organization"] = user_org
		return filters

	frappe.throw(_("Not permitted"), frappe.PermissionError)


def ninja_base_conditions(User, UserMetadata, filters=None):
	filters = filters or {}
	conditions = (
		(User.enabled == 1)
		& (UserMetadata.org_id.isnotnull())
		& (UserMetadata.org_id != "")
		& (UserMetadata.publish_status == "Publish")
	)
	if filters.get("organization"):
		conditions = conditions & (UserMetadata.org_id == filters["organization"])
	elif not filters.get("include_excluded_orgs"):
		conditions = conditions & (UserMetadata.org_id.notin(EXCLUDED_ORGS))
	return conditions


def apply_ninja_user_joins(query, User, NinjaProfile, UserMetadata, UserOrganization=None):
	query = (
		query.join(NinjaProfile).on(User.name == NinjaProfile.name)
		.join(UserMetadata).on(User.name == UserMetadata.name)
	)
	if UserOrganization is not None:
		query = query.left_join(UserOrganization).on(UserMetadata.org_id == UserOrganization.name)
	return query


def build_profile_url(username):
	base = frappe.conf.get("cmp_base_url") or frappe.utils.get_url()
	return f"{base}/user-profile/{username}"


def build_pagination(total_count, page_length, start):
	return {
		"total_count": total_count,
		"page_length": page_length,
		"start": start,
		"has_next": (start + page_length) < total_count,
		"has_prev": start > 0,
	}


def get_skill_badge_names():
	cache_key = "solve_ninja:skill_badge_names"
	cached = frappe.cache().get_value(cache_key)
	if cached is not None:
		return cached

	badge_names = frappe.get_all(
		"Badge",
		filters=[["_user_tags", "like", "%skill%"]],
		pluck="name",
	)
	frappe.cache().set_value(cache_key, badge_names, expires_in_sec=3600)
	return badge_names


def _org_stats_base_query(User, NinjaProfile, UserMetadata, UserOrganization, filters):
	query = frappe.qb.from_(User)
	query = apply_ninja_user_joins(query, User, NinjaProfile, UserMetadata, UserOrganization)
	return query.where(ninja_base_conditions(User, UserMetadata, filters))


def fetch_organization_aggregates(page_length, start, days, filters):
	User, NinjaProfile, UserMetadata, UserOrganization, *_ = get_ninja_doctypes()
	threshold_str = get_action_date_threshold(days)
	active_case = Sum(
		Case().when(NinjaProfile.last_action_date >= threshold_str, 1).else_(0)
	)

	query = (
		_org_stats_base_query(User, NinjaProfile, UserMetadata, UserOrganization, filters)
		.select(
			UserMetadata.org_id.as_("org_id"),
			Coalesce(UserOrganization.org_name, UserMetadata.org_id).as_("org_name"),
			Count(User.name).as_("user_count"),
			Coalesce(Sum(NinjaProfile.contributions), 0).as_("total_actions"),
			active_case.as_("active_ninjas_30_days"),
		)
		.groupby(UserMetadata.org_id, UserOrganization.org_name)
		.orderby(Coalesce(Sum(NinjaProfile.contributions), 0), order=Order.desc)
		.limit(page_length)
		.offset(start)
	)

	count_query = (
		_org_stats_base_query(User, NinjaProfile, UserMetadata, UserOrganization, filters)
		.select(UserMetadata.org_id)
		.groupby(UserMetadata.org_id)
	)

	rows = query.run(as_dict=True)
	count_result = count_query.run()
	total_count = len(count_result) if count_result else 0
	return rows, total_count


def fetch_all_organization_aggregates(days, filters):
	User, NinjaProfile, UserMetadata, UserOrganization, *_ = get_ninja_doctypes()
	threshold_str = get_action_date_threshold(days)
	active_case = Sum(
		Case().when(NinjaProfile.last_action_date >= threshold_str, 1).else_(0)
	)

	query = (
		_org_stats_base_query(User, NinjaProfile, UserMetadata, UserOrganization, filters)
		.select(
			UserMetadata.org_id.as_("org_id"),
			Coalesce(UserOrganization.org_name, UserMetadata.org_id).as_("org_name"),
			Count(User.name).as_("user_count"),
			Coalesce(Sum(NinjaProfile.contributions), 0).as_("total_actions"),
			active_case.as_("active_ninjas_30_days"),
		)
		.groupby(UserMetadata.org_id, UserOrganization.org_name)
		.orderby(Coalesce(Sum(NinjaProfile.contributions), 0), order=Order.desc)
	)
	return query.run(as_dict=True)


def fetch_skills_unlocked_count_by_org(org_ids):
	if not org_ids:
		return {}

	skill_badges = get_skill_badge_names()
	if not skill_badges:
		return {org_id: 0 for org_id in org_ids}

	User, NinjaProfile, UserMetadata, _UserOrganization, *_ = get_ninja_doctypes()
	UserBadge = DocType("User badge")

	rows = (
		frappe.qb.from_(User)
		.join(NinjaProfile).on(User.name == NinjaProfile.name)
		.join(UserMetadata).on(User.name == UserMetadata.name)
		.join(UserBadge).on(UserBadge.user == User.name)
		.select(
			UserMetadata.org_id.as_("org_id"),
			Count(User.name).distinct().as_("skills_unlocked_ninja_count"),
		)
		.where(
			(User.enabled == 1)
			& (UserMetadata.org_id.isin(org_ids))
			& (UserBadge.active == 1)
			& (UserBadge.badge.isin(skill_badges))
		)
		.groupby(UserMetadata.org_id)
		.run(as_dict=True)
	)

	result = {org_id: 0 for org_id in org_ids}
	for row in rows:
		result[row.org_id] = row.skills_unlocked_ninja_count or 0
	return result


def fetch_top_ninjas_by_org(org_ids, days, limit=TOP_NINJAS_LIMIT):
	if not org_ids:
		return {}

	User, NinjaProfile, UserMetadata, _UserOrganization, Events, *_ = get_ninja_doctypes()
	threshold_str = get_action_date_threshold(days)

	rows = (
		frappe.qb.from_(User)
		.join(NinjaProfile).on(User.name == NinjaProfile.name)
		.join(UserMetadata).on(User.name == UserMetadata.name)
		.join(Events).on(
			(User.name == Events.user) & (Events.date_of_action >= threshold_str)
		)
		.select(
			UserMetadata.org_id.as_("org_id"),
			User.full_name,
			User.username,
			Count(Events.name).as_("action_count"),
		)
		.where(
			(User.enabled == 1)
			& (UserMetadata.org_id.isin(org_ids))
			& (UserMetadata.publish_status == "Publish")
		)
		.groupby(UserMetadata.org_id, User.name, User.full_name, User.username)
		.orderby(Count(Events.name), order=Order.desc)
		.run(as_dict=True)
	)

	top_map = defaultdict(list)
	for row in rows:
		org_id = row.org_id
		if len(top_map[org_id]) >= limit:
			continue
		top_map[org_id].append({
			"full_name": row.full_name,
			"action_count": row.action_count or 0,
			"profile_url": build_profile_url(row.username),
		})
	return dict(top_map)


def merge_org_stats(org_rows, skills_map, top_map):
	result = []
	for row in org_rows:
		user_count = row.user_count or 0
		total_actions = row.total_actions or 0
		avg_actions = round(total_actions / user_count, 2) if user_count else 0
		org_id = row.org_id
		result.append({
			"org_id": org_id,
			"org_name": row.org_name,
			"user_count": user_count,
			"total_actions": total_actions,
			"avg_actions_per_ninja": avg_actions,
			"active_ninjas_30_days": row.active_ninjas_30_days or 0,
			"skills_unlocked_ninja_count": skills_map.get(org_id, 0),
			"top_active_ninjas": top_map.get(org_id, []),
		})
	return result


def get_skill_bar_color(skill_name):
	if not skill_name:
		return DEFAULT_SKILL_BAR_COLOR
	return SKILL_BAR_COLORS.get(skill_name, DEFAULT_SKILL_BAR_COLOR)


def _energy_point_log_skill_conditions(EnergyPointLog):
	return (
		(EnergyPointLog.type == "Auto")
		& (EnergyPointLog.reverted == 0)
		& (EnergyPointLog.reference_doctype == "Events")
		& (EnergyPointLog.badge.isnotnull())
	)


def fetch_organization_dashboard_stats(filters, days):
	User, NinjaProfile, UserMetadata, UserOrganization, _Events, *_ = get_ninja_doctypes()
	threshold_str = get_action_date_threshold(days)
	active_case = Sum(
		Case().when(NinjaProfile.last_action_date >= threshold_str, 1).else_(0)
	)
	ninjas_taking_actions = Sum(
		Case().when(NinjaProfile.contributions > 0, 1).else_(0)
	)

	rows = (
		_org_stats_base_query(User, NinjaProfile, UserMetadata, UserOrganization, filters)
		.select(
			Count(User.name).as_("total_ninjas"),
			ninjas_taking_actions.as_("ninjas_taking_actions"),
			Coalesce(Sum(NinjaProfile.hours_invested), 0).as_("total_hours_logged"),
			Coalesce(Sum(NinjaProfile.contributions), 0).as_("total_actions"),
			active_case.as_("active_ninjas_last_30_days"),
		)
		.run(as_dict=True)
	)

	row = rows[0] if rows else {}
	total_ninjas = row.get("total_ninjas") or 0
	total_actions = row.get("total_actions") or 0
	avg_actions = round(total_actions / total_ninjas, 2) if total_ninjas else 0

	return {
		"total_ninjas": total_ninjas,
		"ninjas_taking_actions": row.get("ninjas_taking_actions") or 0,
		"total_actions": total_actions,
		"total_hours_logged": round(row.get("total_hours_logged") or 0, 2),
		"avg_actions_per_ninja": avg_actions,
		"active_ninjas_last_30_days": row.get("active_ninjas_last_30_days") or 0,
	}


def fetch_skills_breakdown_for_org(filters, total_ninjas=0, limit=DASHBOARD_SKILLS_LIMIT):
	User, NinjaProfile, UserMetadata, _UserOrganization, _Events, EnergyPointLog, Badge = get_ninja_doctypes()
	epl_conditions = _energy_point_log_skill_conditions(EnergyPointLog)

	skill_rows = (
		_org_stats_base_query(User, NinjaProfile, UserMetadata, None, filters)
		.join(EnergyPointLog).on(EnergyPointLog.user == User.name)
		.join(Badge).on(EnergyPointLog.badge == Badge.name)
		.select(
			Coalesce(Badge.title, EnergyPointLog.badge).as_("skill_name"),
			Count(User.name).distinct().as_("ninjas_with_skill"),
		)
		.where(epl_conditions)
		.groupby(Coalesce(Badge.title, EnergyPointLog.badge))
		.orderby(Count(User.name).distinct(), order=Order.desc)
		.run(as_dict=True)
	)

	total_skill_count = len(skill_rows)
	top_skills = skill_rows[:limit]
	skills_unlocked = []
	for skill_row in top_skills:
		skill_name = skill_row.skill_name
		skills_unlocked.append({
			"skill_name": skill_name,
			"ninjas_with_skill": skill_row.ninjas_with_skill or 0,
			"total_ninjas": total_ninjas,
			"bar_color": get_skill_bar_color(skill_name),
		})

	remaining_skills_count = max(total_skill_count - len(top_skills), 0)
	return skills_unlocked, remaining_skills_count


def fetch_top_action_types_for_org(filters, limit=DASHBOARD_ACTION_TYPES_LIMIT):
	User, NinjaProfile, UserMetadata, _UserOrganization, Events, *_ = get_ninja_doctypes()

	rows = (
		_org_stats_base_query(User, NinjaProfile, UserMetadata, None, filters)
		.join(Events).on(User.name == Events.user)
		.select(
			Events.type.as_("action_type"),
			Count(Events.name).as_("action_count"),
		)
		.where(Events.type.isnotnull())
		.groupby(Events.type)
		.orderby(Count(Events.name), order=Order.desc)
		.limit(limit)
		.run(as_dict=True)
	)

	return [
		{
			"rank": index,
			"action_type": row.action_type,
			"action_count": row.action_count or 0,
		}
		for index, row in enumerate(rows, start=1)
	]


def fetch_user_skills_map(user_names):
	if not user_names:
		return {}

	skill_badges = get_skill_badge_names()
	if not skill_badges:
		return {user: [] for user in user_names}

	UserBadge = DocType("User badge")
	Badge = DocType("Badge")

	rows = (
		frappe.qb.from_(Badge)
		.join(UserBadge).on(UserBadge.badge == Badge.name)
		.select(UserBadge.user, Badge.title)
		.where(
			(UserBadge.user.isin(user_names))
			& (UserBadge.active == 1)
			& (Badge.name.isin(skill_badges))
		)
		.run(as_dict=True)
	)

	skills_map = defaultdict(list)
	for row in rows:
		if row.title:
			skills_map[row.user].append(row.title)
	return {user: skills_map.get(user, []) for user in user_names}


NINJA_LISTING_VIEW = "vw_ninja_listing"

ORG_NINJA_SORT_COLUMNS = {
	"total_actions": "contributions",
	"ninja_name": "full_name",
	"city": "city",
	"last_active": "last_action_date",
	"hours": "hours_invested",
}


def _build_org_ninja_order_clause(sort_by, sort_order):
	column = ORG_NINJA_SORT_COLUMNS.get(sort_by, "contributions")
	direction = "ASC" if sort_order == "asc" else "DESC"

	if sort_by == "last_active":
		return f"{column} IS NULL, {column} {direction}, full_name ASC"

	if sort_by == "ninja_name":
		return f"{column} {direction}"

	return f"{column} {direction}, full_name ASC"


def fetch_organization_ninjas(filters, sort_by="total_actions", sort_order="desc"):
	organization = (filters or {}).get("organization")
	if not organization:
		return []

	sort_by = sort_by or "total_actions"
	sort_order = sort_order if sort_order in ("asc", "desc") else "desc"
	sql_sort_by = "total_actions" if sort_by == "skills_count" else sort_by
	order_clause = _build_org_ninja_order_clause(sql_sort_by, sort_order)

	raw_rows = frappe.db.sql(
		f"""
		SELECT
			user_id,
			full_name,
			username,
			city,
			org_id,
			contributions,
			hours_invested,
			last_action_date
		FROM `{NINJA_LISTING_VIEW}`
		WHERE org_id = %s
		ORDER BY {order_clause}
		""",
		(organization,),
		as_dict=True,
	)

	rows = [
		{
			"name": row.user_id,
			"full_name": row.full_name,
			"username": row.username,
			"city": row.city,
			"org_id": row.org_id,
			"contributions": row.contributions,
			"hours_invested": row.hours_invested,
			"last_action_date": row.last_action_date,
		}
		for row in raw_rows
	]

	if sort_by == "skills_count":
		user_names = [row["name"] for row in rows]
		skills_map = fetch_user_skills_map(user_names)
		for row in rows:
			row["skills_count"] = len(skills_map.get(row["name"], []))
		reverse = sort_order != "asc"
		rows.sort(key=lambda row: row.get("skills_count", 0), reverse=reverse)

	skills_map = fetch_user_skills_map([row["name"] for row in rows])
	for row in rows:
		row["skills"] = skills_map.get(row["name"], [])
		row["profile_url"] = build_profile_url(row["username"])
	return rows


def sanitize_filename(value):
	return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in (value or "export"))


def build_org_stats_xlsx_rows(org_results):
	header = [
		"Organization ID",
		"Organization Name",
		"Total Ninjas",
		"Total Actions",
		"Avg Actions Per Ninja",
		"Active Ninjas (30 Days)",
		"Skills Unlocked Ninja Count",
	]
	rows = [header]
	for org in org_results:
		rows.append([
			org.get("org_id"),
			org.get("org_name"),
			org.get("user_count"),
			org.get("total_actions"),
			org.get("avg_actions_per_ninja"),
			org.get("active_ninjas_30_days"),
			org.get("skills_unlocked_ninja_count"),
		])
	return rows


SUPPORTED_EXPORT_FORMATS = {"excel", "csv", "pdf"}


def normalize_export_format(value):
	from frappe import _

	export_format = (value or "excel").strip().lower()
	if export_format not in SUPPORTED_EXPORT_FORMATS:
		frappe.throw(
			_("Unsupported export format. Use one of: {0}").format(
				", ".join(sorted(SUPPORTED_EXPORT_FORMATS))
			),
			frappe.ValidationError,
		)
	return export_format


def _escape_html(value):
	return (
		str(value or "")
		.replace("&", "&amp;")
		.replace("<", "&lt;")
		.replace(">", "&gt;")
		.replace('"', "&quot;")
	)


def build_rows_html_table(rows, title=None):
	title_html = f"<h2>{_escape_html(title)}</h2>" if title else ""
	if not rows:
		return f"<html><body>{title_html}<p>No data available.</p></body></html>"

	header, *data_rows = rows
	header_html = "".join(f"<th>{_escape_html(cell)}</th>" for cell in header)
	body_html = "".join(
		"<tr>"
		+ "".join(f"<td>{_escape_html(cell)}</td>" for cell in row)
		+ "</tr>"
		for row in data_rows
	)
	return f"""
	<html>
	<head>
		<meta charset="utf-8">
		<style>
			body {{ font-family: Arial, sans-serif; font-size: 10px; }}
			table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
			th, td {{ border: 1px solid #ccc; padding: 4px 6px; text-align: left; word-wrap: break-word; }}
			th {{ background: #f3f4f6; font-size: 9px; }}
		</style>
	</head>
	<body>
		{title_html}
		<table>
			<thead><tr>{header_html}</tr></thead>
			<tbody>{body_html}</tbody>
		</table>
	</body>
	</html>
	"""


def build_rows_html_document(sections, title=None):
	title_html = f"<h1>{_escape_html(title)}</h1>" if title else ""
	section_html = []
	for section_title, rows in sections.items():
		if not rows:
			continue
		header, *data_rows = rows
		header_html = "".join(f"<th>{_escape_html(cell)}</th>" for cell in header)
		body_html = "".join(
			"<tr>"
			+ "".join(f"<td>{_escape_html(cell)}</td>" for cell in row)
			+ "</tr>"
			for row in data_rows
		)
		section_html.append(
			f"<h2>{_escape_html(section_title)}</h2>"
			f"<table><thead><tr>{header_html}</tr></thead>"
			f"<tbody>{body_html}</tbody></table>"
		)
	return f"""
	<html>
	<head>
		<meta charset="utf-8">
		<style>
			body {{ font-family: Arial, sans-serif; font-size: 10px; }}
			table {{ border-collapse: collapse; width: 100%; table-layout: fixed; margin-bottom: 16px; }}
			th, td {{ border: 1px solid #ccc; padding: 4px 6px; text-align: left; word-wrap: break-word; }}
			th {{ background: #f3f4f6; font-size: 9px; }}
			h1 {{ font-size: 16px; margin: 0 0 12px; }}
			h2 {{ font-size: 13px; margin: 20px 0 8px; }}
		</style>
	</head>
	<body>
		{title_html}
		{"".join(section_html)}
	</body>
	</html>
	"""


def _provide_binary_download(filename, extension, content, content_type):
	frappe.local.response.filename = f"{filename}.{extension}"
	frappe.local.response.filecontent = content
	frappe.local.response.type = "download"
	frappe.local.response.content_type = content_type
	frappe.local.response.display_content_as = "attachment"


def build_xlsx_download(data, filename, sheet_name="Export"):
	from frappe.utils.xlsxutils import make_xlsx

	_provide_binary_download(
		filename,
		"xlsx",
		make_xlsx(data, sheet_name).getvalue(),
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
	)


def build_pdf_download(rows, filename, title=None):
	from frappe.utils.pdf import get_pdf

	html = build_rows_html_table(rows, title=title)
	pdf_options = {
		"orientation": "Landscape",
		"page-size": "A4",
		"margin-top": "10mm",
		"margin-right": "10mm",
		"margin-bottom": "10mm",
		"margin-left": "10mm",
	}
	pdf_content = get_pdf(html, pdf_options)
	if isinstance(pdf_content, str):
		pdf_content = pdf_content.encode("latin-1")

	frappe.local.response.filename = f"{filename}.pdf"
	frappe.local.response.filecontent = pdf_content
	frappe.local.response.type = "download"
	frappe.local.response.content_type = "application/pdf"
	frappe.local.response.display_content_as = "attachment"


def build_export_download(rows, filename, sheet_name="Export", export_format="excel", title=None):
	from frappe.utils.csvutils import to_csv
	from frappe.utils.xlsxutils import make_xlsx

	export_format = normalize_export_format(export_format)

	if export_format == "excel":
		_provide_binary_download(
			filename,
			"xlsx",
			make_xlsx(rows, sheet_name).getvalue(),
			"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
		)
	elif export_format == "csv":
		_provide_binary_download(
			filename,
			"csv",
			to_csv(rows).encode("utf-8"),
			"text/csv",
		)
	else:
		build_pdf_download(rows, filename, title=title)


def build_org_dashboard_summary_rows(dashboard_data):
	stats = dashboard_data.get("stats") or {}
	days = dashboard_data.get("days", DEFAULT_DAYS)
	return [
		["Metric", "Value"],
		["Organization", dashboard_data.get("org_name")],
		["Organization ID", dashboard_data.get("org_id")],
		["Reporting Window (days)", days],
		["Total Ninjas", stats.get("total_ninjas")],
		["Ninjas Taking Actions", stats.get("ninjas_taking_actions")],
		["Total Actions", stats.get("total_actions")],
		["Total Hours Logged", stats.get("total_hours_logged")],
		["Avg Actions Per Ninja", stats.get("avg_actions_per_ninja")],
		[f"Active Ninjas (Last {days} Days)", stats.get("active_ninjas_last_30_days")],
		["Remaining Skills Count", dashboard_data.get("remaining_skills_count")],
	]


def build_org_dashboard_skills_rows(skills_unlocked):
	rows = [["Skill Name", "Ninjas With Skill", "Total Ninjas"]]
	for skill in skills_unlocked or []:
		rows.append([
			skill.get("skill_name"),
			skill.get("ninjas_with_skill"),
			skill.get("total_ninjas"),
		])
	return rows


def build_org_dashboard_action_types_rows(top_action_types):
	rows = [["Rank", "Action Type", "Action Count"]]
	for item in top_action_types or []:
		rows.append([
			item.get("rank"),
			item.get("action_type"),
			item.get("action_count"),
		])
	return rows


def build_org_dashboard_export_sections(dashboard_data):
	return {
		"Summary": build_org_dashboard_summary_rows(dashboard_data),
		"Skills Unlocked": build_org_dashboard_skills_rows(dashboard_data.get("skills_unlocked")),
		"Top Action Types": build_org_dashboard_action_types_rows(dashboard_data.get("top_action_types")),
	}


def _build_multisheet_xlsx(sections):
	from io import BytesIO

	import openpyxl

	wb = openpyxl.Workbook(write_only=True)
	for sheet_name, rows in sections.items():
		ws = wb.create_sheet(title=sheet_name[:31])
		for row in rows:
			ws.append(list(row))
	buf = BytesIO()
	wb.save(buf)
	return buf.getvalue()


def _build_sectioned_csv(sections):
	from frappe.utils.csvutils import to_csv

	csv_rows = []
	for section_title, rows in sections.items():
		if csv_rows:
			csv_rows.append([])
		csv_rows.append([section_title])
		csv_rows.extend(rows)
	return to_csv(csv_rows).encode("utf-8")


def build_dashboard_export_download(sections, filename, export_format="excel", title=None):
	from frappe.utils.pdf import get_pdf

	export_format = normalize_export_format(export_format)

	if export_format == "excel":
		_provide_binary_download(
			filename,
			"xlsx",
			_build_multisheet_xlsx(sections),
			"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
		)
	elif export_format == "csv":
		_provide_binary_download(
			filename,
			"csv",
			_build_sectioned_csv(sections),
			"text/csv",
		)
	else:
		html = build_rows_html_document(sections, title=title)
		pdf_options = {
			"orientation": "Landscape",
			"page-size": "A4",
			"margin-top": "10mm",
			"margin-right": "10mm",
			"margin-bottom": "10mm",
			"margin-left": "10mm",
		}
		pdf_content = get_pdf(html, pdf_options)
		if isinstance(pdf_content, str):
			pdf_content = pdf_content.encode("latin-1")
		frappe.local.response.filename = f"{filename}.pdf"
		frappe.local.response.filecontent = pdf_content
		frappe.local.response.type = "download"
		frappe.local.response.content_type = "application/pdf"
		frappe.local.response.display_content_as = "attachment"


def _profile_url_xlsx_cell(profile_url):
	if not profile_url:
		return ""
	escaped = str(profile_url).replace('"', '""')
	return f'=HYPERLINK("{escaped}", "View Profile")'


def build_org_ninjas_xlsx_rows(ninja_rows):
	header = [
		"Rank",
		"Ninja Name",
		"City",
		"Last Action Date",
		"Hours",
		"Total Actions",
		"Skills",
		"Profile URL",
	]
	rows = [header]
	for rank, ninja in enumerate(ninja_rows, start=1):
		rows.append([
			rank,
			ninja.get("full_name"),
			ninja.get("city"),
			ninja.get("last_action_date"),
			ninja.get("hours_invested"),
			ninja.get("contributions"),
			", ".join(ninja.get("skills") or []),
			_profile_url_xlsx_cell(ninja.get("profile_url")),
		])
	return rows
