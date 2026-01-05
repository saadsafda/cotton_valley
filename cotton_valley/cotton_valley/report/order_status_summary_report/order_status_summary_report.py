# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    filters = filters or {}

    # 1. Define Columns
    columns = [
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
        {"label": "Status", "fieldname": "order_status", "fieldtype": "Data", "width": 150},
        {"label": "Total Orders", "fieldname": "total_orders", "fieldtype": "Int", "width": 120},
        {"label": "Total Value", "fieldname": "total_value", "fieldtype": "Currency", "width": 150}
    ]

    # 2. Dynamic Filtering & Grouping Logic
    conditions = ""
    # Default: Agar filter nahi hai to Company column khali rakho aur Grouping mat karo
    select_company = "'' as company" 
    group_by_company = ""           

    # Check if user selected a company
    if filters.get("company"):
        conditions += " AND company = %(company)s"
        select_company = "company"         # Asli company ka naam uthao
        group_by_company = ", company"     # Company ke hisab se group karo

    # 3. SQL Query
    query = f"""
        SELECT
            order_status,
            {select_company},
            COUNT(name) as total_orders,
            SUM(grand_total) as total_value
        FROM
            `tabSales Order`
        WHERE
            order_status IN ('Pending', 'Processing', 'Shipped')
            {conditions}
        GROUP BY
            order_status {group_by_company}
        ORDER BY
            order_status ASC
    """

    # 4. Fetch Data
    data = frappe.db.sql(query, filters, as_dict=True)

    return columns, data