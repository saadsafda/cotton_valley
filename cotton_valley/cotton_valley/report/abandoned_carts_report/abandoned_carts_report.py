# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    # 1. Define Columns
    columns = [
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
        {"label": "SKU", "fieldname": "item_code", "fieldtype": "Data", "width": 150},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 350},
        {"label": "Total Abandoned Quantity", "fieldname": "total_abandoned_quantity", "fieldtype": "Float", "width": 150},
        {"label": "Total Abandoned Value", "fieldname": "total_abandoned_value", "fieldtype": "Currency", "width": 150}
    ]

    # 2. Build the Condition String
    # Start with "1=1" so we can easily append "AND ..." conditions
    conditions = "1=1"
    
    # Only add the company filter if the user has selected one
    if filters.get("company"):
        conditions += " AND T2.company = %(company)s"

    # 3. The SQL Query
    query = f"""
        SELECT
            T1.item_code,
            T1.item_name,
            T2.company,
            SUM(T1.qty) AS total_abandoned_quantity,
            SUM(T1.base_rate * T1.qty) AS total_abandoned_value
        FROM
            `tabSales Order Item` T1
        JOIN
            `tabSales Order` T2 ON T1.parent = T2.name
        WHERE
            {conditions}
        GROUP BY
            T1.item_code,
            T1.item_name,
            T2.company
        ORDER BY
            total_abandoned_value DESC
        LIMIT 5
    """

    # 4. Fetch Data
    data = frappe.db.sql(query, filters, as_dict=True)

    return columns, data