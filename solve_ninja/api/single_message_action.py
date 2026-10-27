import json
from typing import Literal

import frappe
import requests
from openai import OpenAI
from pydantic import BaseModel, Field

JOB_PATH = "solve_ninja.api.single_message_action"
DEFAULT_COMPLETENESS_MODEL = "gpt-4.1-2025-04-14"
REQUIRED_DETAILS = ["what"]  # add "impact" later if it becomes mandatory
MAX_HOURS = 150
HOURS_UNITS = ("hours", "minutes")

ASSESSMENT_PROMPT = """You review a message from a young person describing an action they took to solve a local civic problem.
Decide each field strictly from what is written. Never assume details that are not stated.

- is_action: true only if they describe something they have ALREADY done. Plans, intentions, questions, greetings, complaints without any action, or unrelated text are false.
- has_what: true only if the SPECIFIC activity can be identified, e.g. "cleaned the drain near my school", "reported a broken streetlight to the ward office", "held a session on waste segregation for 20 students". Generic labels such as "community work", "social service", "helped people", "did an activity" are false.
- has_impact: they mention a result, outcome, or change caused by the action.
- has_how: they describe how they did it (steps, method, tools, process).
- has_with_whom: they mention who they did it with or for, or that they did it alone.

missing_details must list every one of "what", "impact", "how", "with_whom" whose field is false.

The message may be in any Indian language or in English, possibly written in Latin script."""


class Assessment(BaseModel):
	reasoning: str = Field(description="One or two sentences explaining the decision")
	is_action: bool
	has_what: bool
	has_impact: bool
	has_how: bool
	has_with_whom: bool
	missing_details: list[Literal["what", "impact", "how", "with_whom"]]


def _openai():
	api_key = frappe.conf.get("openai_api_key")
	if not api_key:
		raise ValueError("Missing OpenAI API key. Set `openai_api_key` in your site config.")
	return OpenAI(api_key=api_key)


def assess_message(text: str) -> Assessment:
	response = _openai().responses.parse(
		model=frappe.conf.get("single_message_completeness_model") or DEFAULT_COMPLETENESS_MODEL,
		input=[
			{"role": "system", "content": ASSESSMENT_PROMPT},
			{"role": "user", "content": text},
		],
		text_format=Assessment,
		temperature=0,
	)
	return response.output_parsed


def completeness_from(missing: list[str]) -> str:
	return "Incomplete" if any(d in missing for d in REQUIRED_DETAILS) else "Complete"


def _cmp(method, path, json_body=None, params=None, timeout=60):
	base_url = frappe.conf.get("cmp_backend_base_url")
	if not base_url:
		raise ValueError("Missing CMP URL. Set `cmp_backend_base_url` in your site config.")
	response = requests.request(
		method, base_url.rstrip("/") + path, json=json_body, params=params, timeout=timeout
	)
	if response.status_code >= 400:
		raise Exception(f"CMP {method} {path} failed: {response.status_code} {response.text[:500]}")
	return response.json() if response.content else None


def _save(doc, **fields):
	doc.db_set(fields)
	frappe.db.commit()


def _enqueue_processing(submission_name, enqueue_after_commit=False):
	return frappe.enqueue(
		f"{JOB_PATH}.process_submission",
		queue="long",
		timeout=900,
		job_id=f"action_submission::{submission_name}",
		deduplicate=True,
		enqueue_after_commit=enqueue_after_commit,
		submission_name=submission_name,
	)


def _validate_hours(hours_value, hours_unit):
	unit = (hours_unit or "hours").strip().lower()
	if unit not in HOURS_UNITS:
		frappe.throw("Time unit must be hours or minutes.")

	try:
		value = float(hours_value)
	except (TypeError, ValueError):
		value = 0
	if value <= 0:
		frappe.throw("Please tell us how much time you spent on this action.")
	if unit == "minutes" and value != int(value):
		frappe.throw("Enter a whole number of minutes (1 or more).")

	hours_equivalent = value / 60 if unit == "minutes" else value
	if hours_equivalent > MAX_HOURS:
		frappe.throw(f"Time invested cannot exceed {MAX_HOURS} hours ({MAX_HOURS * 60} minutes).")
	return value, unit


