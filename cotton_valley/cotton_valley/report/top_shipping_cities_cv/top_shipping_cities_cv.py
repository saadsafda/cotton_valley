# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    # 1. Define Columns
    columns = [
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
        {"label": "City", "fieldname": "city", "fieldtype": "Data", "width": 180},
        {"label": "Total Orders", "fieldname": "total_orders", "fieldtype": "Int", "width": 120},
        {"label": "Total Order Value", "fieldname": "total_order_value", "fieldtype": "Currency", "width": 150}
    ]

	# 2. Define Conditions
    conditions = "SO.company = 'Cotton Valley'"

    # 3. SQL Query
    query = f"""
        SELECT
			SO.company AS company,
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
            {conditions}
        GROUP BY
            A.city,
			SO.company
        ORDER BY
            total_orders DESC, total_order_value DESC
        
    """

    # 4. Fetch Data
    data = frappe.db.sql(query, filters, as_dict=True)

    return columns, data