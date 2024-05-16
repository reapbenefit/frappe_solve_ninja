// Copyright (c) 2024, ReapBenefit and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Events Analytics"] = {
	"filters": [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1)
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.get_today()
		},
		{
			fieldname: "user",
			label: __("User"),
			fieldtype: "Link",
			options: "User",
		},
		{
			fieldname: "have_location",
			label: __("Have Location?"),
			fieldtype: "Check",
		},

	]
};
