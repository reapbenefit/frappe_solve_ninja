import asyncio
import frappe
from samaaja.api.common import custom_response
from solve_ninja.services.chat_manager import ChatManager
from solve_ninja.utils import parse_request_data

@frappe.whitelist(allow_guest=True)
def initiate_chat():
    """First message of a chat. Returns response + session_id."""
    try:
        request_data = parse_request_data()
        
        return asyncio.run(ChatManager.initiate_chat(request_data))
    
    except Exception as e:
        frappe.log_error(f"Error in initiate_chat: {str(e)}")
        return custom_response(
            message="Failed to initiate chat",
            data={"error": str(e)},
            status_code=500,
            error=True,
        )

@frappe.whitelist(allow_guest=True)
def continue_chat():
    """Follow-up message. Requires user_message + session_id."""
    try:
        request_data = parse_request_data()
        
        return asyncio.run(ChatManager.continue_chat(request_data))
        
    except Exception as e:
        frappe.log_error(f"Error in continue_chat: {str(e)}")
        return custom_response(
            message="Failed to continue chat",
            data={"error": str(e)},
            status_code=500,
            error=True,
        )

@frappe.whitelist(allow_guest=True)
def end_chat(): # TODO: Implement this
    pass
