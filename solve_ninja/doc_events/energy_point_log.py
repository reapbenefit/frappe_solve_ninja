import frappe
import requests
import json
from frappe.utils import flt
from solve_ninja.utils import validate_and_normalize_mobile
from time import sleep

# Short lock while enqueue/worker runs; long lock after a successful send
BADGE_NOTIFY_LOCK_SECS = 300
BADGE_NOTIFY_SENT_SECS = 7 * 24 * 3600


def _badge_notification_cache_key(event_name):
	return f"badge_notification_sent_{event_name}"


def _try_acquire_badge_notify_lock(event_name, expires_in_sec=BADGE_NOTIFY_LOCK_SECS):
	"""
	Atomically claim the per-event notify lock.

	Uses Redis SET NX (not get_value/set_value). get_value caches a miss as None in
	frappe.local.cache, and set_value with expires_in_sec does not update local cache,
	so later gets in the same request always miss and re-enqueue — one HSM per skill.
	"""
	cache = frappe.cache()
	redis_key = cache.make_key(_badge_notification_cache_key(event_name))
	try:
		return bool(cache.set(redis_key, b"1", nx=True, ex=expires_in_sec))
	except Exception:
		# Same-request fallback if Redis is unavailable
		locks = getattr(frappe.local, "_badge_notify_locks", None)
		if locks is None:
			locks = frappe.local._badge_notify_locks = set()
		if event_name in locks:
			return False
		locks.add(event_name)
		return True


def _release_badge_notify_lock(event_name):
	cache = frappe.cache()
	redis_key = cache.make_key(_badge_notification_cache_key(event_name))
	try:
		cache.delete(redis_key)
	except Exception:
		pass
	locks = getattr(frappe.local, "_badge_notify_locks", None)
	if locks is not None:
		locks.discard(event_name)


def _mark_badge_notify_sent(event_name):
	cache = frappe.cache()
	redis_key = cache.make_key(_badge_notification_cache_key(event_name))
	try:
		cache.set(redis_key, b"1", ex=BADGE_NOTIFY_SENT_SECS)
	except Exception:
		pass


def handle_energy_point_log(doc, method):
	"""
	Handle Energy Point Log creation and trigger badge notification.
	Only triggers notification for Events documents and ensures only one notification per event.
	"""
	# Only process Auto type Energy Point Logs with badges for Events documents
	if doc.type != "Auto" or not doc.badge or not doc.user:
		return

	if doc.reference_doctype != "Events" or not doc.reference_name:
		return

	# Verify Events document exists and check source
	try:
		events_doc = frappe.get_doc("Events", doc.reference_name)
		if events_doc.source and events_doc.source in ["SamaajData", "manualupload"]:
			return
	except frappe.DoesNotExistError:
		return

	# First caller for this event wins; later skill inserts skip
	if not _try_acquire_badge_notify_lock(doc.reference_name):
		return

	frappe.enqueue(
		"solve_ninja.doc_events.energy_point_log.send_badge_notification",
		event_name=doc.reference_name,
		enqueue_after_commit=True,
	)


def send_badge_notification_after_insert(doc, method=None):
	"""
	On Events create: claim the notify lock early and enqueue once.
	Later Energy Point Log inserts see the same lock and skip enqueueing,
	so multi-skill events send a single WhatsApp notification.
	"""
	if not doc.user or not doc.source or doc.source in ["SamaajData", "manualupload"]:
		return

	if not _try_acquire_badge_notify_lock(doc.name):
		return

	frappe.enqueue(
		"solve_ninja.doc_events.energy_point_log.send_badge_notification",
		event_name=doc.name,
		enqueue_after_commit=True,
	)


def send_glific_message(doc, url, headers, data):
	response = None
	error = None
	try:
		response = requests.post(url, headers=headers, json=data, timeout=10)
		response.raise_for_status()
	except Exception:
		error = frappe.get_traceback()
		frappe.log_error(
			title="Glific Message Send Error",
			message=error,
			reference_doctype=doc.doctype,
			reference_name=doc.name,
		)
	finally:
		log_glific_integration_request(doc, url, headers, data, response.json() if response else None, error)


