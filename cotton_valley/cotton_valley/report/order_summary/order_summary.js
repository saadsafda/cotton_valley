// Copyright (c) 2025, Saad and contributors
// For license information, please see license.txt

frappe.query_reports["Order Summary"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": ""
        },
        {
            "fieldname": "customer",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer"
        },
        {
            "fieldname": "sales_order",
            "label": __("Sales Order"),
            "fieldtype": "Link",
            "options": "Sales Order"
        }
    ],

	"onload": function(report) {
        // Add a button to the top-right menu
        report.page.add_inner_button(__("Send Report"), function() {
            // Logic goes here. For now, it just shows a message.
            frappe.msgprint("You clicked the custom button!");
        });
    }
};