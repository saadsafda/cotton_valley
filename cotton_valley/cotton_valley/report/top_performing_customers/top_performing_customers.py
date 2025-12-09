# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    # 1. Define Columns
    columns = [
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150}, # Added Company
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 200},
        {"label": "Account Number", "fieldname": "customer_account_number", "fieldtype": "Data", "width": 150},
        {"label": "No. of Orders", "fieldname": "total_orders", "fieldtype": "Int", "width": 120},
        {"label": "Total Sales", "fieldname": "total_sales", "fieldtype": "Currency", "width": 150}
    ]

    # 2. Build Filter Conditions
    # Default: docstatus = 1 (Submitted Orders only)
    conditions = "docstatus = 1"
    
    # Dynamic Company Filter
    if filters.get("company"):
        conditions += " AND company = %(company)s"

    # 3. SQL Query
    query = f"""
        SELECT
            customer,
            customer_account_number,
            company,
            COUNT(name) AS total_orders,
            SUM(grand_total) AS total_sales
        FROM
            `tabSales Order`
        WHERE
            {conditions}
        GROUP BY
            customer,
            customer_account_number,
            company
        ORDER BY
            total_sales DESC
        LIMIT 10
    """

    # 4. Fetch Data
    data = frappe.db.sql(query, filters, as_dict=True)

    return columns, data	