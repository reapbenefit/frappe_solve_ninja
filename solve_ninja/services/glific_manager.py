import frappe
from typing import Any, Dict, Optional
from solve_ninja.models.result import Result
from solve_ninja.utils import log_integration_request, safe_get, validate_and_normalize_mobile


class GlificManager:
    @staticmethod
    def get_contact_id_by_phone(phone) -> str:
        """
        Get contact id by phone number.
        """
        glific_settings = frappe.get_doc("Glific Settings")
        response = glific_settings.get_contact_by_phone(phone)
        if safe_get(response, "data", "contactByPhone", "contact") is None:
            return None
        return safe_get(response, "data", "contactByPhone", "contact", "id")

    @classmethod
    def create_contact(cls, request_data: Dict[str, Any]) -> Result:  
        """
        Create a new contact in Glific and returns contact id
        """
        service_name = "Create Contact in Glific"
        request_description = "Create new contact in Glific"
        error_title = "Create Contact in Glific"
        result = Result.failure(
            message="Failed to create contact",
            data=None)
        try:
            phone = request_data.get("mobile_no")
            name = request_data.get("name")
            required_fields = ["mobile_no","name"]
            missing_fields = [
                field for field in required_fields if not request_data.get(field)
            ]
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            
            phone = validate_and_normalize_mobile(phone)
            # Check if contact already exists
            contact_id = GlificManager.get_contact_id_by_phone(phone)
            if contact_id:
                result = Result.success(
                    message="Contact already exists",
                    data=contact_id,
                )
                return result
            
            glific_settings = frappe.get_doc("Glific Settings") 
            response = glific_settings.create_contact(phone, name)
            if safe_get(response, "data", "createContact", "contact") is not None:
                contact_id = safe_get(response, "data", "createContact", "contact", "id")
                
                response = glific_settings.optin_contact(phone, name)
                if safe_get(response, "data", "optinContact", "contact") is not None:
                    result = Result.success(
                        message="Contact created and opted in successfully",
                        data=contact_id,
                    )
                    return result
                else:
                    result = Result.failure(
                        message="Contact created but failed to optin contact after creation",
                        data=contact_id,
                    )
                    return result
            else:
                error_message = safe_get(response, "data", "createContact", "errors", "message")
                result = Result.failure(
                    message=error_message or "Failed to create contact",
                    data=None,
                )
                return result
        except Exception as e:
            frappe.log_error(
                title="Error in create_contact",
                message=str(e),
            )
            result = Result.failure(
                message=f"Failed to create contact: {str(e)}",
                data=None,
            )
            return result
        finally:
            # This will log the request and response data to the Integration Request doctype. 
            # This will always run, even if there was a return statement.
            log_integration_request(
                request_data=request_data,
                response_data=result.to_dict(),
                service_name=service_name,
                request_description=request_description,
                error_data=result.error_data if result.error_data else None,
                reference_doctype=None,
                reference_docname=None,
                error_title=error_title,
            )

    @classmethod
    def ensure_contact_for_user(
        cls,
        mobile_no: str,
        name: str,
        user: Optional[str] = None,
    ) -> Result:
        """
        Ensure a Glific contact exists (create + opt-in if needed) and
        store wa_id on the Ninja Profile when a Frappe user is known.

        Used by signup (add_user) and OTP send (send_hsm_otp) so WhatsApp
        OTP works for newly registered users.
        """
        display_name = (name or "").strip() or "Solve Ninja"
        result = cls.create_contact({
            "mobile_no": mobile_no,
            "name": display_name,
        })
        contact_id = result.data
        if not contact_id:
            return result

        profile_user = user
        if not profile_user:
            try:
                normalized = validate_and_normalize_mobile(mobile_no)
                profile_user = frappe.db.get_value("User", {"mobile_no": normalized}, "name")
                if not profile_user and len(normalized) == 12:
                    profile_user = frappe.db.get_value(
                        "User", {"mobile_no": normalized[-10:]}, "name"
                    )
            except Exception:
                profile_user = None

        if profile_user and frappe.db.exists("Ninja Profile", profile_user):
            current_wa_id = frappe.db.get_value("Ninja Profile", profile_user, "wa_id")
            if str(current_wa_id or "") != str(contact_id):
                frappe.db.set_value(
                    "Ninja Profile",
                    profile_user,
                    "wa_id",
                    contact_id,
                    update_modified=False,
                )

        return Result.success(
            message=result.message or "Glific contact ready",
            data=contact_id,
        )