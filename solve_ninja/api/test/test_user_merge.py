# Copyright (c) 2025, ReapBenefit and Contributors
# See license.txt

import random

import frappe
from frappe.exceptions import PermissionError, ValidationError
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, cint, flt, now_datetime

from solve_ninja.api.user_merge import get_merge_preview, merge_users


class MergeTestDataFactory:
	"""Create and clean up merge-test users and related records."""

	def __init__(self):
		self.created_docs = []
		self.suffix = str(random.randint(1000000000, 9999999999))
		self.prefix = f"merge-test-{self.suffix}"

	def track(self, doctype, name):
		self.created_docs.append((doctype, name))
		return name

	def create_merge_test_user(self, mobile_suffix, first_name, profile_overrides=None):
		email = f"91{mobile_suffix}@solveninja.org"
		mobile = f"91{mobile_suffix}"

		if frappe.db.exists("User", email):
			frappe.delete_doc("User", email, force=True, ignore_permissions=True)

		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"mobile_no": mobile,
				"enabled": 1,
			}
		)
		user.flags.ignore_permissions = True
		user.insert()
		self.track("User", user.name)

		profile_overrides = profile_overrides or {}
		user_fields = profile_overrides.get("user") or {}
		if user_fields:
			user_doc = frappe.get_doc("User", user.name)
			for fieldname, value in user_fields.items():
				user_doc.set(fieldname, value)
			user_doc.flags.ignore_permissions = True
			user_doc.save(ignore_permissions=True)

		if frappe.db.exists("User Metadata", user.name):
			metadata_fields = profile_overrides.get("user_metadata") or {}
			if metadata_fields:
				meta = frappe.get_doc("User Metadata", user.name)
				for fieldname, value in metadata_fields.items():
					meta.set(fieldname, value)
				meta.flags.ignore_permissions = True
				meta.save(ignore_permissions=True)

		if frappe.db.exists("Ninja Profile", user.name):
			ninja_fields = profile_overrides.get("ninja_profile") or {}
			if ninja_fields:
				ninja = frappe.get_doc("Ninja Profile", user.name)
				for fieldname, value in ninja_fields.items():
					ninja.set(fieldname, value)
				ninja.flags.ignore_permissions = True
				ninja.save(ignore_permissions=True)

		return user.name

	def get_or_create_event_masters(self):
		event_type = frappe.db.get_value("Event Type", {}, "name")
		event_category = frappe.db.get_value("Event Category", {}, "name")
		event_sub_category = frappe.db.get_value("Event Sub Category", {}, "name")

		if not event_type:
			event_type = self.prefix + "-type"
			doc = frappe.get_doc({"doctype": "Event Type", "type": event_type})
			doc.flags.ignore_permissions = True
			doc.insert()
			self.track("Event Type", doc.name)

		if not event_category:
			event_category = self.prefix + "-category"
			doc = frappe.get_doc({"doctype": "Event Category", "category": event_category})
			doc.flags.ignore_permissions = True
			doc.insert()
			self.track("Event Category", doc.name)

		if not event_sub_category:
			event_sub_category = self.prefix + "-subcategory"
			doc = frappe.get_doc(
				{"doctype": "Event Sub Category", "subcategory": event_sub_category}
			)
			doc.flags.ignore_permissions = True
			doc.insert()
			self.track("Event Sub Category", doc.name)

		return event_type, event_category, event_sub_category

	def create_event(self, user, hours, title_suffix):
		event_type, event_category, event_sub_category = self.get_or_create_event_masters()
		doc = frappe.get_doc(
			{
				"doctype": "Events",
				"title": f"{self.prefix}-{title_suffix}",
				"type": event_type,
				"category": event_category,
				"subcategory": event_sub_category,
				"description": f"Merge test event {title_suffix}",
				"user": user,
				"hours_invested": hours,
			}
		)
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.insert()
		self.track("Events", doc.name)
		return doc.name

	def get_or_create_badge(self, title_suffix):
		title = f"{self.prefix}-{title_suffix}"
		if frappe.db.exists("Badge", title):
			return title

		doc = frappe.get_doc({"doctype": "Badge", "title": title})
		doc.flags.ignore_permissions = True
		doc.insert()
		self.track("Badge", doc.name)
		return doc.name

	def create_user_badge(self, user, badge, badge_count=1, active=1):
		doc = frappe.get_doc(
			{
				"doctype": "User badge",
				"user": user,
				"badge": badge,
				"badge_count": badge_count,
				"active": active,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		self.track("User badge", doc.name)
		return doc.name

	def create_login_otp(self, user):
		mobile = frappe.db.get_value("User", user, "mobile_no")
		doc = frappe.get_doc(
			{
				"doctype": "Login OTP",
				"mobile": mobile,
				"user": user,
				"otp": "123456",
				"valid_till": add_to_date(now_datetime(), minutes=10),
				"status": "Pending",
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		self.track("Login OTP", doc.name)
		return doc.name

	def create_limited_user(self, mobile_suffix):
		email = f"91{mobile_suffix}@solveninja.org"
		if frappe.db.exists("User", email):
			frappe.delete_doc("User", email, force=True, ignore_permissions=True)

		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "LimitedUser",
				"mobile_no": f"91{mobile_suffix}",
				"enabled": 1,
			}
		)
		user.flags.ignore_permissions = True
		user.insert()
		user.add_roles("Solve Ninja")
		self.track("User", user.name)
		return user.name

	def seed_standard_merge_scenario(self):
		source_suffix = self.suffix + "1"
		target_suffix = self.suffix + "2"

		source = self.create_merge_test_user(
			source_suffix,
			"SourceName",
			{
				"user": {"bio": "Source bio"},
				"user_metadata": {
					"story": "Source story",
					"summary": "Source summary",
				},
			},
		)
		target = self.create_merge_test_user(
			target_suffix,
			"TargetName",
			{
				"user": {"bio": ""},
				"user_metadata": {},
			},
		)

		self.create_event(source, 2, "source-1")
		self.create_event(source, 3, "source-2")
		self.create_event(target, 5, "target-1")

		badge_a = self.get_or_create_badge("badge-a")
		badge_b = self.get_or_create_badge("badge-b")
		self.create_user_badge(source, badge_a, badge_count=3)
		self.create_user_badge(source, badge_b, badge_count=1)
		self.create_user_badge(target, badge_a, badge_count=2)

		return {
			"source": source,
			"target": target,
			"badge_a": badge_a,
			"badge_b": badge_b,
		}

	def cleanup(self):
		for doctype, name in reversed(self.created_docs):
			if frappe.db.exists(doctype, name):
				try:
					frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
				except Exception:
					frappe.log_error(
						title="Merge Test Cleanup Failed",
						message=f"Failed to delete {doctype} {name}",
					)
		self.created_docs = []
		frappe.db.commit()


class TestUserMerge(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.factory = MergeTestDataFactory()

	def tearDown(self):
		self.factory.cleanup()
		frappe.set_user("Administrator")

	def test_merge_preview_counts(self):
		data = self.factory.seed_standard_merge_scenario()
		preview = get_merge_preview(data["source"], data["target"])

		self.assertEqual(preview["reassignments"].get("Events.user"), 2)
		self.assertEqual(preview["badge_summary"]["badges_to_reassign"], 1)
		self.assertEqual(preview["badge_summary"]["badges_to_sum"], 1)
		self.assertEqual(preview["ninja_profile"]["projected"]["contributions"], 3)
		self.assertEqual(preview["ninja_profile"]["projected"]["hours_invested"], 10)
		self.assertIn("bio", preview["profile_fields"]["user"])
		self.assertIn("story", preview["profile_fields"]["user_metadata"])

	def test_merge_reassigns_events_and_recomputes_ninja_profile(self):
		data = self.factory.seed_standard_merge_scenario()
		merge_users(data["source"], data["target"])

		self.assertEqual(frappe.db.count("Events", {"user": data["source"]}), 0)
		self.assertEqual(frappe.db.count("Events", {"user": data["target"]}), 3)

		ninja = frappe.db.get_value(
			"Ninja Profile",
			data["target"],
			["contributions", "hours_invested"],
			as_dict=True,
		)
		self.assertEqual(cint(ninja.contributions), 3)
		self.assertEqual(flt(ninja.hours_invested), 10)

	def test_merge_sums_duplicate_user_badges(self):
		data = self.factory.seed_standard_merge_scenario()
		merge_users(data["source"], data["target"])

		target_badge = frappe.db.get_value(
			"User badge",
			{"user": data["target"], "badge": data["badge_a"]},
			["badge_count", "name"],
			as_dict=True,
		)
		self.assertIsNotNone(target_badge)
		self.assertEqual(cint(target_badge.badge_count), 5)
		self.assertEqual(
			frappe.db.count("User badge", {"user": data["source"], "badge": data["badge_a"]}),
			0,
		)

	def test_merge_reassigns_unique_user_badges(self):
		data = self.factory.seed_standard_merge_scenario()
		merge_users(data["source"], data["target"])

		self.assertEqual(
			frappe.db.count("User badge", {"user": data["target"], "badge": data["badge_b"]}),
			1,
		)
		self.assertEqual(frappe.db.count("User badge", {"user": data["source"]}), 0)

	def test_merge_fills_empty_profile_fields_only(self):
		data = self.factory.seed_standard_merge_scenario()
		merge_users(data["source"], data["target"])

		target_user = frappe.db.get_value(
			"User",
			data["target"],
			["first_name", "bio"],
			as_dict=True,
		)
		target_meta = frappe.db.get_value(
			"User Metadata",
			data["target"],
			["story", "summary"],
			as_dict=True,
		)

		self.assertEqual(target_user.first_name, "TargetName")
		self.assertEqual(target_user.bio, "Source bio")
		self.assertEqual(target_meta.story, "Source story")
		self.assertEqual(target_meta.summary, "Source summary")

	def test_merge_disables_source_user(self):
		data = self.factory.seed_standard_merge_scenario()
		merge_users(data["source"], data["target"])
		self.assertEqual(frappe.db.get_value("User", data["source"], "enabled"), 0)

	def test_merge_creates_audit_comments(self):
		data = self.factory.seed_standard_merge_scenario()
		merge_users(data["source"], data["target"])

		target_comments = frappe.db.count(
			"Comment",
			{
				"reference_doctype": "User",
				"reference_name": data["target"],
				"comment_type": "Info",
			},
		)
		source_comments = frappe.db.count(
			"Comment",
			{
				"reference_doctype": "User",
				"reference_name": data["source"],
				"comment_type": "Info",
			},
		)
		self.assertGreaterEqual(target_comments, 1)
		self.assertGreaterEqual(source_comments, 1)

	def test_merge_leaves_login_otp_untouched(self):
		data = self.factory.seed_standard_merge_scenario()
		self.factory.create_login_otp(data["source"])
		before = frappe.db.count("Login OTP", {"user": data["source"]})

		merge_users(data["source"], data["target"])

		self.assertEqual(frappe.db.count("Login OTP", {"user": data["source"]}), before)

	def test_merge_requires_system_manager(self):
		data = self.factory.seed_standard_merge_scenario()
		limited_user = self.factory.create_limited_user(self.factory.suffix + "9")
		frappe.set_user(limited_user)

		with self.assertRaises(PermissionError):
			get_merge_preview(data["source"], data["target"])

	def test_merge_validation_errors(self):
		data = self.factory.seed_standard_merge_scenario()

		with self.assertRaises(ValidationError):
			get_merge_preview(data["source"], data["source"])

		with self.assertRaises(ValidationError):
			get_merge_preview("missing@solveninja.org", data["target"])

		with self.assertRaises(ValidationError):
			get_merge_preview("Administrator", data["target"])

	def test_merge_user_event_stats_when_doctype_exists(self):
		if not frappe.db.exists("DocType", "User Event Stats"):
			self.skipTest("User Event Stats doctype not installed on this site")

		data = self.factory.seed_standard_merge_scenario()
		event_type = self.factory.get_or_create_event_masters()[0]

		source_stat = frappe.get_doc(
			{
				"doctype": "User Event Stats",
				"user": data["source"],
				"event_type": event_type,
				"count": 4,
			}
		)
		source_stat.flags.ignore_permissions = True
		source_stat.insert()
		self.factory.track("User Event Stats", source_stat.name)

		target_stat = frappe.get_doc(
			{
				"doctype": "User Event Stats",
				"user": data["target"],
				"event_type": event_type,
				"count": 2,
			}
		)
		target_stat.flags.ignore_permissions = True
		target_stat.insert()
		self.factory.track("User Event Stats", target_stat.name)

		merge_users(data["source"], data["target"])

		merged_count = frappe.db.get_value(
			"User Event Stats",
			{"user": data["target"], "event_type": event_type},
			"count",
		)
		self.assertEqual(cint(merged_count), 6)
		self.assertEqual(
			frappe.db.count("User Event Stats", {"user": data["source"], "event_type": event_type}),
			0,
		)
