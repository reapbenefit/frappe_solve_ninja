import frappe
import asyncio
import threading
from frappe.utils import logger
import httpx

logger.set_log_level("DEBUG")
logger = frappe.logger("api", allow_site=True, file_count=50)


@frappe.whitelist(allow_guest=True)
def transcribe_audio(audio_url,contact_id,flow_id):    
    logger.info(f"transcribe_audio called with audio_url: {audio_url}, contact_id: {contact_id}, flow_id: {flow_id}")
    frappe.enqueue(
        "solve_ninja.api.audio_transcribe.upload_and_create_sarvam_job",
        audio_url=audio_url,
        callback_function = "solve_ninja.api.conversational_record_action.send_audio_output",
        callback_kwargs={"contact_id": contact_id, "flow_id": flow_id}
    )
    
    return {
        "status": "success",
        "message": "Audio submitted successfully",
    }


def send_audio_output(text, contact_id,flow_id):
    logger.info(f"send_audio_output called with text: {text}, contact_id: {contact_id}, flow_id: {flow_id}")
    glific_settings = frappe.get_doc("Glific Settings")
    glific_settings.resume_glific_flow(
        flow_id=flow_id,
        contact_id=contact_id,
        result=text       ,
        
    )


@frappe.whitelist(allow_guest=True)
def initialize_chat(user_mobile_no,user_msg,contact_id,flow_id):    
    logger.info(f"initialize_chat called with user_mobile_no: {user_mobile_no}, user_msg: {user_msg}, contact_id: {contact_id}, flow_id: {flow_id}")
    
    user_email = str(user_mobile_no)+'@solveninja.org'
    
    url = "https://cmp-api.solveninja.org/actions"
    payload = {
        "user_email": user_email,
        "user_message": user_msg
    }
    logger.info(f"payload: {payload}")
    run_async_post_call_with_callback(payload, url,paramters={"contact_id": contact_id, "flow_id": flow_id})
    
    return {
        "status": "success",
        "message": "Chat initialized successfully",
    }

@frappe.whitelist(allow_guest=True)
def continue_chat(action_uuid,last_user_message,contact_id,flow_id):
    url = "https://cmp-api.solveninja.org/ai/basic_action_chat"
    payload = {
        "action_uuid": action_uuid,
        "last_user_message": last_user_message
    }

    run_async_post_call_with_callback(payload, url,paramters={"contact_id": contact_id, "flow_id": flow_id})
    
    return {
        "status": "success",
        "message": "Chat initialized successfully"
    }
    
@frappe.whitelist(allow_guest=True)
def extract_action_metadata(action_uuid,contact_id,flow_id):
    url = "https://cmp-api.solveninja.org/ai/extract_action_metadata?action_uuid="+action_uuid

    run_async_get_call_with_callback(url,paramters={"contact_id": contact_id,"flow_id": flow_id})
    
    return {
        "status": "success",
        "message": "Action metadata extraction initiated successfully"
    }


def run_async_post_call_with_callback(payload, url, paramters):
    frappe.enqueue(
        "solve_ninja.api.conversational_record_action.async_post_job",
        payload=payload,
        url=url,
        paramters=paramters
    )

def run_async_get_call_with_callback(url, paramters=None):
    frappe.enqueue(
        "solve_ninja.api.conversational_record_action.async_get_job",
        url=url,
        paramters=paramters
    )

def async_post_job(payload, url, paramters=None):

    headers = {"Content-Type": "application/json"}

    with httpx.Client(timeout=20.0) as client:
        response = client.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            result = response.json()
        else:
            result = {"error": response.text}

    resume_flow(result, **(paramters or {}))

def async_get_job(url, paramters=None):

    headers = {"Content-Type": "application/json"}
    curl = build_curl(url, {}, headers)
    logger.info(f"Executing cURL command: {curl}")
    with httpx.Client(timeout=20.0) as client:
        response = client.post(url, headers=headers)
        if response.status_code == 200:
            result = response.json()
        else:
            result = {"error": response.text}

    resume_flow(result, **(paramters or {}))

def resume_flow(response, **kwargs):
    if "error" in response:
        logger.error(f"API call failed: {response['error']}")
        return
    
    glific_settings = frappe.get_doc("Glific Settings")
    glific_settings.resume_glific_flow(flow_id=kwargs.get("flow_id"),contact_id=kwargs.get("contact_id"),result=response)


def build_curl(url, payload, headers):
    header_str = " ".join([f"-H '{k}: {v}'" for k, v in headers.items()])
    data_str = f"-d '{frappe.as_json(payload)}'"
    return f"curl -X POST {header_str} {data_str} '{url}'"
