import frappe
import json
import requests
import base64
from frappe.utils import logger
logger.set_log_level("DEBUG")
logger = frappe.logger("api", allow_site=True, file_count=50)

@frappe.whitelist(methods=['POST'])
def transcribe_audio():
	logger.info('STARTS - voice-to-text transcribe_audio  ------------')
	req_data = json.loads(frappe.request.data)
	service_id = req_data.get('service_id')
	src_lang_code = req_data.get('src_lang_code')
	audio_url = req_data.get('audio_url')

	if not (service_id and src_lang_code and audio_url):
		logger.info('missing paramters')
		frappe.response.http_status_code = 400
		return {'error': 'Missing required parameters'}

	audio_response = requests.get(audio_url)
	if audio_response.status_code != 200:
		frappe.response.http_status_code = 500
		return {'error': 'Failed to retrieve audio content from the URL'}
	
	audio_binary = audio_response.content
	audio_content = base64.b64encode(audio_binary).decode("utf-8")

	headers = {"Authorization": 'yuwfR4u9k-5TLC2-DkujtivhGj6Z7dthnAs3LUY_QUTW3Abw7MC0hvsUt7t2YhpF'}

	pipeline_task = [
		{
			"taskType": "asr",
			"config": {
				"language": {
					"sourceLanguage":  src_lang_code
				},
				"serviceId": service_id,
				"audioFormat": "wav",
				"samplingRate": 16000
			}
		}
	]

	input_data = {
		"audio" : [
			{
				"audioContent": audio_content
			}
		]
	}

	response = requests.post(
		"https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
		headers = headers,
		json = {"pipelineTasks": pipeline_task, "inputData": input_data}
	)

	if response.status_code != 200:
		frappe.response.http_status_code = 500
		return {'error': 'Request failed'}


	output_text = response.json()["pipelineResponse"][0]["output"][0]["source"]
	return {'transcript': output_text}


@frappe.whitelist(methods=['POST'])
def transcribe():
	logger.info('STARTS - voice-to-text transcribe_audio  ------------')
	req_data = json.loads(frappe.request.data)
	service_id = req_data.get('service_id')
	src_lang_code = req_data.get('src_lang_code')
	audio_url = req_data.get('audio_url')

	if not (service_id and src_lang_code and audio_url):
		logger.info('missing paramters')
		frappe.response.http_status_code = 400
		return {'error': 'Missing required parameters'}

	audio_response = requests.get(audio_url)
	if audio_response.status_code != 200:
		frappe.response.http_status_code = 500
		return {'error': 'Failed to retrieve audio content from the URL'}

	audio_binary = audio_response.content
	audio_content = base64.b64encode(audio_binary).decode("utf-8")

	headers = {"Authorization": 'yuwfR4u9k-5TLC2-DkujtivhGj6Z7dthnAs3LUY_QUTW3Abw7MC0hvsUt7t2YhpF'}

	pipeline_task = [
		{
			"taskType": "asr",
			"config": {
				"language": {
					"sourceLanguage":  src_lang_code
				},
				"serviceId": service_id,
				"audioFormat": "wav",
				"samplingRate": 16000
			}
		},
		{
			"taskType": "translation",
			"config": {
				"language": {
					"sourceLanguage": src_lang_code,
					"targetLanguage": "en"
				},
				"serviceId": "ai4bharat/indictrans-v2-all-gpu--t4"
			}
		}
	]

	input_data = {
		"audio" : [
			{
				"audioContent": audio_content
			}
		]
	}

	response = requests.post(
		"https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
		headers = headers,
		json = {"pipelineTasks": pipeline_task, "inputData": input_data}
	)

	if response.status_code != 200:
		frappe.response.http_status_code = 500
		return {'error': 'Request failed'}

	output_text = response.json()["pipelineResponse"][1]["output"][0]["source"]
	output_text_eng = response.json()["pipelineResponse"][1]["output"][0]["target"]
	return {'transcript': output_text,
			'English' : output_text_eng}

@frappe.whitelist(methods=['POST'])
def translation():
	logger.info('STARTS - voice-to-text transcribe_audio  ------------')
	req_data = json.loads(frappe.request.data)
	src_lang_code = req_data.get('src_lang_code')
	input_text = req_data.get('input_text')

	if not (src_lang_code and input_text):
		logger.info('missing paramters')
		frappe.response.http_status_code = 400
		return {'error': 'Missing required parameters'}
	
	headers = {"Authorization": 'yuwfR4u9k-5TLC2-DkujtivhGj6Z7dthnAs3LUY_QUTW3Abw7MC0hvsUt7t2YhpF'}

	pipeline_task = [
		{
			"taskType": "translation",
			"config": {
				"language": {
					"sourceLanguage": src_lang_code,
					"targetLanguage": "en"
				},
				"serviceId": "ai4bharat/indictrans-v2-all-gpu--t4"
			}
		}
	]

	input_data = {
		"input": [
			{
				"source": input_text
			}
		]
	}

	response = requests.post(
		"https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
		headers = headers,
		json = {"pipelineTasks": pipeline_task, "inputData": input_data}
	)

	if response.status_code != 200:
		frappe.response.http_status_code = 500
		return {'error': 'Request failed'}

	output_text = response.json()["pipelineResponse"][0]["output"][0]["target"]
	return {'transcript': output_text}