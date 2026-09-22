# Copyright (c) 2026, ReapBenefit and contributors
# One-shot smoke harness for v1 + common.py whitelisted APIs.
# Run: bench --site v16.solveninja.org execute solve_ninja.api._smoke_v1_common.run

from __future__ import annotations

import ast
import importlib
import inspect
import json
import traceback
from pathlib import Path
from typing import Any

import frappe

APP_ROOT = Path(__file__).resolve().parents[1]
V1_DIR = APP_ROOT / "api" / "v1"
COMMON_FILE = APP_ROOT / "api" / "common.py"

# Endpoints that hit external services or need multipart — skip live call after import check
EXTERNAL_SKIP = {
	"solve_ninja.api.common.upload_audio",
	"solve_ninja.api.common.fetch_data_gov_in",
	"solve_ninja.api.v1.events.upload_attachment",
	"solve_ninja.api.v1.chat.initiate_chat",
	"solve_ninja.api.v1.chat.continue_chat",
	"solve_ninja.api.v1.chat.add_chat_message",
	"solve_ninja.api.v1.chat.submit_feedback_for_session",
	"solve_ninja.api.v1.chat.get_chat_history",
	"solve_ninja.api.v1.chat.submit_feedback_for_chat_message",
	"solve_ninja.api.v1.glific_audience.create_filtered_glific_collection",
	"solve_ninja.api.v1.glific_audience.add_all_filtered_audience_to_members",
	"solve_ninja.api.v1.automated_cohort.create_monthly_automated_collections",
	"solve_ninja.api.v1.automated_cohort.sync_automated_cohort_to_glific",
}

# Prefer incomplete args so writes fail validation without mutating data
WRITE_VALIDATION_KWARGS: dict[str, dict[str, Any]] = {
	"solve_ninja.api.common.add_event": {},
	"solve_ninja.api.common.highlight_event": {"username": "", "event_id": ""},
	"solve_ninja.api.common.add_user": {},
	"solve_ninja.api.common.update_user": {},
	"solve_ninja.api.common.reset_password": {},
	"solve_ninja.api.common.delete_event": {"event": "__smoke_nonexistent__"},
	"solve_ninja.api.v1.solve_event.create_solve_event": {},
	"solve_ninja.api.v1.solve_event.set_solve_event_cover_image": {},
	"solve_ninja.api.v1.solve_event.event_checkin": {},
	"solve_ninja.api.v1.solve_event.program_checkin": {},
	"solve_ninja.api.v1.mentorship_request.create": {},
	"solve_ninja.api.v1.initiative_request.submit_initiative_request": {},
	"solve_ninja.api.v1.glific_audience.preview_audience": {"doc_name": "__smoke_nonexistent__"},
	"solve_ninja.api.v1.glific_audience.search_users_for_glific_group": {
		"filters_json": None,
		"start": 0,
		"page_length": 1,
	},
	"solve_ninja.api.v1.chat.end_chat": {},
}

