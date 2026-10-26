// Copyright (c) 2026, ReapBenefit and contributors
// For license information, please see license.txt

frappe.listview_settings["Ninja Monthly Snapshot"] = {
	onload(listview) {
		if (!frappe.user.has_role("System Manager")) {
			return;
		}
		listview.page.add_inner_button(__("Run Monthly MIS"), () => show_run_monthly_mis_dialog(listview));
	},
};

function show_run_monthly_mis_dialog(listview) {
	const last_month = moment().subtract(1, "months").startOf("month").format("YYYY-MM-DD");
	const dialog = new frappe.ui.Dialog({
		title: __("Run Monthly MIS"),
		fields: [
			{
				fieldtype: "Date",
				fieldname: "month",
				label: __("Month"),
				description: __("Any date in the month. The current month gives a partial (month-to-date) snapshot."),
				default: last_month,
				reqd: 1,
			},
			{
				fieldtype: "Select",
				fieldname: "steps",
				label: __("What to run"),
				options: [
					{ value: "all", label: __("Full monthly job (status, level, snapshot) - last month only") },
					{ value: "snapshot", label: __("Rebuild snapshot only") },
				],
				default: "all",
				reqd: 1,
			},
		],
		primary_action_label: __("Run"),
		primary_action(values) {
			frappe.call({
				method: "solve_ninja.services.ninja_mis.trigger_monthly_mis",
				args: { month: values.month, steps: values.steps },
				freeze: true,
				callback(r) {
					if (r.message) {
						frappe.show_alert({ message: r.message, indicator: "green" }, 7);
					}
					dialog.hide();
					listview.refresh();
				},
			});
		},
	});
	dialog.show();
}
