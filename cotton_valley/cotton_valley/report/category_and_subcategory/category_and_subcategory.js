// Copyright (c) 2025, Saad and contributors
// For license information, please see license.txt

frappe.query_reports["Category and Subcategory"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": "",
			"reqd": 0
		},
		{
			"fieldname": "category",
			"label": __("Category"),
			"fieldtype": "Link",
			"options": "Product Category",
			"reqd": 0,
			
		},
		{
			"fieldname": "subcategory",
			"label": __("Subcategory"),
			"fieldtype": "Link",
			"options": "Product Subcategory",
			"reqd": 0
		}
	]
};
