// Copyright (c) 2025, Saad and contributors
// For license information, please see license.txt

frappe.query_reports["Sales Person Customer Report"] = {
	"filters": [
		{
			"fieldname": "sales_person",
			"label": __("Sales Person"),
			"fieldtype": "Link",
			"options": "Sales Person",
			"width": 100
		},
		{
			"fieldname": "customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer",
			"width": 100
		},
		{
			"fieldname": "cv_price_level",
			"label": __("CV Price Level"),
			"fieldtype": "Link",
			"options": "Price List",
			"width": 100
		},
		{
			"fieldname": "udc_price_level",
			"label": __("UDC Price Level"),
			"fieldtype": "Link",
			"options": "Price List",
			"width": 100
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"width": 100
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"width": 100,
			"default": frappe.datetime.get_today()
		}
	]
};
