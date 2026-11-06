"""
Website check-in with the shared unique code (Program, Solve Event, Social Media).

The same code that the WhatsApp bot uses for program / event check-in can be passed to
the website as ?code=<unique_id>. After signup or OTP login, apply_unique_code() records
the same effects as the bot check-ins:

- Program: set the user's organisation and create Program Participation.
- Solve Event: create Registration (unless ignore_reg) and Participation, inside the
  check-in window only.
- Social Media: acquisition tracking only.

Acquisition source is recorded only for new users so existing users keep their first source.
"""

import re

import frappe
from frappe.utils import now_datetime

from solve_ninja.utils import get_doc_by_unique_id

WEB_CHECKIN_PATH = "/checkin"
# Marketplace SPA route where website users land after a code-link login
WEB_CHECKIN_LANDING = "/#/quick-add"
WEB_REGISTRATION_SOURCE = "Web Form"
# Staff accounts: changing their org would move Organisation Manager permissions.
ORG_LOCKED_ROLES = ("Organisation Manager", "System Manager")

_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,63}$")

_TITLE_FIELDS = {
	"Program": "program_name",
	"Solve Event": "title",
	"Social Media": "campaign_name",
}


def normalize_code(code):
	"""Return the code in upper case, or None if it is empty or malformed."""
	if not code:
		return None
	code = str(code).strip().upper()
	if not _CODE_PATTERN.match(code):
		return None
	return code


def resolve_unique_code(code):
	"""
	Return {"code", "doctype", "name", "title"} for a unique code, or None if unknown.
	"""
	code = normalize_code(code)
	if not code:
		return None

	target = get_doc_by_unique_id(code)
	if not target:
		return None

	title_field = _TITLE_FIELDS.get(target["doctype"])
	title = frappe.db.get_value(target["doctype"], target["name"], title_field) if title_field else None
	return {
		"code": code,
		"doctype": target["doctype"],
		"name": target["name"],
		"title": title or target["name"],
	}


def build_web_checkin_url(code):
	"""Shareable website link for a unique code."""
	if not code:
		return None
	return frappe.utils.get_url(f"{WEB_CHECKIN_PATH}?code={code}")


def apply_unique_code(user, code, is_new_user=False):
	"""
	Apply a unique code to a user who is already authenticated (or was just created).

	Safe to call more than once for the same user and code.

	Returns a dict:
	- applied: True if the code was recognised and applied
	- doctype, name, title: what the code points to (when recognised)
	- message: short user-facing result
	"""
	target = resolve_unique_code(code)
	if not target:
		return {"applied": False, "message": "This link is not valid."}

	if not user or user == "Guest" or not frappe.db.exists("User", user):
		return {"applied": False, "message": "Please log in to continue.", **target}

	doctype = target["doctype"]
	if doctype == "Program":
		result = _apply_program(user, target)
	elif doctype == "Solve Event":
		result = _apply_solve_event(user, target)
	else:
		result = {"applied": True, "message": "Welcome to Solve Ninja!"}

	if is_new_user:
		_set_acquisition_source(user, target["code"])

	return {**target, **result}


def apply_unique_code_safely(user, code, is_new_user=False):
	"""
	apply_unique_code() inside a savepoint so a failed check-in never breaks signup or login.
	"""
	save_point = "apply_unique_code"
	frappe.db.savepoint(save_point)
	try:
		result = apply_unique_code(user, code, is_new_user=is_new_user)
	except Exception:
		frappe.db.rollback(save_point=save_point)
		frappe.log_error(
			title="Apply Unique Code Error",
			message=f"user={user} code={code}\n{frappe.get_traceback()}",
		)
		return {"applied": False, "message": "We could not record your check-in. Please try again."}
	frappe.db.release_savepoint(save_point)
	return result


def _is_org_locked(user):
	roles = set(frappe.get_roles(user))
	return any(role in roles for role in ORG_LOCKED_ROLES)


def _apply_program(user, target):
	from solve_ninja.api.common import assign_user_organization
	from solve_ninja.api.v1.solve_event import create_program_participation

	program = target["name"]
	org_updated = False
	if frappe.db.exists("User Organization", program) and not _is_org_locked(user):
		assign_user_organization(user, program)
		org_updated = True

	create_program_participation(user, program)
	return {
		"applied": True,
		"org_updated": org_updated,
		"message": f"You have joined {target['title']}.",
	}


def _apply_solve_event(user, target):
	from solve_ninja.api.v1.solve_event import (
		create_participation,
		find_or_create_registration,
		get_event_checkin_window_status,
	)

	event = frappe.db.get_value(
		"Solve Event",
		target["name"],
		["start_date_time", "end_date_time", "ignore_reg"],
		as_dict=True,
	)
	title = target["title"]

	window_status = get_event_checkin_window_status(
		now_datetime(), event.start_date_time, event.end_date_time
	)
	if window_status == "not_started":
		return {
			"applied": False,
			"message": f"Check-in for {title} opens one hour before the event starts.",
		}
	if window_status == "ended":
		return {"applied": False, "message": f"{title} has ended, so check-in is closed."}

	if event.ignore_reg in (None, "", "No"):
		find_or_create_registration(user, target["name"], source=WEB_REGISTRATION_SOURCE)

	participation = create_participation(user, target["name"])
	if participation["already_checked_in"]:
		message = f"You have already checked in to {title}."
	else:
		message = f"You are checked in to {title}."
	return {
		"applied": True,
		"already_checked_in": participation["already_checked_in"],
		"message": message,
	}


def _set_acquisition_source(user, code):
	# Ninja Profile.validate derives acquisition_source_category / name from the unique id.
	if not frappe.db.exists("Ninja Profile", user):
		return
	ninja_profile = frappe.get_doc("Ninja Profile", user)
	if ninja_profile.acquisition_source_unique_id == code:
		return
	ninja_profile.acquisition_source_unique_id = code
	ninja_profile.save(ignore_permissions=True)
