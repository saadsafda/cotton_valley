# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    # Ensure filters is not None
    filters = filters or {}
    
    # 1. Define Columns
    columns = [
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
        {"label": "City", "fieldname": "city", "fieldtype": "Data", "width": 150},
        {"label": "Total Orders", "fieldname": "total_orders", "fieldtype": "Int", "width": 120},
        {"label": "Total Order Value", "fieldname": "total_order_value", "fieldtype": "Currency", "width": 150}
    ]

    # 2. Dynamic Filtering & Grouping Logic
    conditions = ""
    select_company = "'' as company"  # Default: Agar filter nahi hai to Company column khali rakho taake rows merge ho sakein
    group_by_company = ""           # Default: Company se group nahi karenge

    # Agar Company filter user ne select kiya hai
    if filters.get("company"):
        conditions += " AND SO.company = %(company)s"
        select_company = "SO.company as company" # Company ka naam dikhao
        group_by_company = ", SO.company"        # Grouping mein company shamil karo

    # 3. SQL Query
    query = f"""
        SELECT
            {select_company},
            A.city AS city,
            COUNT(DISTINCT SO.name) AS total_orders,
            SUM(SOI.base_rate * SOI.qty) AS total_order_value
        FROM
            `tabSales Order` SO
        JOIN
            `tabSales Order Item` SOI ON SOI.parent = SO.name
        JOIN
            `tabAddress` A ON A.name = SO.shipping_address_name
        WHERE
            1=1 {conditions}
        GROUP BY
            A.city {group_by_company}
        ORDER BY
            total_orders DESC, total_order_value DESC
        LIMIT 5
    """

    # 4. Fetch Data
    data = frappe.db.sql(query, filters, as_dict=True)

    return columns, data