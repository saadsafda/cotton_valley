# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    # 1. Define Columns
    columns = [
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
        {"label": "State", "fieldname": "state", "fieldtype": "Data", "width": 150},
        {"label": "Total Orders", "fieldname": "total_orders", "fieldtype": "Int", "width": 120},
        {"label": "Total Revenue", "fieldname": "total_revenue", "fieldtype": "Currency", "width": 150}
    ]

    # 2. Handle the Filter Logic
    # We create a 'conditions' string. If the user selects a company, we add the SQL check.
    # If they don't, 'conditions' remains empty, so it fetches ALL data.
    conditions = ""
    if filters.get("company"):
        conditions += " AND so.company = %(company)s"

    # 3. The SQL Query
    # Note: We use {conditions} f-string to inject the filter dynamically
    query = f"""
        SELECT
            so.company,
            addr.state,
            COUNT(so.name) as total_orders,
            SUM(so.grand_total) as total_revenue
        FROM
            `tabSales Order` so
        LEFT JOIN
            `tabAddress` addr ON so.customer_address = addr.name
        WHERE
            so.docstatus = 1
            {conditions}
        GROUP BY
            so.company,
            addr.state
        ORDER BY
            total_revenue DESC
        LIMIT 5
    """

    # 4. Fetch Data
    data = frappe.db.sql(query, filters, as_dict=True)

    return columns, data