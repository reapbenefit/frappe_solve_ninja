import frappe
from frappe.utils import nowdate
from samaaja.api.common import custom_response

from solve_ninja.api.v1.ninja_query_utils import (
	DEFAULT_DAYS,
	build_dashboard_export_download,
	build_export_download,
	build_org_dashboard_export_sections,
	build_org_ninjas_xlsx_rows,
	build_pagination,
	fetch_organization_aggregates,
	fetch_organization_dashboard_stats,
	fetch_organization_ninjas,
	fetch_skills_breakdown_for_org,
	fetch_skills_unlocked_count_by_org,
	fetch_top_action_types_for_org,
	fetch_top_ninjas_by_org,
	merge_org_stats,
	normalize_export_format,
	parse_list_params,
	parse_organization_request,
	resolve_organization_filters,
	sanitize_filename,
)


def _build_organization_results(page_length, start, days, filters):
	org_rows, total_count = fetch_organization_aggregates(page_length, start, days, filters)
	org_ids = [row.org_id for row in org_rows if row.org_id]
	skills_map = fetch_skills_unlocked_count_by_org(org_ids)
	top_map = fetch_top_ninjas_by_org(org_ids, days)
	result = merge_org_stats(org_rows, skills_map, top_map)
	return result, total_count


def _build_organization_dashboard_data(days, filters):
	filters = resolve_organization_filters(filters, require_organization=True)
	organization = filters.get("organization")

	stats = fetch_organization_dashboard_stats(filters, days)
	skills_unlocked, remaining_skills_count = fetch_skills_breakdown_for_org(
		filters,
		total_ninjas=stats.get("total_ninjas", 0),
	)
	top_action_types = fetch_top_action_types_for_org(filters)
	org_name = frappe.db.get_value("User Organization", organization, "org_name") or organization

	return {
		"org_id": organization,
		"org_name": org_name,
		"stats": stats,
		"skills_unlocked": skills_unlocked,
		"remaining_skills_count": remaining_skills_count,
		"top_action_types": top_action_types,
		"days": days,
		"applied_filters": filters,
	}


@frappe.whitelist()
def get_organization_stats(page_length=10, start=0, days=DEFAULT_DAYS, filters=None):
	"""
	Get organization-wise ninja statistics grouped by User Metadata.org_id.

	Supports GET (query params) and POST (JSON body). POST body overrides query params.

	Args:
	- page_length: Number of organizations per page (default: 10)
	- start: Pagination offset (default: 0)
	- days: Rolling window for active ninjas and top-10 action count (default: 30)
	- filters: dict or JSON string; optional {"organization": "<User Organization name>"}

	GET example:
	/api/method/solve_ninja.api.v1.organization.get_organization_stats?page_length=10&days=30

	POST example:
	{"page_length": 10, "start": 0, "days": 30, "filters": {"organization": "..."}}
	"""
	try:
		params = parse_organization_request(
			defaults={"page_length": page_length, "start": start, "days": days, "filters": filters},
			page_length=page_length,
			start=start,
			days=days,
			filters=filters,
		)
		page_length, start, days, filters = parse_list_params(
			params.get("page_length", 10),
			params.get("start", 0),
			params.get("days", DEFAULT_DAYS),
			params.get("filters"),
		)
		filters = resolve_organization_filters(filters, require_organization=False)
		result, total_count = _build_organization_results(page_length, start, days, filters)

		return custom_response(
			message="Organization statistics retrieved successfully",
			data={
				"result": result,
				"pagination": build_pagination(total_count, page_length, start),
				"filters": {
					"days": days,
					"applied_filters": filters,
				},
			},
			status_code=200,
			error=None,
		)
	except frappe.PermissionError as e:
		return custom_response(
			message=str(e),
			data=None,
			status_code=403,
			error=str(e),
		)
	except Exception as e:
		frappe.log_error(title="get_organization_stats failed", message=frappe.get_traceback())
		return custom_response(
			message="Failed to retrieve organization statistics",
			data=None,
			status_code=500,
			error=str(e),
		)