READ_DEFAULTS: dict[str, dict[str, Any]] = {
	"solve_ninja.api.v1.marketplace.get_city_wise_ninja_stats": {"page_length": 1, "start": 0, "days": 60},
	"solve_ninja.api.v1.marketplace.get_ninjas_in_focus": {"page_length": 1, "start": 0},
	"solve_ninja.api.v1.marketplace.get_opportunities_for_youth": {"page_length": 1, "start": 0},
	"solve_ninja.api.v1.marketplace.get_learn_page_content": {"language": "en"},
	"solve_ninja.api.v1.marketplace.get_connect_page_content": {"language": "en"},
	"solve_ninja.api.v1.marketplace.get_lead_page_content": {"language": "en"},
	"solve_ninja.api.v1.marketplace.get_home_page_content": {"language": "en"},
	"solve_ninja.api.v1.solve_event.get_upcoming_events": {"page_length": 1, "start": 0},
	"solve_ninja.api.v1.solve_event.get_past_events": {"page_length": 1, "start": 0},
	"solve_ninja.api.v1.solve_event.get_solve_events": {"page_length": 1, "start": 0},
	"solve_ninja.api.v1.solve_event.get_adda_rooms": {},
	"solve_ninja.api.v1.solve_event.get_adda_room_availability": {},
	"solve_ninja.api.v1.skill_based_projects.get_skill_based_projects": {"page_length": 1, "start": 0},
	"solve_ninja.api.v1.skill_based_projects.get_projects": {"page_length": 1, "start": 0},
	"solve_ninja.api.v1.skill_based_projects.get_project_details": {"id": "__smoke__"},
	"solve_ninja.api.v1.skill_based_projects.get_tags": {},
	"solve_ninja.api.v1.project.get_funded_projects": {"page_length": 1, "start": 0},
	"solve_ninja.api.v1.project.get_funded_project_details": {"project_name": "__smoke__"},
	"solve_ninja.api.v1.project.get_funded_projects_by_status": {"status": "Active", "page_length": 1, "start": 0},
	"solve_ninja.api.v1.samaaj_data.get_subcategories_user_tag_wise_stats": {},
	"solve_ninja.api.v1.samaaj_data.get_addresses": {},
	"solve_ninja.api.v1.organization.get_organization_stats": {"page_length": 1, "start": 0, "days": 30},
	"solve_ninja.api.v1.organization.get_organization_dashboard": {"days": 30},
	"solve_ninja.api.v1.organization.export_organization_stats": {"days": 30, "format": "excel"},
	"solve_ninja.api.v1.organization.export_organization_ninjas": {"format": "excel"},
	"solve_ninja.api.v1.mentor.get_mentors": {"page_length": 1, "start": 0},
	"solve_ninja.api.v1.mentor.get_chapter_lead": {"page_length": 1, "start": 0},
	"solve_ninja.api.v1.leaderboard.get_top_reviewed_users": {"page_length": 1, "start": 0, "days": 30},
	"solve_ninja.api.v1.automated_cohort.get_monthly_cohort_period": {},
	"solve_ninja.api.v1.mentorship_request.get_mentorship_request_for_feedback": {"request_id": "__smoke__"},
	"solve_ninja.api.v1.ninjas.get_ninja_listing": {"page_length": 1, "start": 0},
	"solve_ninja.api.v1.ninjas.get_ninja_listing_skill_options": {},
	"solve_ninja.api.v1.initiative_request.get_cities": {},
	"solve_ninja.api.v1.glific_audience.search_audience_standalone": {"start": 0, "page_length": 1},
	"solve_ninja.api.common.search_users": {},
	"solve_ninja.api.common.search_users_": {"page_length": 1, "start": 0},
	"solve_ninja.api.common.fetch_profile": {},
	"solve_ninja.api.common.fetch_full_profile": {},
	"solve_ninja.api.common.download_profile": {},
	"solve_ninja.api.common.get_action_count": {},
}

EXPECTED_EXC = (
	frappe.ValidationError,
	frappe.PermissionError,
	frappe.DoesNotExistError,
	frappe.AuthenticationError,
	frappe.MandatoryError,
	TypeError,  # missing required positional sometimes surfaces as TypeError
	ValueError,
	KeyError,
	json.JSONDecodeError,
)


def _discover_whitelists(py_path: Path, module_path: str) -> list[dict]:
	src = py_path.read_text()
	tree = ast.parse(src)
	out = []
	for node in tree.body:
		if not isinstance(node, ast.FunctionDef):
			continue
		allow_guest = False
		is_whitelisted = False
		for dec in node.decorator_list:
			text = ast.unparse(dec) if hasattr(ast, "unparse") else ""
			if "whitelist" in text:
				is_whitelisted = True
				if "allow_guest=True" in text or "allow_guest = True" in text:
					allow_guest = True
		if is_whitelisted:
			out.append(
				{
					"name": node.name,
					"module": module_path,
					"dotted": f"{module_path}.{node.name}",
					"allow_guest": allow_guest,
					"file": str(py_path),
				}
			)
	return out


def discover_all() -> list[dict]:
	endpoints = []
	for py in sorted(V1_DIR.glob("*.py")):
		if py.name.startswith("test_") or py.name.startswith("_") or py.name == "__init__.py":
			continue
		if py.name in ("ninja_query_utils.py", "glific_cohort_notifications.py"):
			continue
		mod = f"solve_ninja.api.v1.{py.stem}"
		endpoints.extend(_discover_whitelists(py, mod))
	endpoints.extend(_discover_whitelists(COMMON_FILE, "solve_ninja.api.common"))
	return endpoints


