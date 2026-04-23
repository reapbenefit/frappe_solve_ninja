# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, now_datetime
from collections import defaultdict


class ChatSessionArchive(Document):
	pass


def archive_old_chat_records():
	"""
	Daily scheduled task to archive Chat History and Chat Feedback records
	older than 4 weeks into Chat Session Archive (one document per session_id).
	Each message row includes its feedback inline (chat_feedback, chat_feedback_comment).
	"""
	cutoff = add_to_date(now_datetime(), weeks=-4)
	sessions_per_batch = 500
	sessions_archived = 0

	# 1. Get Chat History records older than 4 weeks
	old_chat_history = frappe.get_all(
		"Chat History",
		filters={"creation": ["<", cutoff]},
		fields=[
			"name",
			"event_id",
			"user",
			"role",
			"content",
			"response_type",
			"session_id",
			"use_case",
			"sequence_number",
			"creation",
		],
	)

	if not old_chat_history:
		frappe.logger("scheduler").info("No Chat History records to archive")
		return

	# 2. Group by session_id
	sessions = defaultdict(list)
	for ch in old_chat_history:
		session_id = ch.get("session_id") or ""
		if session_id:
			sessions[session_id].append(ch)

	# Limit sessions per run
	session_ids = list(sessions.keys())[:sessions_per_batch]

	for session_id in session_ids:
		# Skip if already archived
		if frappe.db.exists("Chat Session Archive", {"session_id": session_id}):
			continue

		messages_data = sessions[session_id]
		# Sort by sequence_number, then creation
		messages_data.sort(
			key=lambda m: (m.get("sequence_number") or 0, m.get("creation") or "")
		)

		chat_history_names = [m.get("name") for m in messages_data]

		# 3. Get Chat Feedback for these messages and index by chat_history_message
		chat_feedback_list = frappe.get_all(
			"Chat Feedback",
			filters={"chat_history_message": ["in", chat_history_names]},
			fields=["name", "chat_history_message", "chat_feedback", "chat_feedback_comment"],
		)
		feedback_by_message = {
			cf.get("chat_history_message"): cf for cf in chat_feedback_list
		}

		# 4. Build messages child table rows with inline feedback
		messages_rows = []
		for m in messages_data:
			msg_name = m.get("name")
			fb = feedback_by_message.get(msg_name)
			messages_rows.append(
				{
					"source_chat_history_name": msg_name,
					"role": m.get("role"),
					"content": m.get("content") or "",
					"response_type": m.get("response_type") or "",
					"sequence_number": m.get("sequence_number") or 0,
					"user": m.get("user"),
					"event_id": m.get("event_id") or "",
					"message_creation": m.get("creation"),
					"chat_feedback": fb.get("chat_feedback") if fb else None,
					"chat_feedback_comment": fb.get("chat_feedback_comment") if fb else "",
				}
			)

		first_message = messages_data[0] if messages_data else {}
		use_case = first_message.get("use_case") or ""
		first_message_creation = first_message.get("creation")

		try:
			archive_doc = frappe.get_doc(
				{
					"doctype": "Chat Session Archive",
					"session_id": session_id,
					"use_case": use_case,
					"first_message_creation": first_message_creation,
					"messages": messages_rows,
				}
			)
			archive_doc.insert(ignore_permissions=True)

			# 5. Delete Chat Feedback first
			for cf in chat_feedback_list:
				frappe.delete_doc(
					"Chat Feedback",
					cf.get("name"),
					ignore_permissions=True,
				)

			# 6. Delete Chat History
			for m in messages_data:
				frappe.delete_doc("Chat History", m.get("name"), ignore_permissions=True)

			sessions_archived += 1
		except Exception:
			frappe.log_error(
				title="Chat Session Archive Error",
				message=frappe.get_traceback(),
			)

	frappe.db.commit()

	frappe.logger("scheduler").info(
		f"Archived {sessions_archived} chat sessions to Chat Session Archive"
	)
