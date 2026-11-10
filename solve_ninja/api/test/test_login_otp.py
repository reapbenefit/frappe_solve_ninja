# Copyright (c) 2026, ReapBenefit and Contributors
# See license.txt

import random
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from solve_ninja.api.auth import OTP_SENDS_PER_HOUR, send_otp

SEND_HSM_OTP = "solve_ninja.api.auth.send_hsm_otp"


class TestSendOtp(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.mobile = str(random.randint(6000000000, 9999999999))
		self.email = f"91{self.mobile}@solveninja.org"
		self._clear_rate_limit()

	def tearDown(self):
		frappe.db.rollback()
		self._clear_rate_limit()
		frappe.db.delete("Login OTP", {"user": self.email})
		for doctype in ("Ninja Profile", "User Metadata", "User"):
			if frappe.db.exists(doctype, self.email):
				frappe.delete_doc(doctype, self.email, force=True, ignore_permissions=True)
		frappe.db.commit()

	def _clear_rate_limit(self):
		frappe.cache.delete_value(f"sn:login_otp_sends:{self.mobile}")

	def _create_user(self, enabled=1):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": self.email,
				"first_name": "OtpTest",
				"mobile_no": f"91{self.mobile}",
				"enabled": enabled,
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)

	def test_unknown_number_returns_user_not_found(self):
		with patch(SEND_HSM_OTP) as send_hsm:
			result = send_otp(self.mobile)

		self.assertFalse(result["success"])
		self.assertEqual(result["reason"], "user_not_found")
		send_hsm.assert_not_called()

	def test_disabled_user_is_not_sent_to_signup(self):
		self._create_user(enabled=0)

		with patch(SEND_HSM_OTP) as send_hsm:
			result = send_otp(self.mobile)

		self.assertEqual(result["reason"], "user_disabled")
		send_hsm.assert_not_called()

	def test_existing_user_gets_otp(self):
		self._create_user()

		with patch(SEND_HSM_OTP, return_value=True):
			result = send_otp(self.mobile)

		self.assertTrue(result["success"], result)
		self.assertTrue(frappe.db.exists("Login OTP", {"user": self.email, "status": "Pending"}))

	def test_whatsapp_failure_has_its_own_reason(self):
		self._create_user()

		with patch(SEND_HSM_OTP, return_value=False):
			result = send_otp(self.mobile)

		self.assertEqual(result["reason"], "whatsapp_failed")

	def test_rate_limit_counts_10_and_12_digit_formats_together(self):
		self._create_user()

		with patch(SEND_HSM_OTP, return_value=True) as send_hsm:
			for attempt in range(OTP_SENDS_PER_HOUR):
				number = self.mobile if attempt % 2 else f"91{self.mobile}"
				self.assertTrue(send_otp(number)["success"], attempt)
			blocked = send_otp(self.mobile)

		self.assertFalse(blocked["success"])
		self.assertEqual(blocked["reason"], "rate_limited")
		self.assertEqual(send_hsm.call_count, OTP_SENDS_PER_HOUR)
