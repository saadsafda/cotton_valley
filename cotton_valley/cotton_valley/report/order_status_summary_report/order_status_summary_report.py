# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    # 1. Define Columns
    columns = [
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
        {"label": "Status", "fieldname": "order_status", "fieldtype": "Data", "width": 150},
        {"label": "Total Orders", "fieldname": "total_orders", "fieldtype": "Int", "width": 120},
        {"label": "Total Value", "fieldname": "total_value", "fieldtype": "Currency", "width": 150}
    ]

    # 2. Build Conditions
    # We start with an empty string because the base query already has a WHERE clause.
    conditions = ""
    
    # Check if user selected a company
    if filters.get("company"):
        conditions += " AND company = %(company)s"

    # 3. SQL Query
    # We add {conditions} dynamically.
    query = f"""
        SELECT
            order_status,
            company,
            COUNT(name) as total_orders,
            SUM(grand_total) as total_value
        FROM
            `tabSales Order`
        WHERE
            order_status IN ('Pending', 'Processing', 'Shipped')
            {conditions}
        GROUP BY
            order_status,
            company
        ORDER BY
            order_status ASC
    """

    # 4. Fetch Data
    data = frappe.db.sql(query, filters, as_dict=True)

    return columns, data