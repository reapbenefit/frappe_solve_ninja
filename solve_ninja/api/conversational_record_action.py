import frappe
import asyncio
import threading
from frappe.utils import logger
import httpx

logger.set_log_level("DEBUG")
logger = frappe.logger("api", allow_site=True, file_count=50)

@frappe.whitelist(allow_guest=True)
def resume_glific_flow(flow_id,contact_id,data):
    glific_settings = frappe.get_doc("Glific Settings")
    return glific_settings.resume_glific_flow(flow_id,contact_id,data)


@frappe.whitelist(allow_guest=True)
def initialize_chat(user_mobile_no,user_msg,contact_id):    
    flow_id = 'df308548-3d8c-436b-8314-bb85b79203d9'
    user_email = str(user_mobile_no)+'@solveninja.org'
    
    url = "https://cmp-api.solveninja.org/actions"
    payload = {
        "user_email": user_email,
        "user_message": user_msg
    }

    run_async_call_with_callback(payload, url, my_callback,paramters={"contact_id": contact_id, "flow_id": flow_id})
    
    return {
        "status": "success",
        "message": "Chat initialized successfully",
    }

@frappe.whitelist(allow_guest=True)
def continue_chat(action_uuid,last_user_message,contact_id):
    flow_id='df308548-3d8c-436b-8314-bb85b79203d9'
    url = "https://cmp-api.solveninja.org/ai/basic_action_chat"
    payload = {
        "action_uuid": action_uuid,
        "last_user_message": last_user_message
    }

    run_async_call_with_callback(payload, url, my_callback,paramters={"contact_id": contact_id, "flow_id": flow_id})
    
    return {
        "status": "success",
        "message": "Chat initialized successfully"
    }
    
def run_async_call_with_callback(payload, url, callback_function, paramters=None):
    frappe.enqueue(
        "solve_ninja.api.conversational_record_action.async_post_job",
        payload=payload,
        url=url,
        callback_function_name=callback_function,
        paramters=paramters
    )

def async_post_job(payload, url, callback_function_name, paramters=None):

    headers = {"Content-Type": "application/json"}
    with httpx.Client(timeout=20.0) as client:
        response = client.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            result = response.json()
        else:
            result = {"error": response.text}
    # Dynamically get the callback function
    my_callback(result, **(paramters or {}))

def my_callback(response, **kwargs):
    if "error" in response:
        logger.error(f"API call failed: {response['error']}")
        return
    resume_glific_flow(flow_id=kwargs.get("flow_id"),contact_id=kwargs.get("contact_id"),data=response)
