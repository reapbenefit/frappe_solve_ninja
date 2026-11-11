# Copyright (c) 2026, ReapBenefit and Contributors
# See license.txt

import json
import random
from contextlib import ExitStack
from datetime import timedelta
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from solve_ninja.api.auth import apply_checkin_code, verify_otp_login
from solve_ninja.api.common import add_user, assign_user_organization
from solve_ninja.services.unique_code import (
	WEB_CHECKIN_LANDING,
	apply_unique_code,
	build_web_checkin_url,
	normalize_code,
	resolve_unique_code,
)
from solve_ninja.www.signup_utils import get_checkin_redirect, get_code_from_redirect

DOC_SIDE_EFFECTS = {
	"Program": "solve_ninja.solve_ninja.doctype.program.program.Program",
	"Solve Event": "solve_ninja.solve_ninja.doctype.solve_event.solve_event.SolveEvent",
}


def _no_doc_side_effects(doctype):
	"""Skip Glific keyword sync, QR upload and WhatsApp URL build while saving test docs."""
	stack = ExitStack()
	cls = DOC_SIDE_EFFECTS[doctype]
	stack.enter_context(patch(f"{cls}.update_flow_keyword", lambda self: None))
	stack.enter_context(patch(f"{cls}.generate_qr_code", lambda self, url: None))
	stack.enter_context(patch(f"{cls}.update_checkin_url", lambda self: None))
	return stack


