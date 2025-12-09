# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    columns = [
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 200},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": "Total Qty Sold", "fieldname": "total_quantity_sold", "fieldtype": "Float", "width": 120},
        {"label": "Total Sales Value", "fieldname": "total_sales_value", "fieldtype": "Currency", "width": 150}
    ]

    # Dynamic Filter Logic
    conditions = ""
    if filters.get("company"):
        conditions += " AND SO.company = %(company)s"

    query = f"""
        SELECT
            SOI.item_code AS item_code,
            SOI.item_name AS item_name,
            SO.company AS company,
            SUM(SOI.qty) AS total_quantity_sold,
            SUM(SOI.qty * SOI.base_rate) AS total_sales_value
        FROM
            `tabSales Order Item` SOI
        JOIN
            `tabSales Order` SO ON SOI.parent = SO.name
        WHERE
            SO.docstatus = 1
            {conditions}
        GROUP BY
            SOI.item_code, 
            SOI.item_name, 
            SO.company
        ORDER BY
            total_quantity_sold DESC, total_sales_value DESC
        LIMIT 5
    """

    data = frappe.db.sql(query, filters, as_dict=True)
    return columns, data