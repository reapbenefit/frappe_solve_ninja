import frappe
from sarvamai import SarvamAI
from typing import Dict, Any
from solve_ninja.models.result import Result
class SpeechManager:
    SARVAM_API_KEY = frappe.conf.get("sarvam_api_key")
    @classmethod
    def voice_to_text(cls, audio_url: str)->Result:
        if not audio_url:
            return Result.bad_request(message="Audio URL is required")
        try:
            client = SarvamAI(
            api_subscription_key=cls.SARVAM_API_KEY,
            )
            # Convert URL → actual file path
            file_path = frappe.get_site_path(audio_url.lstrip("/"))
            # Transcribe mode (default)
            with open(file_path, "rb") as f:
                response = client.speech_to_text.transcribe(
                    file=f,
                    model="saaras:v3"
                )

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Speech to Text Error")
            return Result.failure(message=str(e), error_data=frappe.get_traceback())
        return Result.success(message="Speech to Text successful", data={"transcript": response.transcript, "language_code": response.language_code})   