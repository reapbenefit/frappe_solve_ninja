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


@frappe.whitelist(allow_guest=True)
def add_chat_message():
    try:
        request_data = parse_request_data()
        return ChatManager.add_chat_message(request_data).to_custom_response()
    except Exception as e:
        frappe.log_error(f"Error in add_chat_message: {str(e)}")
        return custom_response(
            message="Failed to add chat message",
            data={"error": str(e)},
            status_code=500,
            error=True,
        )

@frappe.whitelist(allow_guest=True)
def submit_feedback_for_session():
    try:
        request_data = parse_request_data()
        return ChatManager.submit_feedback_for_session(request_data).to_custom_response()
    except Exception as e:
        frappe.log_error(f"Error in submit_feedback_for_session: {str(e)}")
        return custom_response(
            message="Failed to submit feedback for session",
            data={"error": str(e)},
            status_code=500,
            error=True,
        )

@frappe.whitelist(allow_guest=True)
def get_chat_history():
    try:
        request_data = parse_request_data()
        return ChatManager.get_chat_history_by_session_id(request_data.get("session_id")).to_custom_response()
    except Exception as e:
        frappe.log_error(f"Error in get_chat_history: {str(e)}")
        return custom_response(message="Failed to get chat history", data={"error": str(e)}, status_code=500, error=True)

@frappe.whitelist(allow_guest=True)
def submit_feedback_for_chat_message():
    try:
        request_data = parse_request_data()
        return ChatManager.submit_feedback_for_chat_message(request_data).to_custom_response()
    except Exception as e:
        frappe.log_error(f"Error in submit_feedback_for_chat_message: {str(e)}")
        return custom_response(
            message="Failed to submit feedback for chat message",
            data={"error": str(e)},
            status_code=500,
            error=True,
        )