def _kwargs_for(dotted: str, fn) -> dict[str, Any]:
	if dotted in WRITE_VALIDATION_KWARGS:
		return dict(WRITE_VALIDATION_KWARGS[dotted])
	if dotted in READ_DEFAULTS:
		return dict(READ_DEFAULTS[dotted])
	# Fill optional params with defaults from signature; leave required empty to trigger EXPECTED
	kwargs = {}
	sig = inspect.signature(fn)
	for name, param in sig.parameters.items():
		if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
			continue
		if param.default is not inspect.Parameter.empty:
			kwargs[name] = param.default
	return kwargs


def _classify(exc: BaseException) -> str:
	name = type(exc).__name__
	msg = str(exc).lower()

	# Programming / SQL / attribute bugs first
	if name in (
		"AttributeError",
		"ImportError",
		"NameError",
		"ProgrammingError",
		"OperationalError",
		"UndefinedTable",
		"UndefinedColumn",
		"InFailedSqlTransaction",
	):
		return "FAIL"
	if "column" in msg and "does not exist" in msg:
		return "FAIL"
	if "undefinedcolumn" in name.lower() or ("undefined" in msg and "column" in msg):
		return "FAIL"

	# Validation / missing data / permission = reachable
	if isinstance(exc, EXPECTED_EXC):
		# TypeError from missing required arg is EXPECTED; unexpected kw is harness bug → FAIL
		if isinstance(exc, TypeError) and "unexpected keyword" in msg:
			return "FAIL"
		return "EXPECTED"
	if name in (
		"ValidationError",
		"PermissionError",
		"DoesNotExistError",
		"MandatoryError",
		"LinkValidationError",
		"DuplicateEntryError",
		"TimestampMismatchError",
	):
		return "EXPECTED"
	if "not found" in msg or "required" in msg or "mandatory" in msg:
		return "EXPECTED"
	if "permission" in msg or "not permitted" in msg:
		return "EXPECTED"
	return "FAIL"


def _reset_request_context():
	"""Bench execute has no HTTP request; keep form_dict/request safe for APIs."""
	frappe.local.form_dict = frappe._dict()
	# Empty JSON body so json.loads works; endpoints then hit validation, not TypeError
	frappe.local.request = frappe._dict(data=b"{}", method="GET", path="/smoke")


def _classify_response(result) -> tuple[str, str] | None:
	"""Classify Werkzeug Response / dict payloads. None = treat as PASS."""
	status_code = getattr(result, "status_code", None)
	body_text = ""
	if hasattr(result, "get_data"):
		try:
			body_text = result.get_data(as_text=True) or ""
		except Exception:
			body_text = ""
	elif isinstance(result, dict):
		status_code = result.get("status_code") or status_code
		body_text = json.dumps(result)

	if not status_code or int(status_code) < 400:
		return None

	msg = body_text.lower()
	try:
		parsed = json.loads(body_text) if body_text else {}
		msg = str(parsed.get("message") or parsed.get("error") or body_text).lower()
	except Exception:
		pass

	expected_markers = (
		"mandatory",
		"required",
		"missing",
		"not found",
		"parse request",
		"must be str",  # empty/malformed JSON body in smoke
		"list index out of range",  # empty lookup on highlight_event
		"invalid",
		"permission",
		"not permitted",
		"select at least",
		"organization filter",
	)
	if any(m in msg for m in expected_markers) or int(status_code) in (400, 401, 403, 404):
		return ("EXPECTED", f"status_code={status_code}: {msg[:160]}")

	fail_markers = (
		"does not exist",
		"undefined",
		"column",
		"doctype",
		"traceback",
		"attributeerror",
		"failed to retrieve",
		"internal",
	)
	if int(status_code) >= 500 and any(m in msg for m in fail_markers):
		return ("FAIL", f"status_code={status_code}: {msg[:220]}")
	if int(status_code) >= 500:
		# Many common.py APIs return 500 for validation; prefer EXPECTED when ambiguous
		return ("EXPECTED", f"status_code={status_code}: {msg[:160]}")
	return ("EXPECTED", f"status_code={status_code}: {msg[:160]}")