def log_glific_integration_request(doc, url, headers, data, response, error=None):
	frappe.get_doc({
		"doctype": "Integration Request",
		"integration_request_service": "Glific HSM",
		"is_remote_request": 1,
		"url": url,
		"request_headers": frappe.as_json(headers),
		"data": frappe.as_json(data),
		"output": frappe.as_json(response) if response else "",
		"error": frappe.as_json(error) if error else "",
		"status": "Completed" if response and not error else "Failed",
		"reference_doctype": doc.doctype,
		"reference_docname": doc.name,
		"request_description": "Send WhatsApp HSM message via Glific",
	}).insert(ignore_permissions=True)


def _log_badge_ir(event_name, status, description, data=None, response=None, error=None):
	try:
		frappe.get_doc({
			"doctype": "Integration Request",
			"integration_request_service": "Glific Badge HSM",
			"reference_doctype": "Events",
			"reference_docname": event_name,
			"status": status,
			"request_description": description,
			"data": frappe.as_json(data) if data else "",
			"output": frappe.as_json(response) if response else "",
			"error": frappe.as_json(error) if error else "",
			"is_remote_request": 1,
		}).insert(ignore_permissions=True, ignore_links=True)
	except Exception:
		frappe.log_error(
			title="Badge IR Logging Error",
			message=frappe.get_traceback(),
			reference_doctype="Events",
			reference_name=event_name,
		)


def _build_badge_notification_context(user, ninja_profile, user_metadata, eps, events):
	"""Build Jinja context for Momentum Update HSM parameters."""
	# Skill = EPS.badge (comma-separated unique names)
	skills = sorted({e.badge for e in eps if e.get("badge")})

	# Microskill = EPS.microskill Link → Microskill.title (comma-separated; optional)
	microskill_ids = list({e.microskill for e in eps if e.get("microskill")})
	microskill_titles = []
	if microskill_ids:
		microskill_titles = frappe.get_all(
			"Microskill",
			filters={"name": ("in", microskill_ids)},
			pluck="title",
		)

	total_hours_row = frappe.db.get_all(
		"Events",
		filters={"user": events.user},
		fields=["sum(hours_invested) as total_hours"],
	)
	total_hours = flt(total_hours_row[0].total_hours) if total_hours_row else 0

	return {
		"user": user,
		"ninja_profile": ninja_profile,
		"user_metadata": user_metadata,
		"eps": eps,
		"event": events,
		"skills": ", ".join(skills) if skills else "-",
		"microskills": ", ".join(microskill_titles) if microskill_titles else "-",
		"action_hours": events.hours_invested or 0,
		"total_hours": total_hours,
	}


