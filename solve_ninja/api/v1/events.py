import frappe
from samaaja.api.common import custom_response

from solve_ninja.models.result import Result
from solve_ninja.services.events_manager import EventsManager
from solve_ninja.utils import log_integration_request, parse_request_data

_SERVICE_NAME = "Upload Event Attachment"
_REQUEST_DESCRIPTION = "Upload file to Events attachment1"
_ERROR_TITLE = "Upload Event Attachment"


@frappe.whitelist()
def upload_attachment():
	"""
	Upload one attachment for optional linking to an Events document.

	Request Body/Form:
	- event_id (string, optional): If provided and an Events record exists, sets attachment1 on it.
	- file (multipart file, optional): File to upload
	- file_url/link/url (string, optional): URL to download and upload

	Provide exactly one of file or file_url/link/url.
	If event_id is omitted or does not exist, the file is saved only; response includes file_url for a later event update.
	"""
	try:
		request_data = _parse_upload_request_data()
		return EventsManager.upload_attachment(request_data).to_custom_response()
	except Exception as e:
		parse_failure = Result.failure(
			message="Failed to parse request data",
			error_data={
				"error": str(e),
				"traceback": frappe.get_traceback(),
			},
		)
		try:
			log_integration_request(
				request_data={},
				response_data=parse_failure.to_dict(),
				service_name=_SERVICE_NAME,
				request_description=_REQUEST_DESCRIPTION,
				error_data=parse_failure.error_data,
				reference_doctype=None,
				reference_docname=None,
				error_title=_ERROR_TITLE,
			)
		except Exception as log_exc:
			frappe.log_error(
				f"Event attachment upload integration logging failed: {str(log_exc)}\n{frappe.get_traceback()}",
				f"{_ERROR_TITLE} Integration Request Logging Error",
			)
		return custom_response(
			message="Failed to parse request data",
			data={"error": str(e)},
			status_code=500,
			error=True,
		)


def _parse_upload_request_data():
	if frappe.request.files or frappe.form_dict:
		return frappe.form_dict or {}
	return parse_request_data()
