// Copyright (c) 2026, ReapBenefit and contributors
// For license information, please see license.txt

// On Postgres, JSON columns reach the form already parsed (list / dict), but the
// JSON editor only accepts text and fails to render, so the record will not open.
const ACTION_SUBMISSION_JSON_FIELDS = ["skills", "assessment"];

function stringify_action_submission_json_fields(doc) {
	ACTION_SUBMISSION_JSON_FIELDS.forEach((fieldname) => {
		const value = doc[fieldname];
		if (value && typeof value === "object") {
			doc[fieldname] = JSON.stringify(value, null, 2);
		}
	});
}

// "form-refresh" fires on every render, just before fields are drawn (incl. reloads after save)
$(document)
	.off("form-refresh.action_submission")
	.on("form-refresh.action_submission", (event, frm) => {
		if (frm.doctype === "Action Submission") {
			stringify_action_submission_json_fields(frm.doc);
		}
	});