def send_badge_notification(event_name, events=None):
	"""
	Send badge notification for an Events document.
	Logs every outcome (skip, failure, success) to Integration Request
	so ops can query by reference_docname = <event_id>.
	"""
	solve_ninja_settings = frappe.get_single("Solve Ninja Settings")
	if not solve_ninja_settings.enable_badge_notification:
		_log_badge_ir(event_name, "Cancelled", "Badge notifications disabled in Solve Ninja Settings")
		return

	# Small delay to allow all Energy Point Logs to be created in the same request
	sleep(3)

	# Always reload by name — do not rely on a serialized Document from enqueue
	try:
		events = frappe.get_doc("Events", event_name)
	except frappe.DoesNotExistError:
		_log_badge_ir(event_name, "Failed", "Events document not found")
		frappe.log_error(
			title="Badge Notification Error",
			message=f"Events document {event_name} not found",
			reference_doctype="Events",
			reference_name=event_name,
		)
		return

	eps = frappe.get_all("Energy Point Log", filters={
		"reference_doctype": "Events",
		"reference_name": event_name,
		"type": "Auto",
		"badge": ("is", "set")
	}, fields=["*"])

	if not eps:
		_log_badge_ir(event_name, "Cancelled", "No badge Energy Point Logs found for event")
		_release_badge_notify_lock(event_name)
		return

	if not events.user:
		_log_badge_ir(event_name, "Cancelled", "Events document has no user")
		return

	if events.source and events.source in ["SamaajData", "manualupload"]:
		_log_badge_ir(event_name, "Cancelled", f"Source '{events.source}' is excluded from badge notifications")
		return

	# Belt-and-suspenders: if another worker already sent successfully, do not send again
	already_sent = frappe.db.exists(
		"Integration Request",
		{
			"integration_request_service": "Glific Badge HSM",
			"reference_doctype": "Events",
			"reference_docname": event_name,
			"status": "Completed",
		},
	)
	if already_sent:
		_log_badge_ir(event_name, "Cancelled", "Badge HSM already sent for this event")
		_mark_badge_notify_sent(event_name)
		return

	try:
		user = frappe.get_doc("User", events.user)
		ninja_profile = frappe.get_doc("Ninja Profile", events.user, for_update=False)
		user_metadata = frappe.get_doc("User Metadata", events.user)

		badge_template = frappe.get_doc("Badge Template", solve_ninja_settings.default_badge_template)

		if not badge_template or not badge_template.parameters_json:
			_log_badge_ir(event_name, "Failed", "No valid badge template or parameters_json found",
						  data={"user": events.user, "default_badge_template": solve_ninja_settings.default_badge_template})
			frappe.log_error(
				title="Badge Notification Error",
				message="No valid badge template found",
				reference_doctype="Events",
				reference_name=event_name,
			)
			return

		# Normalize before truthiness check; catch throw so junk mobiles become Cancelled IRs
		raw_mobile_no = user.mobile_no
		try:
			mobile_no = validate_and_normalize_mobile((raw_mobile_no or "").strip())
		except Exception:
			mobile_no = ""

		if solve_ninja_settings.channel != "Glific":
			_log_badge_ir(event_name, "Cancelled", f"Channel is '{solve_ninja_settings.channel}', not Glific",
						  data={"user": events.user, "channel": solve_ninja_settings.channel})
			return

		if not mobile_no:
			_log_badge_ir(event_name, "Cancelled", f"No valid mobile number for user {events.user}",
						  data={"user": events.user, "raw_mobile_no": raw_mobile_no})
			return

		glific_settings = frappe.get_doc("Glific Settings")

		if not ninja_profile.wa_id:
			response = glific_settings.get_contact_by_phone(mobile_no)
			contact = (
				(response or {})
				.get("data", {})
				.get("contactByPhone", {})
				.get("contact")
			) or {}
			contact_id = contact.get("id")
			if contact_id:
				ninja_profile.db_set("wa_id", contact_id, commit=True)
				ninja_profile.reload()

		if not ninja_profile.wa_id:
			_log_badge_ir(event_name, "Cancelled", f"No Glific contact found for phone {mobile_no}",
						  data={"user": events.user, "mobile_no": mobile_no})
			return

		context = _build_badge_notification_context(
			user, ninja_profile, user_metadata, eps, events
		)
		parameters = json.loads(frappe.render_template(badge_template.parameters_json, context))
		request_data = {
			"wa_id": ninja_profile.wa_id,
			"template_id": badge_template.template_id,
			"parameters": parameters,
			"user": events.user,
			"mobile_no": mobile_no,
		}

		# One transient retry on timeout
		glific_response = glific_settings.send_hsm_message(
			ninja_profile.wa_id, badge_template.template_id, parameters
		)
		if (glific_response or {}).get("error", "").lower().startswith("glific api timed out"):
			sleep(5)
			glific_response = glific_settings.send_hsm_message(
				ninja_profile.wa_id, badge_template.template_id, parameters
			)

		# Validate response before treating as success
		hsm_result = (glific_response or {}).get("data", {}).get("sendHsmMessage", {})
		gql_errors = (glific_response or {}).get("errors") or hsm_result.get("errors") or []
		message_id = (hsm_result.get("message") or {}).get("id")

		if gql_errors or not message_id:
			error_detail = gql_errors or glific_response
			_log_badge_ir(event_name, "Failed", "Glific returned an error for HSM send",
						  data=request_data, response=glific_response, error=error_detail)
			frappe.log_error(
				title="Badge Notification Error",
				message=frappe.as_json(error_detail),
				reference_doctype="Events",
				reference_name=event_name,
			)
			_release_badge_notify_lock(event_name)
			return

		_log_badge_ir(event_name, "Completed",
					  f"HSM sent successfully (message id: {message_id})",
					  data=request_data, response=glific_response)
		# Keep lock so later EPS for this event cannot re-notify
		_mark_badge_notify_sent(event_name)

	except Exception:
		tb = frappe.get_traceback()
		_log_badge_ir(event_name, "Failed",
					  f"Unhandled exception in badge notification for {event_name}",
					  error=tb)
		frappe.log_error(
			title="Badge Notification Error",
			message=tb,
			reference_doctype="Events",
			reference_name=event_name,
		)
		_release_badge_notify_lock(event_name)
