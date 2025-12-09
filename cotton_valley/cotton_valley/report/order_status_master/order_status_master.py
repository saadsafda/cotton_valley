# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    # 1. Define Columns
    columns = [
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 120}, # Added Company Column
        {"label": "Order ID", "fieldname": "name", "fieldtype": "Link", "options": "Sales Order", "width": 120},
        {"label": "Customer", "fieldname": "customer_name", "fieldtype": "Data", "width": 150},
        {"label": "Date", "fieldname": "transaction_date", "fieldtype": "Date", "width": 100},
        {"label": "Amount", "fieldname": "grand_total", "fieldtype": "Currency", "width": 120},
        {"label": "Status", "fieldname": "order_status", "fieldtype": "Data", "width": 100}
    ]

    # 2. Build Filter Conditions
    # We start with an empty string.
    conditions = ""

    # Check if the user has selected a company
    if filters.get("company"):
        conditions += " AND company = %(company)s"

    # 3. SQL Query
    query = f"""
        SELECT
            name,
            customer_name,
            transaction_date,
            company,
            grand_total,
            order_status
        FROM
            `tabSales Order`
        WHERE
            order_status IN ('Pending', 'Processing', 'Shipped')
            {conditions}
        ORDER BY
            transaction_date DESC
    """

    # 4. Fetch Data
    data = frappe.db.sql(query, filters, as_dict=True)

    return columns, data