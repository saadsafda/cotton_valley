// Copyright (c) 2026, Saad and contributors
// For license information, please see license.txt

frappe.query_reports["New customer Yearly chart"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company"
		}
	]
};
