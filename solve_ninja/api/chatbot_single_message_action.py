import frappe

from solve_ninja.api.single_message_action import _profile_url_for_user, record_action_for_user
from solve_ninja.services.events_manager import EventsManager
from solve_ninja.utils import find_user_by_mobile, parse_request_data

NEEDS_REGISTRATION_MESSAGE = (
	"No account found with this mobile number. Please sign up or register first."
)
DISABLED_ACCOUNT_MESSAGE = "Your account is disabled. Please contact administrator."
ACCEPTED_MESSAGE = (
	"Saved! Adding it to your profile…\nYou’ll see your skills here in about a minute."
)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def record_action(
	mobile=None,
	text=None,
	user_msg=None,
	hours_value=None,
	hours_unit="hours",
	photo_url=None,
	file_url=None,
	link=None,
	contact_id=None,
	flow_id=None,
):
	"""
	Glific single-message action: one call with description, hours, and optional photo.

	Returns immediately after queuing so Glific does not time out. OpenAI assessment
	and remote photo download run in assess_and_process_submission.

	Looks up the user by mobile. If none exists, returns needs_registration so the
	flow can send them to sign up — does not create an account.

	Pass contact_id + flow_id so that when processing finishes we resume the waiting
	Glific flow with a summary (title, hours, skills, profile_url, events_url) and
	skip the Momentum badge HSM for that event.
	"""
	data = _request_fields(
		mobile=mobile,
		text=text,
		user_msg=user_msg,
		hours_value=hours_value,
		hours_unit=hours_unit,
		photo_url=photo_url,
		file_url=file_url,
		link=link,
		contact_id=contact_id,
		flow_id=flow_id,
	)

	mobile = (data.get("mobile") or "").strip()
	if not mobile:
		frappe.throw("Mobile number is required.")

	user_name, _, _username = find_user_by_mobile(mobile)
	if not user_name:
		return {
			"recorded": False,
			"needs_registration": True,
			"message": NEEDS_REGISTRATION_MESSAGE,
		}

	if not frappe.db.get_value("User", user_name, "enabled"):
		return {
			"recorded": False,
			"needs_registration": False,
			"message": DISABLED_ACCOUNT_MESSAGE,
		}

	text = (data.get("text") or data.get("user_msg") or "").strip()
	# Defer http(s) download to the background job; keep /files/ and multipart sync.
	photo_url = _resolve_photo_url(
		data.get("photo_url") or data.get("file_url") or data.get("link"),
		download_remote=False,
	)

	result = record_action_for_user(
		user_name,
		text=text,
		hours_value=data.get("hours_value"),
		hours_unit=data.get("hours_unit") or "hours",
		photo_url=photo_url,
		validate_files=False,
		assess=False,
		glific_contact_id=data.get("contact_id"),
		glific_flow_id=data.get("flow_id"),
	)
	return _accepted_response(user_name, result)


def _accepted_response(user_name, result):
	"""Fast Glific ack with profile link; assessment finishes in the background."""
	if not result.get("recorded"):
		return result

	profile_url = _profile_url_for_user(user_name)
	out = dict(result)
	out["accepted"] = True
	out["profile_url"] = profile_url  # available for Glific; not in ack message (avoids early tap-away)
	out["message"] = ACCEPTED_MESSAGE
	return out


def _request_fields(**kwargs):
	"""Prefer explicit args; fall back to JSON/form body (Glific-style)."""
	body = _safe_request_body()
	merged = dict(body)
	for key, value in kwargs.items():
		if value is not None and value != "":
			merged[key] = value
	return merged


def _safe_request_body():
	try:
		body = parse_request_data()
	except (ValueError, RuntimeError):
		return {}
	return body if isinstance(body, dict) else {}


def _uploaded_file():
	try:
		return frappe.request.files.get("file")
	except RuntimeError:
		return None


def _resolve_photo_url(source_url=None, *, download_remote=True):
	"""Save multipart file or (optionally) remote URL as a File; return path or URL."""
	uploaded_file = _uploaded_file()
	has_file = bool(uploaded_file and uploaded_file.filename)
	source_url = (source_url or "").strip() or None

	if has_file and source_url:
		frappe.throw("Provide exactly one of file or photo_url/file_url.")

	if has_file:
		return EventsManager._save_uploaded_file(uploaded_file, None).file_url

	if not source_url:
		return None

	if source_url.startswith("/files/") or source_url.startswith("/private/files/"):
		if not frappe.db.exists("File", {"file_url": source_url}):
			frappe.throw("The photo could not be found. Please upload it again.")
		return source_url

	if source_url.startswith("http://") or source_url.startswith("https://"):
		if not download_remote:
			# Background assess_and_process_submission downloads this URL.
			return source_url
		return EventsManager._save_file_from_url(source_url, None).file_url

	frappe.throw("photo_url must be an http(s) URL or a site file path.")
