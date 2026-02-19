import frappe
from frappe.utils.file_manager import save_file

@frappe.whitelist()
def upload_file():
    file = frappe.request.files.get("file")
    is_private = frappe.form_dict.get("is_private")

    if file is None or not file:
        frappe.throw("No file attached")

    filename = file.filename
    content = file.read()

    # YOUR CUSTOM VALIDATION
    allowed = ["jpg","jpeg","png","pdf","txt",
               "doc","docx","xls","xlsx","ppt","pptx",
               "ogg","webm","wav","mp3"]

    ext = filename.split(".")[-1].lower()

    if ext not in allowed:
        frappe.throw("File type not allowed")

    return save_file(filename, content, None, None, is_private=is_private)
