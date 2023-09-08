import frappe
from frappe import _
from frappe.utils import scrub_urls
from PyPDF2 import PdfReader, PdfWriter
from distutils.version import LooseVersion
from frappe.utils.pdf import get_wkhtmltopdf_version, get_file_data_from_writer, cleanup, PDF_CONTENT_ERRORS
import pdfkit
from PyPDF2 import PdfReader, PdfWriter
import io
from frappe.utils.file_manager import save_file_on_filesystem

@frappe.whitelist(allow_guest=True)
def get_certificate(user, project):
	frappe.flags.ignore_permissions = True
	user = frappe.db.exists("User", f"{user}@solveninja.org")
	if not user:
		frappe.throw(_("User not found."))
	project = frappe.db.exists("Project", project)
	if not project:
		frappe.throw(_("Project not found."))
	
	certificate = frappe.db.exists("Certificate", {"user": user, "project": project})
	if certificate:
		certificate = frappe.get_doc("Certificate", certificate)
	else:
		certificate = frappe.get_doc(
			{
				"doctype": "Certificate",
				"user": user,
				"project": project
			}
		).insert(ignore_permissions=1)
	
	template = "solve_ninja/solve_ninja/api/jal.html"
	t = """
		<style>
			.certificate_wrapper{
			background: url(https://solveninja.org/files/certificate.jpg) no-repeat;
			background-size: cover;
			width: 100%;
			height: 100%;
			position: relative;
		}
		.certificate_name{
			position: absolute;
			left: 55%;
			transform: translateX(-50%);
			font-size: 30px;
			font-weight: 600;
			color: #0600be;
			top: 40%;
			font-family: Georgia;
		}
		</style>

		<div class="certificate_wrapper">
			<div class="certificate_name">{{fullname}}</div>
		</div>
	"""

	html = frappe.render_template(
		t, {"fullname": certificate.full_name}
	)

	options_={
		'margin-top': '0mm',
		'margin-right': '0mm',
		'margin-bottom': '0mm',
		'margin-left': '0mm',
		'page-size': 'A4',
		# "page-height": "220.9mm",
		# "page-width": "309.6mm",
		"orientation": "Landscape"
	}

	frappe.flags.ignore_permissions = False
	file_name="JalUtsav/"+user+"Certificate.pdf"
	is_private=False
	content = get_pdf(html, options=options_)
	file_path = save_file_on_filesystem(file_name,
              content,
              is_private)
	file_path["file_url"]="https://solveninja.org"+file_path["file_url"]
	frappe.response.message = file_path

def get_pdf(html, options=None, output: PdfWriter | None = None):
	html = scrub_urls(html)
	# html, options = prepare_options(html, options)

	options.update({"disable-javascript": "", "disable-local-file-access": ""})

	filedata = ""
	if LooseVersion(get_wkhtmltopdf_version()) > LooseVersion("0.12.3"):
		options.update({"disable-smart-shrinking": ""})

	try:
		# Set filename property to false, so no file is actually created
		filedata = pdfkit.from_string(html, options=options or {}, verbose=True)

		# create in-memory binary streams from filedata and create a PdfReader object
		reader = PdfReader(io.BytesIO(filedata))
	except OSError as e:
		if any([error in str(e) for error in PDF_CONTENT_ERRORS]):
			if not filedata:
				print(html, options)
				frappe.throw(_("PDF generation failed because of broken image links"))

			# allow pdfs with missing images if file got created
			if output:
				output.append_pages_from_reader(reader)
		else:
			raise
	finally:
		cleanup(options)

	if "password" in options:
		password = options["password"]

	if output:
		output.append_pages_from_reader(reader)
		return output

	writer = PdfWriter()
	writer.append_pages_from_reader(reader)

	if "password" in options:
		writer.encrypt(password)

	filedata = get_file_data_from_writer(writer)

	return filedata