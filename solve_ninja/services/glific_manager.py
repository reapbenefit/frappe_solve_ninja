import frappe
from typing import Any, Dict
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