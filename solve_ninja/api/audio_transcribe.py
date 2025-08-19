import frappe
import whisper
from sarvamai import SarvamAI
from frappe.handler import upload_file
import os, io, json
from frappe.utils.file_manager import save_file
import mimetypes
import requests
from urllib.parse import urlparse
import asyncio
from sarvamai import AsyncSarvamAI


SARVAM_API_KEY = "sk_5namj6hd_Yd5PzB3LBpfo6ksd1ZJMxMtE"

@frappe.whitelist(allow_guest=True)
def transcribe_audio(file_url=None):
    if not file_url:
        return {"error": "No audio file URL provided"}

    file_path = frappe.get_site_path("public", file_url.replace("/files/", "files/"))

    if not os.path.exists(file_path):
        return {"error": "File not found"}

    try:
        model = whisper.load_model("medium")
        result = model.transcribe(file_path, task="translate")
        return {
            "text": result["text"],
            "language": result["language"]
        }
    except Exception as e:
        frappe.log_error()
        return {"error": str(e)}

@frappe.whitelist(allow_guest=True)
def transcribe_sarvam(file_url=None):
    if not file_url:
        return {"error": "Missing file URL"}

    # Local file path
    file_path = frappe.get_site_path("public", file_url.replace("/files/", "files/"))

    if not os.path.exists(file_path):
        return {"error": "File not found"}

    try:
        # Initialize client with your API key
        client = SarvamAI(api_subscription_key=SARVAM_API_KEY)

        # Transcribe using saarika (for Indian + English languages)
        with open(file_path, "rb") as f:
            response = client.speech_to_text.transcribe(
                file=f,
                model="saarika:v2.5",  # or saaras:v2.5 for translation
                language_code="unknown"  # auto-detect language
            )

        return {
            "transcript": response.transcript,
            "language_code": response.language_code
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Sarvam Transcription Error")
        return {"error": str(e)}

@frappe.whitelist(allow_guest=True)
def upload_and_transcribe_sarvam():
    file = upload_file()
    try:
        file_path = file.get_full_path()

        if not os.path.exists(file_path):
            return {"error": "File save failed"}

        # Sarvam API call
        client = SarvamAI(api_subscription_key=SARVAM_API_KEY)

        with open(file_path, "rb") as f:
            response = client.speech_to_text.transcribe(
                file=f,
                model="saarika:v2.5",
                language_code="unknown"
            )

        return {
            "file_url": file_path,
            "transcript": response.transcript,
            "language_code": response.language_code
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Upload + Transcribe Error")
        return {"error": str(e)}


@frappe.whitelist(allow_guest=True)
def upload_and_create_sarvam_job(audio_url, model=None, with_timestamps=1, with_diarization=0, num_speakers=None,callback_function=None, callback_kwargs=None):
# async def upload_and_create_sarvam_job(audio_url, model=None, with_timestamps=1, with_diarization=0, num_speakers=None):
    """
    Upload via upload_file() and create a Sarvam Batch STT job (saarika only).
    Returns job_id for polling.
    """

    # file_doc = upload_file()
    # file_url = file_doc.file_url
    # file_path = file_doc.get_full_path()

    # if not os.path.exists(file_path):
    #     return {"error": "File save failed"}
    
    client = SarvamAI(api_subscription_key=SARVAM_API_KEY)

    file_doc = save_audio_from_url(audio_url, is_private=1)
    file_url = file_doc.get_full_path()
    allowed = {"saarika:v1", "saarika:v2", "saarika:v2.5", "saarika:flash"}
    model = (model or "saarika:v2.5").strip()
    if model not in allowed:
        model = "saarika:v2.5"

    request_payload = {
        "model": model,
        "language_code": "en-IN",
        "with_timestamps": bool(int(with_timestamps)),
        "with_diarization": bool(int(with_diarization)),
        "num_speakers": int(num_speakers) if num_speakers else None,
    }

    job = client.speech_to_text_job.create_job(**request_payload)

    job.upload_files([file_url])
    job.start()
    final_status = job.wait_until_complete()

    job_id = getattr(job, "job_id", None) or getattr(job, "request_id", None)
    if not job_id:
        # Log for debugging once if SDK changes
        try:
            frappe.log_error(str(vars(job)), "Sarvam STT Job object missing job_id")
        except Exception:
            pass
        return {"error": "Could not read job_id from SDK object. Check server logs."}
    
    tj = frappe.get_doc({
        "doctype": "Transcript Job",
        "external_service": "Sarvam",
        "external_job_id": job_id,
        "status": "Queued",
        "request_json": json.dumps(request_payload, indent=2)
    }).insert(ignore_permissions=True)

    file_doc.attached_to_doctype = "Transcript Job"
    file_doc.attached_to_name = tj.name
    file_doc.save()
    if job.is_failed():
        tj.status = "Failed"
        tj.save()
        return

    private_dir = frappe.get_site_path("private", "files", f"sarvam_job_{job_id}")
    os.makedirs(private_dir, exist_ok=True)

    job.download_outputs(output_dir=str(private_dir))
    out = {}
    json_files = [f for f in os.listdir(private_dir) if f.lower().endswith(".json")]
    json_content = None

    if json_files:
        json_path = os.path.join(private_dir, json_files[0])
        try:
            with io.open(json_path, "r", encoding="utf-8", errors="ignore") as fh:
                json_content = json.load(fh)
        except Exception:
            with io.open(json_path, "r", encoding="utf-8", errors="ignore") as fh:
                json_content = fh.read()

    out["json_output"] = json_content
    out["saved_folder"] = private_dir
    out["saved_json_file"] = json_files[0] if json_files else None
    tj.respomse_json = json.dumps(out, indent=2)
    tj.save()


    if callback_function and callback_kwargs:
        # If callback function is provided, call it with the result
        callback_kwargs = json.loads(callback_kwargs) if isinstance(callback_kwargs, str) else callback_kwargs
        callback_kwargs["text"] = json_content.get("transcript", "")

        # Use enqueue to run the callback asynchronously
        frappe.enqueue(
            callback_function,
            **callback_kwargs
        )

@frappe.whitelist(allow_guest=True)
def get_sarvam_job_status(job_id: str):
    """Poll Sarvam batch job. When complete, returns transcript & artifacts list."""

    client = SarvamAI(api_subscription_key=SARVAM_API_KEY)

    job = client.speech_to_text_job.get_job(job_id)
    # Build a safe dict (only primitives)
    job_status = job.get_status()
    out = {
        "job_id": job_status.job_id,
        "status": job_status.job_state,
        "created_at": job_status.created_at,
        "updated_at": job_status.updated_at,
        "error_message": job_status.error_message,
    }

    if out["status"] != "Completed" or out["error_message"]:
        return out

    private_dir = frappe.get_site_path("private", "files", f"sarvam_job_{job_id}")
    os.makedirs(private_dir, exist_ok=True)

    job.download_outputs(output_dir=str(private_dir))

    json_files = [f for f in os.listdir(private_dir) if f.lower().endswith(".json")]
    json_content = None

    if json_files:
        json_path = os.path.join(private_dir, json_files[0])
        try:
            with io.open(json_path, "r", encoding="utf-8", errors="ignore") as fh:
                json_content = json.load(fh)
        except Exception:
            with io.open(json_path, "r", encoding="utf-8", errors="ignore") as fh:
                json_content = fh.read()

    out["json_output"] = json_content
    out["saved_folder"] = private_dir
    out["saved_json_file"] = json_files[0] if json_files else None

    transcribe_job = frappe.db.exists("Transcript Job", {"external_job_id": job_id})
    if transcribe_job:
        tj = frappe.get_doc("Transcript Job", transcribe_job)
        tj.status = job_status.job_state
        tj.response_json = json.dumps(out, indent=2)
        tj.save()
    
    return out

def save_audio_from_url(audio_url: str, attach_to_doctype: str=None, attach_to_name: str=None, is_private: int=1):
    """
    Downloads audio from a URL and saves it as a File doc in Frappe storage.
    Returns (file_doc, absolute_file_path).

    - attach_to_doctype/name are optional (to link the File to a document)
    - is_private: 1 => /private/files, 0 => /public/files
    """
    r = requests.get(audio_url, stream=True, timeout=60)
    r.raise_for_status()

    # 2) Determine filename & extension
    parsed = urlparse(audio_url)
    basename = os.path.basename(parsed.path) or "audio"
    # If no extension, infer from Content-Type
    if "." not in basename:
        ext = None
        ctype = r.headers.get("Content-Type")
        if ctype:
            ext = mimetypes.guess_extension(ctype.split(";")[0].strip())
        basename += (ext or ".wav")  # default to .wav if unknown

    # 3) Read content into memory (or write to temp if very large)
    content = r.content  # for large files consider iter_content() -> temp file

    # 4) Save via Frappe’s file manager (creates File doctype entry)
    file_doc = save_file(
        fname=basename,
        content=content,
        dt=attach_to_doctype,
        dn=attach_to_name,
        is_private=is_private,
        decode=False
    )

    return file_doc