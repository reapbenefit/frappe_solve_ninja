# Copyright (c) 2025, ReapBenefit and Contributors
# See license.txt

import json
import random

import frappe
from frappe.tests.utils import FrappeTestCase

from solve_ninja.api.common import update_user


class UpdateUserTestDataFactory:
	"""Create and clean up users used by update_user API tests."""

	def __init__(self):
		self.created_docs = []
		self.suffix = str(random.randint(1000000000, 9999999999))
		self.prefix = f"upd-usr-{self.suffix}"
		self.mobile = f"91{self.suffix}"
		self.user_name = f"{self.mobile}@solveninja.org"
		self.initial_city = f"{self.prefix}-Chennai"

	def track(self, doctype, name):
		self.created_docs.append((doctype, name))
		return name

	def ensure_gender(self, gender_name):
		if not frappe.db.exists("Gender", gender_name):
			doc = frappe.get_doc({"doctype": "Gender", "gender": gender_name})
			doc.flags.ignore_permissions = True
			doc.insert()
			self.track("Gender", doc.name)

	def ensure_samaaja_city(self, city_name):
		if not frappe.db.exists("Samaaja Cities", city_name):
			doc = frappe.get_doc({"doctype": "Samaaja Cities", "city_name": city_name})
			doc.flags.ignore_permissions = True
			doc.insert()
			self.track("Samaaja Cities", doc.name)
		elif ("Samaaja Cities", city_name) not in self.created_docs:
			# Track for cleanup only if this factory created a unique prefixed city
			if city_name.startswith(self.prefix):
				self.track("Samaaja Cities", city_name)
		return city_name

	def create_test_user(self, with_metadata=True):
		self.ensure_gender("Female")
		self.ensure_gender("Male")
		self.ensure_samaaja_city(self.initial_city)

		if frappe.db.exists("User", self.user_name):
			frappe.delete_doc("User", self.user_name, force=True, ignore_permissions=True)

		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": self.user_name,
				"first_name": "InitialName",
				"last_name": "Test",
				"mobile_no": self.mobile,
				"gender": "Male",
				"enabled": 1,
				"send_welcome_email": 0,
			}
		)
		if frappe.get_meta("User").has_field("city"):
			user.city = self.initial_city
		if frappe.get_meta("User").has_field("age"):
			user.age = 20
		user.flags.ignore_permissions = True
		user.insert()
		self.track("User", user.name)

		if frappe.db.exists("Ninja Profile", user.name):
			self.track("Ninja Profile", user.name)

		if with_metadata:
			if frappe.db.exists("User Metadata", user.name):
				frappe.db.set_value(
					"User Metadata",
					user.name,
					{"city": self.initial_city, "year_of_birth": 2000},
				)
			else:
				meta = frappe.get_doc(
					{
						"doctype": "User Metadata",
						"user": user.name,
						"city": self.initial_city,
						"year_of_birth": 2000,
					}
				)
				meta.flags.ignore_permissions = True
				meta.insert()
			self.track("User Metadata", user.name)

		frappe.db.commit()
		return user.name

	def cleanup(self):
		# Integration Requests for this user
		for name in frappe.get_all(
			"Integration Request",
			filters={
				"integration_request_service": "Update User API",
				"reference_docname": self.user_name,
			},
			pluck="name",
		):
			frappe.delete_doc("Integration Request", name, force=True, ignore_permissions=True)

		# IRs without reference (e.g. missing mobile / not found) that mention our mobile/prefix
		for name in frappe.get_all(
			"Integration Request",
			filters={"integration_request_service": "Update User API"},
			fields=["name", "data"],
			order_by="creation desc",
			limit_page_length=50,
		):
			data = name.get("data") or ""
			if self.mobile in data or self.prefix in data or "910000000000" in data:
				frappe.delete_doc(
					"Integration Request", name["name"], force=True, ignore_permissions=True
				)

		# Prefixed Samaaja Cities created during tests (may not be in created_docs if API created them)
		for city_name in frappe.get_all(
			"Samaaja Cities",
			filters={"city_name": ["like", f"{self.prefix}%"]},
			pluck="name",
		):
			if ("Samaaja Cities", city_name) not in self.created_docs:
				self.created_docs.append(("Samaaja Cities", city_name))

		for doctype, name in reversed(self.created_docs):
			if frappe.db.exists(doctype, name):
				try:
					frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
				except Exception:
					frappe.log_error(
						title="Update User Test Cleanup Failed",
						message=f"Failed to delete {doctype} {name}",
					)
		self.created_docs = []
		frappe.db.commit()