class TestUniqueCodeCheckin(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.suffix = str(random.randint(1000000000, 9999999999))
		self.program_name = f"TestWebCode-{self.suffix}"
		self.program_code = f"OTWC{self.suffix}"
		self.event_code = f"ETWC{self.suffix}"
		self.created = []

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		for doctype, filters in (
			("Program Participation", {"program": self.program_name}),
			("Solve Event Participation", {"solve_event": ["like", f"TestWebEvent-{self.suffix}%"]}),
			("Solve Event Registration", {"solve_event": ["like", f"TestWebEvent-{self.suffix}%"]}),
			("Login OTP", {"user": f"91{self.suffix}@solveninja.org"}),
		):
			for name in frappe.get_all(doctype, filters=filters, pluck="name"):
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)

		for doctype, name in reversed(self.created):
			try:
				if name and frappe.db.exists(doctype, name):
					frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
			except Exception:
				pass

		for doctype in ("Program", "User Organization"):
			if frappe.db.exists(doctype, self.program_name):
				frappe.delete_doc(doctype, self.program_name, force=True, ignore_permissions=True)
		frappe.db.commit()

	def track(self, doctype, name):
		self.created.append((doctype, name))
		return name

	def _city(self):
		city = f"TestWebCity-{self.suffix}"
		if not frappe.db.exists("Samaaja Cities", city):
			frappe.get_doc({"doctype": "Samaaja Cities", "city_name": city}).insert(ignore_permissions=True)
			self.track("Samaaja Cities", city)
		return city

	def _create_program(self):
		city = self._city()
		source = f"TestWebSrc-{self.suffix}"
		frappe.get_doc({"doctype": "Program Source", "source_type": source}).insert(ignore_permissions=True)
		self.track("Program Source", source)
		sub = f"TestWebSub-{self.suffix}"
		frappe.get_doc(
			{"doctype": "Program Sub Source", "sub_source": sub, "program_source": source}
		).insert(ignore_permissions=True)
		self.track("Program Sub Source", sub)

		with _no_doc_side_effects("Program"):
			program = frappe.get_doc(
				{
					"doctype": "Program",
					"program_name": self.program_name,
					"start_date": "2026-01-01",
					"end_date": "2026-01-31",
					"city": city,
					"mode": "Offline",
					"program_source": source,
					"program_sub_source": sub,
					"college_name": "Test College",
				}
			)
			program.insert(ignore_permissions=True)
		self.track("Program", program.name)
		# Fixed code so the test does not depend on generated ids
		frappe.db.set_value("Program", program.name, "unique_id", self.program_code)
		return program

	def _create_event(self, starts_in=timedelta(minutes=-30), name_suffix=""):
		start = now_datetime() + starts_in
		code = f"{self.event_code}{name_suffix}"
		with _no_doc_side_effects("Solve Event"):
			event = frappe.get_doc(
				{
					"doctype": "Solve Event",
					"title": f"TestWebEvent-{self.suffix}{name_suffix}",
					"type": "Adda",
					"description": "Test",
					"start_date_time": start,
					"end_date_time": start + timedelta(hours=2),
					"city": self._city(),
					"unique_id": code,
					"ignore_reg": "No",
				}
			)
			event.flags.ignore_mandatory = True
			event.insert(ignore_permissions=True)
		self.track("Solve Event", event.name)
		return event, code

	def _create_user(self, roles=None):
		mobile = f"91{self.suffix}"
		email = f"{mobile}@solveninja.org"
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "WebCode",
				"mobile_no": mobile,
				"send_welcome_email": 0,
			}
		)
		for role in roles or []:
			user.append("roles", {"role": role})
		user.insert(ignore_permissions=True)
		self.track("User", email)
		for doctype in ("Ninja Profile", "User Metadata"):
			if frappe.db.exists(doctype, email):
				self.track(doctype, email)
		return email

	def _other_org(self, user):
		# User Organization has hash names; Program-backed orgs are renamed to the Program name.
		other_org = f"TestWebOther-{self.suffix}"
		org = frappe.get_doc(
			{"doctype": "User Organization", "org_name": other_org, "org_id": other_org}
		).insert(ignore_permissions=True)
		self.track("User Organization", org.name)
		assign_user_organization(user, org.name)
		self.assertEqual(frappe.db.get_value("User Metadata", user, "org_id"), org.name)
		return org.name

	def test_normalize_and_resolve(self):
		self._create_program()
		self.assertIsNone(normalize_code(""))
		self.assertIsNone(normalize_code("bad code!"))
		self.assertIsNone(resolve_unique_code("NOPE-NOT-A-CODE"))

		target = resolve_unique_code(self.program_code.lower())
		self.assertEqual(target["doctype"], "Program")
		self.assertEqual(target["name"], self.program_name)
		self.assertEqual(target["code"], self.program_code)

	def test_program_code_existing_user_updates_org_and_keeps_acquisition(self):
		self._create_program()
		user = self._create_user()
		self._other_org(user)
		before_source = frappe.db.get_value("Ninja Profile", user, "acquisition_source_unique_id")

		result = apply_unique_code(user, self.program_code)

		self.assertTrue(result["applied"])
		self.assertEqual(frappe.db.get_value("User Metadata", user, "org_id"), self.program_name)
		self.assertTrue(
			frappe.db.exists("Program Participation", {"user": user, "program": self.program_name})
		)
		self.assertEqual(
			frappe.db.get_value("Ninja Profile", user, "acquisition_source_unique_id"), before_source
		)

		# Second call is a no-op
		apply_unique_code(user, self.program_code)
		self.assertEqual(
			frappe.db.count("Program Participation", {"user": user, "program": self.program_name}), 1
		)

	def test_program_code_new_user_records_acquisition(self):
		self._create_program()
		user = self._create_user()

		apply_unique_code(user, self.program_code, is_new_user=True)

		profile = frappe.db.get_value(
			"Ninja Profile",
			user,
			["acquisition_source_unique_id", "acquisition_source_category", "acquisition_source_name"],
			as_dict=True,
		)
		self.assertEqual(profile.acquisition_source_unique_id, self.program_code)
		self.assertEqual(profile.acquisition_source_category, "Program")
		self.assertEqual(profile.acquisition_source_name, self.program_name)

	def test_program_code_does_not_move_organisation_manager(self):
		self._create_program()
		user = self._create_user(roles=["Organisation Manager"])
		other_org = self._other_org(user)

		result = apply_unique_code(user, self.program_code)

		self.assertTrue(result["applied"])
		self.assertFalse(result["org_updated"])
		self.assertEqual(frappe.db.get_value("User Metadata", user, "org_id"), other_org)
		self.assertTrue(
			frappe.db.exists("Program Participation", {"user": user, "program": self.program_name})
		)

	@patch("frappe.enqueue")
	def test_event_code_checks_in_with_web_registration(self, _enqueue):
		event, code = self._create_event()
		user = self._create_user()

		first = apply_unique_code(user, code)
		second = apply_unique_code(user, code)

		self.assertTrue(first["applied"])
		self.assertFalse(first["already_checked_in"])
		self.assertTrue(second["already_checked_in"])
		self.assertEqual(
			frappe.db.get_value(
				"Solve Event Registration", {"user": user, "solve_event": event.name}, "source"
			),
			"Web Form",
		)
		self.assertEqual(
			frappe.db.count("Solve Event Participation", {"user": user, "solve_event": event.name}), 1
		)

	def test_event_code_outside_window_does_not_check_in(self):
		event, code = self._create_event(starts_in=timedelta(days=3), name_suffix="F")
		user = self._create_user()

		result = apply_unique_code(user, code)

		self.assertFalse(result["applied"])
		self.assertIn("opens one hour before", result["message"])
		self.assertFalse(
			frappe.db.exists("Solve Event Participation", {"user": user, "solve_event": event.name})
		)

	def test_apply_checkin_code_uses_session_user(self):
		self._create_program()
		user = self._create_user()

		frappe.set_user(user)
		result = apply_checkin_code(self.program_code)
		frappe.set_user("Administrator")

		self.assertTrue(result["applied"])
		self.assertTrue(
			frappe.db.exists("Program Participation", {"user": user, "program": self.program_name})
		)

	def _verify_otp(self, user, code=None):
		mobile = frappe.db.get_value("User", user, "mobile_no")
		frappe.get_doc(
			{
				"doctype": "Login OTP",
				"mobile": mobile,
				"user": user,
				"otp": "123456",
				"valid_till": now_datetime() + timedelta(minutes=5),
				"status": "Pending",
			}
		).insert(ignore_permissions=True)

		previous_login_manager = getattr(frappe.local, "login_manager", None)
		frappe.local.login_manager = MagicMock()
		try:
			return verify_otp_login(mobile, "123456", code=code)
		finally:
			frappe.local.login_manager = previous_login_manager

	def test_otp_login_with_code_lands_on_quick_add(self):
		self._create_program()
		user = self._create_user()

		result = self._verify_otp(user, code=self.program_code)

		self.assertTrue(result["success"], result)
		self.assertEqual(result["redirect_to"], WEB_CHECKIN_LANDING)
		self.assertTrue(result["code_result"]["applied"])

	def test_otp_login_with_code_mentor_lands_on_quick_add(self):
		self._create_program()
		# Mentor accounts also carry Desk User, which makes them System Users
		user = self._create_user(roles=["Mentor", "Desk User"])
		self.assertEqual(frappe.db.get_value("User", user, "user_type"), "System User")

		result = self._verify_otp(user, code=self.program_code)

		self.assertEqual(result["redirect_to"], WEB_CHECKIN_LANDING)

	def test_otp_login_with_code_organisation_manager_lands_on_desk(self):
		self._create_program()
		user = self._create_user(roles=["Organisation Manager"])

		result = self._verify_otp(user, code=self.program_code)

		self.assertEqual(result["redirect_to"], "/desk")

	def test_otp_login_without_code_lands_on_profile(self):
		user = self._create_user()

		result = self._verify_otp(user)

		self.assertTrue(result["success"], result)
		self.assertEqual(result["redirect_to"], "/user-profile/me")

	def _call_add_user(self, payload):
		"""Run add_user as the website signup does; return (response, signup email)."""
		email = f"91{payload['mobile']}@solveninja.org"
		self.track("User", email)
		self.track("Ninja Profile", email)
		self.track("User Metadata", email)

		frappe.local.form_dict = frappe._dict(payload)

		class _TestRequest:
			host = frappe.local.site
			url = f"https://{host}/api/method/solve_ninja.api.common.add_user"
			headers = {"Content-Type": "application/json"}
			data = None

		previous_request = getattr(frappe.local, "request", None)
		frappe.local.request = _TestRequest()
		try:
			with patch("frappe.enqueue"), patch(
				"solve_ninja.services.glific_manager.GlificManager.ensure_contact_for_user",
				return_value=frappe._dict(data="glific-contact", message="ok"),
			):
				response = add_user()
		finally:
			frappe.local.request = previous_request
			frappe.local.form_dict = frappe._dict()
		return response, email

	def test_add_user_with_program_code(self):
		self._create_program()
		response, email = self._call_add_user(
			{
				"mobile": self.suffix,
				"first_name": "Web Signup",
				"acquisition_source_category": "Website Direct",
				"code": self.program_code,
			}
		)

		body = json.loads(response.get_data(as_text=True))
		self.assertEqual(response.status_code, 200, body)
		self.assertIn(f"You have joined {self.program_name}", body["message"])
		self.assertEqual(frappe.db.get_value("User Metadata", email, "org_id"), self.program_name)
		self.assertTrue(
			frappe.db.exists("Program Participation", {"user": email, "program": self.program_name})
		)
		self.assertEqual(
			frappe.db.get_value("Ninja Profile", email, "acquisition_source_category"), "Program"
		)

	def test_add_user_matches_whatsapp_signup_without_role_popup(self):
		frappe.local.message_log = []
		response, email = self._call_add_user(
			{
				"mobile": self.suffix,
				"first_name": "Web Signup",
				"acquisition_source_category": "Website Direct",
			}
		)

		self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
		self.assertEqual(frappe.get_roles(email).count("Solve Ninja"), 1)
		self.assertEqual(frappe.db.get_value("User", email, "user_type"), "Website User")
		self.assertEqual(frappe.db.get_value("User", email, "send_welcome_email"), 0)
		titles = [str(message.get("title")) for message in frappe.local.message_log]
		self.assertNotIn("No Roles Specified", titles)

	def test_web_checkin_url_set_on_save(self):
		self._create_program()
		program = frappe.get_doc("Program", self.program_name)
		with _no_doc_side_effects("Program"):
			program.save(ignore_permissions=True)
		self.assertEqual(program.web_checkin_url, build_web_checkin_url(program.unique_id))
		self.assertTrue(program.web_checkin_url.endswith(f"/checkin?code={program.unique_id}"))

	def test_checkin_redirect_round_trip(self):
		redirect = get_checkin_redirect("ABC123", "/events")
		self.assertEqual(redirect, "/checkin?code=ABC123&redirect-to=%2Fevents")
		self.assertEqual(get_code_from_redirect(redirect), "ABC123")
		self.assertIsNone(get_code_from_redirect("/user-profile/me"))
