# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    # 1. Define Columns
    columns = [
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
        {"label": "Sales Person", "fieldname": "sales_person", "fieldtype": "Data", "width": 150},
        {"label": "Total Orders", "fieldname": "total_orders", "fieldtype": "Int", "width": 100},
        {"label": "Total Quantity", "fieldname": "total_quantity", "fieldtype": "Float", "width": 120},
        {"label": "Total Amount", "fieldname": "total_amount", "fieldtype": "Currency", "width": 150}
    ]

    # 2. Build Filter Conditions
    # Default: only Submitted orders (docstatus = 1)
    conditions = "so.docstatus = 1"
    
    # Dynamic Company Filter
    if filters.get("company"):
        conditions += " AND so.company = %(company)s"

    # 3. SQL Query
    query = f"""
        SELECT
            so.custom_customer_sales_representative AS sales_person,
            so.company,
            COUNT(DISTINCT so.name) AS total_orders,
            SUM(so_item.qty) AS total_quantity,
            SUM(so_item.base_net_amount) AS total_amount
        FROM
            `tabSales Order` AS so
        LEFT JOIN
            `tabSales Team` AS st ON st.parent = so.name
        LEFT JOIN
            `tabSales Order Item` AS so_item ON so_item.parent = so.name
        WHERE
            {conditions}
        GROUP BY
            so.custom_customer_sales_representative,
            so.company
        ORDER BY
            total_amount DESC
        LIMIT 5
    """

    # 4. Fetch Data
    data = frappe.db.sql(query, filters, as_dict=True)

    return columns, data