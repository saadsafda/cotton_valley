// Copyright (c) 2025, Saad and contributors
// For license information, please see license.txt

frappe.query_reports["Shipped vs Pending Report"] = {
	"filters": [
		{
			"fieldname": "sales_person",
			"label": __("Sales Person"),
			"fieldtype": "Link",
			"options": "Sales Person",
			"reqd": 0
		},
		{
			"fieldname": "year_filter",
			"label": __("Fiscal Year"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
			"default": frappe.defaults.get_user_default("fiscal_year") || frappe.sys_defaults.fiscal_year,
			"reqd": 1,
			"wildcard_filter": 0
		},
		{
			"fieldname": "month_filter",
			"label": __("Month"),
			"fieldtype": "Select",
			"options": [
				"", // Empty option allows selecting "All Months" if your logic supports it
				"January", "February", "March", "April", "May", "June",
				"July", "August", "September", "October", "November", "December"
			].join("\n"),
			"default": "",
			"reqd": 0
		}
	]
};
