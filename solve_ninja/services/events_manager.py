import mimetypes
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import frappe
import requests
from frappe.utils.file_manager import save_file

from solve_ninja.models.result import Result
from solve_ninja.utils import log_integration_request


class EventsManager:
    """Domain manager for Events attachment uploads."""

    @classmethod
    def upload_attachment(cls, request_data: Dict[str, Any]) -> Result:
        service_name = "Upload Event Attachment"
        request_description = "Upload file to Events attachment1"
        error_title = "Upload Event Attachment"

        result = Result.failure(
            message="Failed to upload event attachment",
            error_data=None,
        )
        event_id: Optional[str] = None

        try:
            request_data = dict(request_data or {})
            event_id = request_data.get("event_id") or request_data.get("event")
            event_exists = bool(
                event_id and frappe.db.exists("Events", event_id)
            )
            attach_dn = event_id if event_exists else None

            uploaded_file = frappe.request.files.get("file")
            source_url = cls._get_source_url(request_data)

            has_file = bool(uploaded_file and uploaded_file.filename)
            has_url = bool(source_url)
            if has_file == has_url:
                result = Result.bad_request(
                    message="Provide exactly one of file or file_url/link"
                )
                return result

            if has_file:
                file_doc = cls._save_uploaded_file(uploaded_file, attach_dn)
            else:
                file_doc = cls._save_file_from_url(source_url, attach_dn)

            if event_exists:
                event_doc = frappe.get_doc("Events", attach_dn)
                event_doc.attachment1 = file_doc.file_url
                event_doc.save(ignore_permissions=True)

                result = Result.success(
                    message="Event attachment uploaded successfully",
                    data={
                        "event_updated": True,
                        "event_id": event_doc.name,
                        "file_name": file_doc.file_name,
                        "file_url": file_doc.file_url,
                    },
                )
            else:
                result = Result.success(
                    message="File uploaded successfully",
                    data={
                        "event_updated": False,
                        "event_id": event_id,
                        "file_name": file_doc.file_name,
                        "file_url": file_doc.file_url,
                    },
                )
            return result
        except Exception as exc:
            frappe.log_error(
                f"Error in upload_event_attachment: {str(exc)}\n{frappe.get_traceback()}",
                "Event Attachment API Error",
            )
            result = Result.failure(
                message="Failed to upload event attachment",
                error_data={
                    "error": str(exc),
                    "traceback": frappe.get_traceback(),
                },
            )
            return result
        finally:
            try:
                log_integration_request(
                    request_data=cls._safe_log_request_data(request_data),
                    response_data=result.to_dict(),
                    service_name=service_name,
                    request_description=request_description,
                    error_data=result.error_data if result.error_data else None,
                    reference_doctype="Events" if event_exists else None,
                    reference_docname=attach_dn if event_exists else None,
                    error_title=error_title,
                )
            except Exception as log_exc:
                frappe.log_error(
                    f"Integration request logging failed in EventsManager.upload_attachment: {str(log_exc)}\n{frappe.get_traceback()}",
                    f"{error_title} Integration Request Logging Error",
                )

    @staticmethod
    def _get_source_url(request_data: Dict[str, Any]) -> Optional[str]:
        source_url = (
            request_data.get("file_url")
            or request_data.get("link")
            or request_data.get("url")
        )
        return source_url.strip() if isinstance(source_url, str) else source_url

    @staticmethod
    def _save_uploaded_file(uploaded_file, attach_to_name: Optional[str]):
        content = uploaded_file.stream.read()
        if not content:
            raise ValueError("Uploaded file is empty")

        dt = "Events" if attach_to_name else None
        df = "attachment1" if attach_to_name else None

        return save_file(
            fname=uploaded_file.filename,
            content=content,
            dt=dt,
            dn=attach_to_name,
            is_private=0,
            df=df,
        )

    @classmethod
    def _save_file_from_url(cls, file_url: str, attach_to_name: Optional[str]):
        parsed_url = urlparse(file_url)
        if parsed_url.scheme not in ("http", "https"):
            raise ValueError("file_url/link must be an http or https URL")

        response = requests.get(file_url, timeout=60)
        response.raise_for_status()

        content = response.content
        if not content:
            raise ValueError("Downloaded file is empty")

        filename = cls._filename_from_url_or_headers(file_url, response.headers)

        dt = "Events" if attach_to_name else None
        df = "attachment1" if attach_to_name else None

        return save_file(
            fname=filename,
            content=content,
            dt=dt,
            dn=attach_to_name,
            is_private=0,
            df=df,
        )

    @staticmethod
    def _filename_from_url_or_headers(file_url: str, headers: Dict[str, Any]) -> str:
        parsed_url = urlparse(file_url)
        filename = os.path.basename(parsed_url.path) or "event_attachment"
        if "." in filename:
            return filename

        content_type = headers.get("Content-Type")
        extension = None
        if content_type:
            extension = mimetypes.guess_extension(content_type.split(";")[0].strip())

        return f"{filename}{extension or ''}"

    @staticmethod
    def _safe_log_request_data(request_data: Dict[str, Any]) -> Dict[str, Any]:
        safe_data = dict(request_data or {})
        if frappe.request.files.get("file"):
            safe_data["file"] = frappe.request.files["file"].filename
        return safe_data
