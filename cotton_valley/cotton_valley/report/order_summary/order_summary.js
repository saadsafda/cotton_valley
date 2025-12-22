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
        report.page.add_inner_button(__("Send Report"), function() {
            // 1. Get current filters
            let filters = report.get_values();

            // 2. Ask user for email address
            frappe.prompt([
                {
                    label: 'Email Address',
                    fieldname: 'email',
                    fieldtype: 'Data',
                    reqd: 1,
                    default: frappe.session.user_email
                }
            ], (values) => {
                // 3. Call Server API
                frappe.call({
                    method: "cotton_valley.cotton_valley.report.order_summary.order_summary.send_report_email",
                    args: {
                        filters: filters,
                        recipient_email: values.email
                    },
                    freeze: true,
                    freeze_message: "Sending Email...",
                    callback: function(r) {
                        if (!r.exc) {
                            frappe.msgprint("Email sent successfully!");
                        }
                    }
                });
            });
        });
    }
};;