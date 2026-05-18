// Copyright (c) 2026, Saad and contributors
// For license information, please see license.txt

frappe.query_reports["SR target report"] = {
	"filters": [
		{
			"fieldname": "period_type",
			"label": "Period Type",
			"fieldtype": "Select",
			"options": "Weekly\nMonthly\nQuarterly\nYearly",
			"default": "Monthly"
		},
		{
			"fieldname": "sales_person",
			"label": "Sales Person",
			"fieldtype": "Link",
			"options": "Sales Person"
		},
		{
			"fieldname": "product_category",
			"label": "Product Category",
			"fieldtype": "Link",
			"options": "Product Category"
		},
		{
			"fieldname": "product_subcategory",
			"label": "Product Subcategory",
			"fieldtype": "Link",
			"options": "Product Subcategory"
		},
		
	]
};
