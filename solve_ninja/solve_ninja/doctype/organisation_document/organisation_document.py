# Copyright (c) 2026, ReapBenefit and contributors
# For license information, please see license.txt

import mimetypes

import frappe
from frappe import _
from frappe.model.document import Document

from solve_ninja.api.v1.ninja_query_utils import resolve_organization_filters


class OrganisationDocument(Document):
	pass


@frappe.whitelist()
def download_organisation_document(name=None):
	"""
	Stream the file linked to an Organisation Document.

	Organisation Managers may only download documents for their assigned org.
	System Managers may download any organisation document.
	"""
	try:
		doc_name = str(name or "").strip()
		if not doc_name:
			frappe.throw(_("Document name is required"), frappe.ValidationError)

		filters = resolve_organization_filters({}, require_organization=False)
		organization = filters.get("organization")

		doc = frappe.db.get_value(
			"Organisation Document",
			doc_name,
			["org_id", "file", "file_title"],
			as_dict=True,
		)
		if not doc:
			frappe.throw(_("Organisation Document not found"), frappe.DoesNotExistError)

		if organization and doc.org_id != organization:
			frappe.throw(_("Not permitted"), frappe.PermissionError)

		if not doc.file:
			frappe.throw(_("No file attached to this document"), frappe.ValidationError)

		file_doc = frappe.get_doc("File", doc.file)
		file_doc.flags.ignore_permissions = True
		content = file_doc.get_content()

		filename = (doc.file_title or file_doc.file_name or doc.file).strip()
		if not filename:
			filename = "document"

		content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

		frappe.local.response.filename = filename
		frappe.local.response.filecontent = content
		frappe.local.response.type = "download"
		frappe.local.response.content_type = content_type
		frappe.local.response.display_content_as = "attachment"
	except (frappe.PermissionError, frappe.ValidationError, frappe.DoesNotExistError):
		raise
	except Exception as e:
		frappe.log_error(f"Error in download_organisation_document: {str(e)}")
		frappe.throw(_("Download failed. Please try again."))
