frappe.query_reports["Sales Invoice report View"] = {
    "filters": [
        {
            "fieldname": "si_number",
            "label": __("SI Number"),
            "fieldtype": "Data",
            "reqd": 0
        },
        {
            "fieldname": "so_number",
            "label": __("SO Number"),
            "fieldtype": "Data",
            "reqd": 0
        },
        {
            "fieldname": "customer",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer",
            "reqd": 0
        },
        {
            "fieldname": "account_code",
            "label": __("Account Code"),
            "fieldtype": "Data",  // Changed to Data to allow searching text like 'Sher-NY'
            "reqd": 0
        }
    ]
};