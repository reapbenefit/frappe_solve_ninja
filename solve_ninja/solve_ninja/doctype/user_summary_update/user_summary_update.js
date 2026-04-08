// Copyright (c) 2026, ReapBenefit and contributors
// For license information, please see license.txt

frappe.ui.form.on("User Summary Update", {
	refresh(frm) {
		frm.disable_save();

		const status = frm.doc.status;

		if (status === "Draft" || status === "Failed") {
			frm.page.set_primary_action(__("Start Import"), () => {
				frappe.confirm(
					__("This will generate AI summaries for all users in the uploaded file. Continue?"),
					() => {
						frappe.dom.freeze(__("Queuing import..."));
						frm.call("start_import")
							.then(() => {
								frappe.dom.unfreeze();
								frm.reload_doc();
							})
							.catch(() => {
								frappe.dom.unfreeze();
							});
					}
				);
			});
		} else {
			frm.page.clear_primary_action();
		}

		if (status === "Queued" || status === "In Progress") {
			frm.set_intro(
				__("Import is running in the background. This page will refresh automatically."),
				"blue"
			);
			setTimeout(() => frm.reload_doc(), 5000);
		}

		if (status === "Completed") {
			frm.set_intro(
				__("Import completed. See the Results section for details."),
				"green"
			);
		}

		if (status === "Failed") {
			frm.set_intro(
				__("Import failed. Check the Log for details, then click Start Import to retry."),
				"red"
			);
		}

		// Render stored HTML table into the read-only log field wrapper
		if (frm.doc.log) {
			frm.fields_dict["log"].$wrapper
				.find(".control-value")
				.html(frm.doc.log);
		}
	},
});