def _validate_own_file(file_url, user, label):
	if not file_url:
		return None
	file = frappe.db.get_value("File", {"file_url": file_url}, ["owner", "is_private"], as_dict=True)
	if not file or (file.is_private and file.owner != user):
		frappe.throw(f"The {label} could not be found. Please upload it again.")
	return file_url


@frappe.whitelist(methods=["POST"])
def record_action(text=None, hours_value=None, hours_unit="hours", photo_url=None, audio_file_url=None):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw("Login required", frappe.PermissionError)

	text = (text or "").strip()
	if not text:
		frappe.throw("Please describe the action you took.")

	hours_value, hours_unit = _validate_hours(hours_value, hours_unit)
	photo_url = _validate_own_file(photo_url, user, "photo")
	audio_file_url = _validate_own_file(audio_file_url, user, "voice recording")

	if not frappe.db.get_value("User", user, "username"):
		frappe.throw("Your account has no username yet. Please complete your profile first.")

	try:
		assessment = assess_message(text)
	except Exception:
		frappe.log_error(title="Single message action: assessment failed", message=frappe.get_traceback())
		frappe.throw("We couldn't read your message right now. Please try again in a minute.")

	completeness = completeness_from(assessment.missing_details) if assessment.is_action else ""

	submission = frappe.get_doc(
		{
			"doctype": "Action Submission",
			"user": user,
			"raw_text": text,
			"audio_file": audio_file_url,
			"photo_url": photo_url,
			"hours_value": hours_value,
			"hours_unit": hours_unit,
			"assessment": assessment.model_dump_json(),
			"missing_details": json.dumps(assessment.missing_details),
			"action_completeness": completeness,
			"status": "Pending" if assessment.is_action else "Not an Action",
			"last_completed_step": 0,
		}
	).insert(ignore_permissions=True)

	if not assessment.is_action:
		return {
			"recorded": False,
			"submission": submission.name,
			"message": "This sounds like something you are planning or haven't done yet. "
			"Come back and share it once you have taken the action!",
		}

	_enqueue_processing(submission.name, enqueue_after_commit=True)

	return {
		"recorded": True,
		"submission": submission.name,
		"action_completeness": completeness,
		"missing_details": assessment.missing_details,
		"message": "Your action has been recorded! We are adding the skills you showed to your portfolio.",
	}


def _full_message(submission):
	return "\n".join(filter(None, [submission.raw_text, submission.additional_details]))


def _cmp_will_publish(ai_response):
	# Older CMP transcripts omit create_action; treat a missing flag as publishable, like the web chat does.
	if not isinstance(ai_response, dict) or "create_action" not in ai_response:
		return True
	return bool(ai_response.get("create_action"))


def process_submission(submission_name):
	submission = frappe.get_doc("Action Submission", submission_name)
	if submission.status in ("Done", "Not an Action", "Needs Details"):
		return

	user = frappe.get_doc("User", submission.user)
	username = user.username
	step = submission.last_completed_step or 0
	_save(submission, status="Processing")

	try:
		if step < 1:
			_cmp(
				"POST",
				"/get_or_create_user_by_email",
				{
					"email": user.email,
					"first_name": user.first_name or "",
					"last_name": user.last_name or "",
					"username": username,
				},
			)
			step = 1
			_save(submission, last_completed_step=step)

		if step < 2:
			# /actions is not idempotent, so never call it twice for one submission.
			if not submission.event_id:
				result = _cmp(
					"POST",
					"/actions",
					{"user_email": user.email, "user_message": _full_message(submission)},
				)
				ai_response = result.get("ai_response") or {}
				action_uuid = result["action"]["uuid"]
				submission.suggested_followup = ai_response.get("response")

				if not _cmp_will_publish(ai_response):
					# CMP refuses to extract metadata for this draft, so park it until the user adds details.
					previous = json.loads(submission.previous_event_ids or "[]") + [action_uuid]
					_save(
						submission,
						status="Needs Details",
						suggested_followup=submission.suggested_followup,
						previous_event_ids=json.dumps(previous),
						error=None,
					)
					return

				submission.event_id = action_uuid
			step = 2
			_save(
				submission,
				last_completed_step=step,
				event_id=submission.event_id,
				suggested_followup=submission.suggested_followup,
			)

		uuid = submission.event_id

		if step < 3:
			try:
				_cmp("POST", "/ai/extract_action_metadata", params={"action_uuid": uuid}, timeout=180)
			except Exception:
				# CMP creates the event before refreshing the summary; only the summary may have failed.
				if not frappe.db.exists("Events", uuid):
					raise
			step = 3
			_save(submission, last_completed_step=step)

		if step < 4:
			_cmp(
				"POST",
				f"/actions/{uuid}/hours_invested",
				{
					"time_invested_value": submission.hours_value,
					"time_invested_unit": submission.hours_unit or "hours",
				},
			)
			step = 4
			_save(submission, last_completed_step=step)

		if step < 5:
			_cmp("POST", f"/ai/profile_summary/{username}", timeout=120)
			step = 5
			_save(submission, last_completed_step=step)

		if step < 6:
			if submission.photo_url:
				_attach_photo(uuid, submission.photo_url)
			step = 6
			_save(submission, last_completed_step=step, status="Done", error=None)
	except Exception:
		_save(submission, status="Failed", error=frappe.get_traceback())
		frappe.log_error(title=f"Single message action failed: {submission_name}", message=frappe.get_traceback())
		raise


