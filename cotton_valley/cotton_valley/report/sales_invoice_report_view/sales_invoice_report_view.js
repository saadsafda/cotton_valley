frappe.query_reports["Sales Invoice report View"] = {
    "filters": [
        {
            "fieldname": "si_number",
            "label": __("SI Number"),
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "reqd": 0
        },
        {
            "fieldname": "so_number",
            "label": __("SO Number"),
            "fieldtype": "Link",
            "options": "Sales Order",
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
            "fieldtype": "Link",  
        }
    ]
};