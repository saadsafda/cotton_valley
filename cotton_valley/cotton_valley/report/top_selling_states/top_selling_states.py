# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    filters = filters or {}

    # 1. Define Columns
    # (Maine columns wese hi rakhe hain, bas logic badal raha hoon)
    columns = [
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
        {"label": "State", "fieldname": "state", "fieldtype": "Data", "width": 150},
        {"label": "Total Orders", "fieldname": "total_orders", "fieldtype": "Int", "width": 120},
        {"label": "Total Revenue", "fieldname": "total_revenue", "fieldtype": "Currency", "width": 150}
    ]

    # 2. Dynamic Filtering & Grouping Logic
    conditions = ""
    
    # Default: Agar filter nahi hai to Company column khali rakho aur Grouping mat karo
    select_company = "'' as company"
    group_by_company = ""

    # Check if user selected a company
    if filters.get("company"):
        conditions += " AND so.company = %(company)s"
        select_company = "so.company"       # Company ka naam dikhao
        group_by_company = ", so.company"   # Company ke hisab se alag karo

    # 3. SQL Query
    query = f"""
        SELECT
            {select_company},
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
            addr.state {group_by_company}
        ORDER BY
            total_revenue DESC
        LIMIT 5
    """

    # 4. Fetch Data
    data = frappe.db.sql(query, filters, as_dict=True)

    return columns, data