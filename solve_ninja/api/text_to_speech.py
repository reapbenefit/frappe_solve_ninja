import frappe
import json
import base64
import requests
from frappe.utils.file_manager import save_file_on_filesystem
from frappe.utils import logger
logger.set_log_level("DEBUG")
logger = frappe.logger("api", allow_site=True, file_count=50)

API_KEY = "HeMflsqk-2yJu3Q5mDn9-C_LIasjTXF72n5qpae1GOQu-8Oe0i_Loc4wl3iJSBt-"
INFERENCE_URL = "https://api.dhruva.ai4bharat.org/services/inference"

@frappe.whitelist(allow_guest=True, methods=['POST'])
def text_to_speech():
    logger.info('STARTS - text_to_speech transcribe_audio  ------------')
    try:
        data = json.loads(frappe.request.data)
        service_id = data.get('service_id')
        src_lang_code = data.get('src_lang_code')
        input_text = data.get('input_text')

        if not (service_id and src_lang_code and input_text):
            logger.info('missing parameters')
            frappe.response.http_status_code = 400
            return {'error': 'Missing required parameters'}


        inference_cfg = {
            "language": {"sourceLanguage": src_lang_code},
            "gender": "female"
        }

        inference_inputs = [{"source": input_text}]

        headers = {"authorization": API_KEY}

        response = requests.post(
            f"{INFERENCE_URL}/tts?serviceId={service_id}",
            headers=headers,
            json={"config": inference_cfg, "input": inference_inputs}
        )

        if response.status_code != 200:
            frappe.response.http_status_code = 500
            return {'error': 'Request failed'}
            
        

        audio_content = response.json()["audio"][0]["audioContent"]
        
        audio_bytes = base64.b64decode(audio_content)
        
        audio_filename = "output_audio.wav"
        with open(audio_filename, "wb") as f:
            f.write(audio_bytes)
        
        
        # Use Frappe's file manager to serve the file
        saved_file = save_file_on_filesystem(audio_filename, "output_audio.wav", "File", is_private=0)
        file_url = saved_file.get('file_url')

        frappe.response.file_url = f"{frappe.utils.get_url()}{file_url}"
        #frappe.response.filename = "output_audio.wav"
        #frappe.response.filecontent = audio_bytes
        #frappe.response.type = "download"
        logger.info('ENDS - text_to_speech transcribe_audio  ------------')
    except Exception as e:
        logger.error(e, exc_info=True)
        frappe.response.http_status_code = 500
        logger.info('ENDS - text_to_speech transcribe_audio  ------------')
        return {'error': str(e)}