@frappe.whitelist()
def export_organization_stats(days=DEFAULT_DAYS, filters=None, format="excel"):
	"""
	Export organization dashboard data as Excel, CSV, or PDF.

	Requires filters.organization (User Organization name). Exports summary stats,
	skills unlocked, and top action types for the scoped organization.

	Supports GET (query params) and POST (JSON body). POST body overrides query params.
	format: excel (default), csv, or pdf
	Filename: SolveNinjas_{PartnerName}_{YYYY-MM-DD}.{xlsx|csv|pdf}

	POST example:
	{"days": 30, "filters": {"organization": "..."}, "format": "pdf"}
	"""
	try:
		params = parse_organization_request(
			defaults={"days": days, "filters": filters, "format": format},
			days=days,
			filters=filters,
			format=format,
		)
		_, _, days, filters = parse_list_params(
			0, 0, params.get("days", DEFAULT_DAYS), params.get("filters")
		)
		export_format = normalize_export_format(params.get("format", "excel"))
		dashboard_data = _build_organization_dashboard_data(days, filters)
		sections = build_org_dashboard_export_sections(dashboard_data)
		org_name = sanitize_filename(dashboard_data.get("org_name"))
		filename = f"SolveNinjas_{org_name}_{nowdate()}"
		build_dashboard_export_download(
			sections,
			filename,
			export_format=export_format,
			title=f"SolveNinjas {dashboard_data.get('org_name')}",
		)
	except (frappe.PermissionError, frappe.ValidationError):
		raise
	except Exception as e:
		frappe.log_error(title="export_organization_stats failed", message=frappe.get_traceback())
		frappe.throw("Download failed. Please try again.")


@frappe.whitelist()
def get_organization_dashboard(days=DEFAULT_DAYS, filters=None):
	"""
	Get single-organization dashboard data for partner UI.

	Requires filters.organization (User Organization name). All metrics are scoped
	to users where User Metadata.org_id matches that organization.

	Supports GET (query params) and POST (JSON body). POST body overrides query params.

	POST example:
	{"days": 30, "filters": {"organization": "Jal Jeevan Mission Assam"}}
	"""
	try:
		params = parse_organization_request(
			defaults={"days": days, "filters": filters},
			days=days,
			filters=filters,
		)
		_, _, days, filters = parse_list_params(
			0, 0, params.get("days", DEFAULT_DAYS), params.get("filters")
		)
		dashboard_data = _build_organization_dashboard_data(days, filters)

		return custom_response(
			message="Organization dashboard retrieved successfully",
			data={
				"org_id": dashboard_data["org_id"],
				"org_name": dashboard_data["org_name"],
				"stats": dashboard_data["stats"],
				"skills_unlocked": dashboard_data["skills_unlocked"],
				"remaining_skills_count": dashboard_data["remaining_skills_count"],
				"top_action_types": dashboard_data["top_action_types"],
				"meta": {
					"days": dashboard_data["days"],
					"applied_filters": dashboard_data["applied_filters"],
				},
			},
			status_code=200,
			error=None,
		)
	except frappe.PermissionError as e:
		return custom_response(
			message=str(e),
			data=None,
			status_code=403,
			error=str(e),
		)
	except frappe.ValidationError as e:
		return custom_response(
			message=str(e),
			data=None,
			status_code=400,
			error=str(e),
		)
	except Exception as e:
		frappe.log_error(title="get_organization_dashboard failed", message=frappe.get_traceback())
		return custom_response(
			message="Failed to retrieve organization dashboard",
			data=None,
			status_code=500,
			error=str(e),
		)


@frappe.whitelist()
def export_organization_ninjas(
	filters=None,
	sort_by="total_actions",
	sort_order="desc",
	format="excel",
):
	"""
	Export ninja rows for a scoped organization as Excel, CSV, or PDF.

	Supports GET (query params) and POST (JSON body). POST body overrides query params.
	Requires filters.organization (User Organization name).
	format: excel (default), csv, or pdf
	Filename: SolveNinjas_{PartnerName}_{YYYY-MM-DD}.{xlsx|csv|pdf}

	POST example:
	{"filters": {"organization": "..."}, "sort_by": "total_actions", "sort_order": "desc", "format": "csv"}
	"""
	try:
		params = parse_organization_request(
			defaults={
				"filters": filters,
				"sort_by": sort_by,
				"sort_order": sort_order,
				"format": format,
			},
			filters=filters,
			sort_by=sort_by,
			sort_order=sort_order,
			format=format,
		)
		_, _, _, filters = parse_list_params(0, 0, 0, params.get("filters"))
		filters = resolve_organization_filters(filters, require_organization=True)
		export_format = normalize_export_format(params.get("format", "excel"))
		sort_by = params.get("sort_by", "total_actions")
		sort_order = params.get("sort_order", "desc")
		organization = filters.get("organization")

		ninja_rows = fetch_organization_ninjas(filters, sort_by=sort_by, sort_order=sort_order)
		rows = build_org_ninjas_xlsx_rows(ninja_rows)
		org_name = sanitize_filename(organization)
		filename = f"SolveNinjas_{org_name}_{nowdate()}"
		build_export_download(
			rows,
			filename,
			sheet_name="Ninjas",
			export_format=export_format,
			title=f"SolveNinjas {organization}",
		)
	except (frappe.PermissionError, frappe.ValidationError):
		raise
	except Exception as e:
		frappe.log_error(title="export_organization_ninjas failed", message=frappe.get_traceback())
		frappe.throw("Download failed. Please try again.")