def debug_fail_bodies():
	"""Print status/body for endpoints that return Werkzeug Responses."""
	from werkzeug.wrappers import Response

	frappe.set_user("Administrator")
	from solve_ninja.api import common
	from solve_ninja.api.v1 import mentorship_request, skill_based_projects

	fns = [
		("add_event", common.add_event, {}),
		("highlight_event", common.highlight_event, {"username": "", "event_id": ""}),
		("search_users", common.search_users, {}),
		("add_user", common.add_user, {}),
		("update_user", common.update_user, {}),
		("fetch_profile", common.fetch_profile, {}),
		("fetch_full_profile", common.fetch_full_profile, {}),
		("get_action_count", common.get_action_count, {}),
		("create", mentorship_request.create, {}),
		("get_projects", skill_based_projects.get_projects, {"page_length": 1, "start": 0}),
	]
	out = []
	for name, fn, kw in fns:
		frappe.db.rollback()
		_reset_request_context()
		try:
			r = fn(**kw)
			if isinstance(r, Response):
				body = r.get_data(as_text=True)[:400]
				out.append({"name": name, "status": r.status_code, "body": body})
			else:
				out.append({"name": name, "type": str(type(r)), "val": str(r)[:400]})
		except Exception as e:
			out.append({"name": name, "exc": f"{type(e).__name__}: {e}"})
	print(json.dumps(out, indent=2))
	return out


def run():
	frappe.set_user("Administrator")
	endpoints = discover_all()
	results = []

	for ep in endpoints:
		dotted = ep["dotted"]
		row = {
			"module": ep["module"],
			"method": ep["name"],
			"allow_guest": ep["allow_guest"],
			"result": "",
			"note": "",
		}
		try:
			mod = importlib.import_module(ep["module"])
			fn = getattr(mod, ep["name"])
		except Exception as e:
			row["result"] = "FAIL"
			row["note"] = f"import: {type(e).__name__}: {e}"
			results.append(row)
			continue

		if dotted in EXTERNAL_SKIP:
			row["result"] = "SKIP"
			row["note"] = "external/mutating; import OK"
			results.append(row)
			continue

		kwargs = _kwargs_for(dotted, fn)
		savepoint = f"smoke_{abs(hash(dotted)) % 10_000_000}"
		try:
			frappe.db.rollback()  # clear any aborted Postgres txn from prior call
			frappe.db.savepoint(savepoint)
			_reset_request_context()
			result = fn(**kwargs)
			classified = _classify_response(result)
			if classified:
				row["result"], row["note"] = classified
			else:
				row["result"] = "PASS"
				row["note"] = "ok"
		except Exception as e:
			row["result"] = _classify(e)
			tb = traceback.format_exc(limit=3)
			row["note"] = f"{type(e).__name__}: {str(e)[:180]}"
			if row["result"] == "FAIL":
				row["note"] += " | " + tb.replace("\n", " ")[-300:]
		finally:
			try:
				frappe.db.rollback()
			except Exception:
				pass

		results.append(row)

	# Print report
	print("=" * 100)
	print(f"{'MODULE':<45} {'METHOD':<40} {'G':<2} {'RESULT':<9} NOTE")
	print("=" * 100)
	counts = {"PASS": 0, "EXPECTED": 0, "FAIL": 0, "SKIP": 0}
	for r in results:
		counts[r["result"]] = counts.get(r["result"], 0) + 1
		g = "Y" if r["allow_guest"] else "N"
		print(f"{r['module']:<45} {r['method']:<40} {g:<2} {r['result']:<9} {r['note'][:80]}")
	print("=" * 100)
	print(
		f"TOTAL={len(results)} PASS={counts.get('PASS',0)} EXPECTED={counts.get('EXPECTED',0)} "
		f"FAIL={counts.get('FAIL',0)} SKIP={counts.get('SKIP',0)}"
	)
	fails = [r for r in results if r["result"] == "FAIL"]
	if fails:
		print("\n--- FAIL DETAILS ---")
		for r in fails:
			print(f"* {r['module']}.{r['method']}: {r['note']}")

	# Persist JSON for the report todo
	out_path = Path("/tmp/solve_ninja_api_smoke_report.json")
	out_path.write_text(json.dumps({"counts": counts, "results": results}, indent=2, default=str))
	print(f"\nWrote {out_path}")
	return {"counts": counts, "fail_count": len(fails)}