def _attach_photo(event_name, photo_url):
	frappe.db.set_value("Events", event_name, "attachment1", photo_url)
	file_name = frappe.db.get_value(
		"File", {"file_url": photo_url, "attached_to_name": ("is", "not set")}, "name"
	)
	if file_name:
		frappe.db.set_value(
			"File",
			file_name,
			{
				"attached_to_doctype": "Events",
				"attached_to_name": event_name,
				"attached_to_field": "attachment1",
			},
		)


@frappe.whitelist()
def get_submission_status(submission_name):
	submission = frappe.get_doc("Action Submission", submission_name)
	if submission.user != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw("Not permitted", frappe.PermissionError)

	return {
		"status": submission.status,
		"event_id": submission.event_id,
		"action_completeness": submission.action_completeness,
		"missing_details": json.loads(submission.missing_details or "[]"),
		"suggested_followup": submission.suggested_followup,
	}


@frappe.whitelist(methods=["POST"])
def answer_followup(submission_name, text=None):
	submission = frappe.get_doc("Action Submission", submission_name)
	if submission.user != frappe.session.user:
		frappe.throw("Not permitted", frappe.PermissionError)
	if submission.status != "Needs Details":
		frappe.throw("This action doesn't need more details right now.")

	text = (text or "").strip()
	if not text:
		frappe.throw("Please add some details about what you did.")

	additional_details = "\n".join(filter(None, [submission.additional_details, text]))
	full_message = "\n".join(filter(None, [submission.raw_text, additional_details]))

	try:
		assessment = assess_message(full_message)
	except Exception:
		frappe.log_error(title="Single message action: assessment failed", message=frappe.get_traceback())
		frappe.throw("We couldn't read your message right now. Please try again in a minute.")

	completeness = completeness_from(assessment.missing_details) if assessment.is_action else ""
	_save(
		submission,
		additional_details=additional_details,
		assessment=assessment.model_dump_json(),
		missing_details=json.dumps(assessment.missing_details),
		action_completeness=completeness,
		status="Pending",
		suggested_followup=None,
		last_completed_step=1,
	)
	_enqueue_processing(submission.name)

	return {
		"accepted": True,
		"submission": submission.name,
		"action_completeness": completeness,
		"missing_details": assessment.missing_details,
		"message": "Thanks! We are adding your action to your portfolio.",
	}


@frappe.whitelist(methods=["POST"])
def retry_submission(submission_name):
	frappe.only_for("System Manager")
	status = frappe.db.get_value("Action Submission", submission_name, "status")
	if status in ("Done", "Not an Action", "Needs Details"):
		frappe.throw(f"Submission {submission_name} is {status} and does not need a retry.")
	if not _enqueue_processing(submission_name):
		return {"queued": False, "submission": submission_name, "message": "Already queued or running."}
	return {"queued": True, "submission": submission_name}
