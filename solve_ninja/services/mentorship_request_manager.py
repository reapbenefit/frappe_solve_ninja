import frappe
from typing import Any, Dict, Optional
from solve_ninja.utils import log_integration_request
from solve_ninja.models.result import Result

class MentorshipRequestManager:
    """Domain manager for Mentorship Request workflows."""

    @classmethod
    def create(cls, request_data: Dict[str, Any]) -> Result:
        service_name = "Create Mentorship Request"
        request_description = "Create new mentorship request"
        error_title = "Create Mentorship Request"

        result = Result.new()

        try:
            required_fields = ["mentee_name", "phone"]
            missing_fields = [
                field for field in required_fields if not request_data.get(field)
            ]
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            else:
                mentorship_request = frappe.get_doc(
                    {
                        "doctype": "Mentorship Request",
                        "mentee": request_data.get("mentee_name"),
                        "phone": request_data.get("phone"),
                        "mentee_age": request_data.get("mentee_age"),
                        "mentee_whatsapp_id": request_data.get("mentee_whatsapp_id"),
                        "chat_session_id": request_data.get("chat_session_id"),
                        "discovered_problem": request_data.get("discovered_problem"),
                        "solve_action": cls._normalize_optional_text(
                            request_data.get("solve_action")
                        ),
                        "guidance_details": cls._normalize_optional_text(
                            request_data.get("guidance_details")
                        ),
                        "anything_else": cls._normalize_optional_text(
                            request_data.get("anything_else")
                        ),
                    }
                )
                mentorship_request.insert(ignore_permissions=True)
                frappe.db.commit()

                doc_name = mentorship_request.name

                return_data = {
                    "id": mentorship_request.name,
                    "mentee": mentorship_request.mentee,
                    "phone": mentorship_request.phone,
                }
                result = Result.success(message="Mentorship request created successfully", data=return_data)
                return result
        except Exception as exc:
            frappe.log_error(
                f"Error in create_mentorship_request: {str(exc)}\n{frappe.get_traceback()}",
                "Mentorship Request API Error",
            )
            result = Result.failure(
                message="Failed to create mentorship request", 
                error_data={
                    "error": str(exc),
                    "traceback": frappe.get_traceback(),
                })
            return result
        finally:
            log_integration_request(
                request_data=request_data,
                response_data=result.to_dict(),
                service_name=service_name,
                request_description=request_description,
                error_data=result.error_data,
                reference_doctype="Mentorship Request" if doc_name else None,
                reference_docname=doc_name,
                error_title=error_title,
            )
   
    @staticmethod
    def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
        if isinstance(value, str) and value.startswith("@"):
            return "Not Provided"
        return value
