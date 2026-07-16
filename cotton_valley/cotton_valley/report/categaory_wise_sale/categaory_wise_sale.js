// Copyright (c) 2026, Saad and contributors
// For license information, please see license.txt

frappe.query_reports["Categaory wise sale"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": "Company",
			"fieldtype": "Link",
			"options": "Company",
			"reqd": 0
		}
	]
};
