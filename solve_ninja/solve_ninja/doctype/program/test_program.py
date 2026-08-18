# Copyright (c) 2025, ReapBenefit and Contributors
# See license.txt

import json
import random
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from solve_ninja.api.common import assign_user_organization
from solve_ninja.api.v1.solve_event import program_checkin


def _parse_response(result):
	if hasattr(result, "status_code"):
		body = json.loads(result.data)
		body["status_code"] = result.status_code
		return body
	return result


class TestProgramUserOrganization(FrappeTestCase):
	def setUp(self):
		self.suffix = str(random.randint(1000000000, 9999999999))
		self.program_name = f"TestProgOrg-{self.suffix}"
		self.created = []

	def tearDown(self):
		frappe.db.rollback()
		for doctype, name in reversed(self.created):
			try:
				if name and frappe.db.exists(doctype, name):
					frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
			except Exception:
				pass

		for row in frappe.get_all(
			"Program Participation",
			filters={"program": self.program_name},
			pluck="name",
		):
			try:
				frappe.delete_doc("Program Participation", row, force=True, ignore_permissions=True)
			except Exception:
				pass

		for doctype in ("Program", "User Organization"):
			if frappe.db.exists(doctype, self.program_name):
				try:
					frappe.delete_doc(doctype, self.program_name, force=True, ignore_permissions=True)
				except Exception:
					pass

		frappe.db.commit()

	def track(self, doctype, name):
		self.created.append((doctype, name))
		return name

	def _ensure_program_deps(self):
		city = f"TestCity-{self.suffix}"
		if not frappe.db.exists("Samaaja Cities", city):
			doc = frappe.get_doc({"doctype": "Samaaja Cities", "city_name": city})
			doc.insert(ignore_permissions=True)
			self.track("Samaaja Cities", doc.name)

		source = f"TestSrc-{self.suffix}"
		if not frappe.db.exists("Program Source", source):
			doc = frappe.get_doc({"doctype": "Program Source", "source_type": source})
			doc.insert(ignore_permissions=True)
			self.track("Program Source", doc.name)

		sub = f"TestSub-{self.suffix}"
		if not frappe.db.exists("Program Sub Source", sub):
			doc = frappe.get_doc(
				{
					"doctype": "Program Sub Source",
					"sub_source": sub,
					"program_source": source,
				}
			)
			doc.insert(ignore_permissions=True)
			self.track("Program Sub Source", doc.name)

		return city, source, sub

	def _create_program(self):
		city, source, sub = self._ensure_program_deps()
		with patch(
			"solve_ninja.solve_ninja.doctype.program.program.Program.update_flow_keyword",
			lambda self: None,
		), patch(
			"solve_ninja.solve_ninja.doctype.program.program.Program.generate_qr_code",
			lambda self, url: None,
		), patch(
			"solve_ninja.solve_ninja.doctype.program.program.Program.update_checkin_url",
			lambda self: None,
		):
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
		if frappe.db.exists("User Organization", self.program_name):
			self.track("User Organization", self.program_name)
		return program

	def test_program_validate_creates_user_organization(self):
		program = self._create_program()
		self.assertEqual(program.name, self.program_name)
		self.assertTrue(frappe.db.exists("User Organization", self.program_name))
		self.assertEqual(
			frappe.db.get_value("User Organization", self.program_name, "org_id"),
			self.program_name,
		)

		# Re-save must not fail / duplicate
		with patch(
			"solve_ninja.solve_ninja.doctype.program.program.Program.update_flow_keyword",
			lambda self: None,
		), patch(
			"solve_ninja.solve_ninja.doctype.program.program.Program.generate_qr_code",
			lambda self, url: None,
		), patch(
			"solve_ninja.solve_ninja.doctype.program.program.Program.update_checkin_url",
			lambda self: None,
		):
			program.reload()
			program.save(ignore_permissions=True)

		self.assertEqual(frappe.db.count("User Organization", {"name": self.program_name}), 1)

	def test_assign_user_organization_sets_metadata(self):
		self._create_program()

		mobile = f"91{self.suffix}"
		email = f"{mobile}@solveninja.org"
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "OrgTest",
				"mobile_no": mobile,
				"send_welcome_email": 0,
			}
		)
		user.insert(ignore_permissions=True)
		self.track("User", user.name)
		if frappe.db.exists("Ninja Profile", user.name):
			self.track("Ninja Profile", user.name)
		if frappe.db.exists("User Metadata", user.name):
			self.track("User Metadata", user.name)

		assign_user_organization(user.name, self.program_name)
		self.assertEqual(
			frappe.db.get_value("User Metadata", user.name, "org_id"),
			self.program_name,
		)

	def test_add_user_async_assigns_org(self):
		from solve_ninja.utils import add_user_async

		self._create_program()

		mobile = f"91{self.suffix}"
		email = f"{mobile}@solveninja.org"

		add_user_async(mobile, whatsapp_name="New Ninja", user_organization=self.program_name)

		self.assertTrue(frappe.db.exists("User", email))
		self.track("User", email)
		if frappe.db.exists("Ninja Profile", email):
			self.track("Ninja Profile", email)
		if frappe.db.exists("User Metadata", email):
			self.track("User Metadata", email)

		self.assertEqual(
			frappe.db.get_value("User Metadata", email, "org_id"),
			self.program_name,
		)

	def test_program_checkin_new_user_gets_org(self):
		self._create_program()

		mobile = f"91{self.suffix}"
		email = f"{mobile}@solveninja.org"

		import frappe.utils.background_jobs as bg

		original_enqueue = bg.enqueue

		def enqueue_now(method, **kwargs):
			kwargs["now"] = True
			return original_enqueue(method, **kwargs)

		with patch("frappe.enqueue", side_effect=enqueue_now), patch(
			"frappe.utils.background_jobs.enqueue", side_effect=enqueue_now
		):
			result = _parse_response(
				program_checkin(mobile=mobile, program_id=self.program_name, whatsapp_name="Checkin User")
			)

		self.assertEqual(result.get("status_code"), 200, result)
		self.track("User", email)
		if frappe.db.exists("Ninja Profile", email):
			self.track("Ninja Profile", email)
		if frappe.db.exists("User Metadata", email):
			self.track("User Metadata", email)

		self.assertEqual(
			frappe.db.get_value("User Metadata", email, "org_id"),
			self.program_name,
		)
		self.assertTrue(
			frappe.db.exists("Program Participation", {"user": email, "program": self.program_name})
		)

	def test_program_checkin_existing_user_overwrites_org(self):
		self._create_program()

		other_org = f"OtherOrg-{self.suffix}"
		frappe.get_doc(
			{
				"doctype": "User Organization",
				"org_name": other_org,
				"org_id": other_org,
			}
		).insert(ignore_permissions=True)
		self.track("User Organization", other_org)

		mobile = f"91{self.suffix}"
		email = f"{mobile}@solveninja.org"
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Existing",
				"mobile_no": mobile,
				"send_welcome_email": 0,
			}
		)
		user.insert(ignore_permissions=True)
		self.track("User", email)
		if frappe.db.exists("Ninja Profile", email):
			self.track("Ninja Profile", email)

		assign_user_organization(email, other_org)
		if frappe.db.exists("User Metadata", email):
			self.track("User Metadata", email)

		self.assertEqual(
			frappe.db.get_value("User Metadata", email, "org_id"),
			other_org,
		)

		result = _parse_response(program_checkin(mobile=mobile, program_id=self.program_name))
		self.assertEqual(result.get("status_code"), 200, result)
		self.assertEqual(
			frappe.db.get_value("User Metadata", email, "org_id"),
			self.program_name,
		)
		self.assertTrue(
			frappe.db.exists("Program Participation", {"user": email, "program": self.program_name})
		)