def call_update_user(payload):
	"""Invoke update_user with form_dict payload; return (http_status, body_dict)."""
	frappe.local.form_dict = frappe._dict(payload)
	# Bound request so log_integration_request / get_url work outside HTTP
	if not frappe.conf.get("host_name"):
		frappe.conf.host_name = frappe.local.site

	class _TestRequest:
		host = frappe.conf.host_name or frappe.local.site or "localhost"
		url = f"http://{host}/api/method/solve_ninja.api.common.update_user"
		headers = {"Content-Type": "application/json"}

	frappe.local.request = _TestRequest()
	response = update_user()
	body = json.loads(response.get_data(as_text=True))
	return response.status_code, body


class TestUpdateUser(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.factory = UpdateUserTestDataFactory()
		self.user_name = self.factory.create_test_user(with_metadata=True)
		self.mobile = self.factory.mobile
		self.prefix = self.factory.prefix
		self.initial_city = self.factory.initial_city

	def tearDown(self):
		self.factory.cleanup()
		frappe.set_user("Administrator")

	def _latest_integration_request(self):
		return frappe.get_all(
			"Integration Request",
			filters={
				"integration_request_service": "Update User API",
				"reference_docname": self.user_name,
			},
			fields=["name", "status", "error", "output"],
			order_by="creation desc",
			limit_page_length=1,
		)

	def test_full_glific_payload_updates_user_and_metadata(self):
		city = f"{self.prefix}-Nalbari"
		old_username = frappe.db.get_value("User", self.user_name, "username")
		status_code, body = call_update_user(
			{
				"year_of_birth": "2002",
				"organization_id": 15,
				"org_id": "sbmassam",
				"mobile": self.mobile,
				"gender": "Female",
				"first_name": "Rumi Mitra",
				"city": city,
				"age": "24",
			}
		)

		self.assertEqual(status_code, 200)
		self.assertEqual(body["status"], "success")
		self.assertIn("/user-profile/", body["data"] or "")

		user = frappe.db.get_value(
			"User",
			self.user_name,
			["first_name", "full_name", "gender", "age", "city", "username"],
			as_dict=True,
		)
		self.assertEqual(user.first_name, "Rumi Mitra")
		self.assertEqual(user.full_name, "Rumi Mitra Test")
		self.assertEqual(user.gender, "Female")
		self.assertNotEqual(user.username, old_username)
		self.assertTrue(user.username)
		self.assertIn(f"/user-profile/{user.username}", body["data"] or "")
		if frappe.get_meta("User").has_field("age"):
			self.assertEqual(user.age, 24)
		if frappe.get_meta("User").has_field("city"):
			self.assertEqual(user.city, city)

		meta = frappe.db.get_value(
			"User Metadata",
			self.user_name,
			["city", "year_of_birth", "full_name"],
			as_dict=True,
		)
		self.assertEqual(meta.city, city)
		self.assertEqual(meta.year_of_birth, 2002)
		self.assertEqual(meta.full_name, "Rumi Mitra Test")
		self.assertTrue(frappe.db.exists("Samaaja Cities", city))

		irs = self._latest_integration_request()
		self.assertTrue(irs)
		self.assertEqual(irs[0].status, "Completed")

	def test_first_name_change_syncs_metadata_and_regenerates_username(self):
		old_username = frappe.db.get_value("User", self.user_name, "username")
		old_city = frappe.db.get_value("User Metadata", self.user_name, "city")
		old_yob = frappe.db.get_value("User Metadata", self.user_name, "year_of_birth")

		status_code, body = call_update_user(
			{
				"mobile": self.mobile,
				"first_name": "NewName",
			}
		)

		self.assertEqual(status_code, 200)
		self.assertEqual(body["status"], "success")

		user = frappe.db.get_value(
			"User",
			self.user_name,
			["first_name", "full_name", "username"],
			as_dict=True,
		)
		self.assertEqual(user.first_name, "NewName")
		self.assertEqual(user.full_name, "NewName Test")
		self.assertNotEqual(user.username, old_username)
		self.assertTrue(user.username.startswith("newname-test-"))
		self.assertIn(f"/user-profile/{user.username}", body["data"] or "")

		meta = frappe.db.get_value(
			"User Metadata",
			self.user_name,
			["full_name", "city", "year_of_birth"],
			as_dict=True,
		)
		self.assertEqual(meta.full_name, "NewName Test")
		self.assertEqual(meta.city, old_city)
		self.assertEqual(meta.year_of_birth, old_yob)

	def test_same_first_name_does_not_regenerate_username(self):
		old_username = frappe.db.get_value("User", self.user_name, "username")

		status_code, body = call_update_user(
			{
				"mobile": self.mobile,
				"first_name": "InitialName",
			}
		)

		self.assertEqual(status_code, 200)
		self.assertEqual(body["status"], "success")

		user = frappe.db.get_value(
			"User",
			self.user_name,
			["first_name", "username"],
			as_dict=True,
		)
		self.assertEqual(user.first_name, "InitialName")
		self.assertEqual(user.username, old_username)
		self.assertIn(f"/user-profile/{old_username}", body["data"] or "")

		self.assertEqual(
			frappe.db.get_value("User Metadata", self.user_name, "full_name"),
			"InitialName Test",
		)

	def test_year_of_birth_without_city(self):
		status_code, body = call_update_user(
			{
				"mobile": self.mobile,
				"year_of_birth": "1999",
			}
		)

		self.assertEqual(status_code, 200)
		self.assertEqual(body["status"], "success")

		meta = frappe.db.get_value(
			"User Metadata",
			self.user_name,
			["city", "year_of_birth"],
			as_dict=True,
		)
		self.assertEqual(meta.year_of_birth, 1999)
		self.assertEqual(meta.city, self.initial_city)

		if frappe.get_meta("User").has_field("city"):
			self.assertEqual(
				frappe.db.get_value("User", self.user_name, "city"),
				self.initial_city,
			)

	def test_city_creates_samaaja_cities_and_links(self):
		city = f"{self.prefix}-Guwahati"
		self.assertFalse(frappe.db.exists("Samaaja Cities", city))

		status_code, body = call_update_user(
			{
				"mobile": self.mobile,
				"city": city,
			}
		)

		self.assertEqual(status_code, 200)
		self.assertEqual(body["status"], "success")
		self.assertTrue(frappe.db.exists("Samaaja Cities", {"city_name": city}))

		meta_city = frappe.db.get_value("User Metadata", self.user_name, "city")
		self.assertEqual(meta_city, city)

		if frappe.get_meta("User").has_field("city"):
			self.assertEqual(frappe.db.get_value("User", self.user_name, "city"), city)

	def test_missing_mobile(self):
		status_code, body = call_update_user({"first_name": "NoMobile"})

		self.assertEqual(status_code, 500)
		self.assertEqual(body["status"], "error")
		self.assertIn("Mobile number is mandatory", body["message"])

		irs = frappe.get_all(
			"Integration Request",
			filters={
				"integration_request_service": "Update User API",
				"data": ["like", "%NoMobile%"],
			},
			fields=["name", "status", "error"],
			order_by="creation desc",
			limit_page_length=1,
		)
		self.assertTrue(irs)
		self.assertEqual(irs[0].status, "Failed")
		self.assertTrue(irs[0].error)

	def test_invalid_mobile(self):
		status_code, body = call_update_user({"mobile": "12345"})

		self.assertEqual(status_code, 500)
		self.assertEqual(body["status"], "error")
		self.assertIn("10 or 12 digits", body["message"])

	def test_user_not_found(self):
		missing_mobile = "910000000000"
		status_code, body = call_update_user(
			{"mobile": missing_mobile, "first_name": "Ghost"}
		)

		self.assertEqual(status_code, 404)
		self.assertEqual(body["status"], "error")
		self.assertIn(missing_mobile, body["message"])

		irs = frappe.get_all(
			"Integration Request",
			filters={
				"integration_request_service": "Update User API",
				"data": ["like", f"%{missing_mobile}%"],
			},
			fields=["name", "status", "error"],
			order_by="creation desc",
			limit_page_length=1,
		)
		self.assertTrue(irs)
		self.assertEqual(irs[0].status, "Failed")
		self.assertTrue(irs[0].error)

	def test_forced_failure_creates_error_log(self):
		before_yob = frappe.db.get_value("User Metadata", self.user_name, "year_of_birth")
		before_city = frappe.db.get_value("User Metadata", self.user_name, "city")

		status_code, body = call_update_user(
			{
				"mobile": self.mobile,
				"year_of_birth": "not-a-year",
			}
		)

		self.assertEqual(status_code, 500)
		self.assertEqual(body["status"], "error")

		self.assertEqual(
			frappe.db.get_value("User Metadata", self.user_name, "year_of_birth"),
			before_yob,
		)
		self.assertEqual(
			frappe.db.get_value("User Metadata", self.user_name, "city"),
			before_city,
		)

		error_logs = frappe.db.sql(
			"""
			SELECT name, method
			FROM `tabError Log`
			WHERE method = %s
			ORDER BY creation DESC
			LIMIT 1
			""",
			("Update User Error",),
			as_dict=True,
		)
		self.assertTrue(error_logs)
		self.assertEqual(error_logs[0].method, "Update User Error")

		irs = self._latest_integration_request()
		self.assertTrue(irs)
		self.assertEqual(irs[0].status, "Failed")
