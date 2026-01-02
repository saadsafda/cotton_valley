# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    # 1. Define Columns
    columns = [
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
        {"label": "Sales Order", "fieldname": "name", "fieldtype": "Link", "options": "Sales Order", "width": 150},
        {"label": "Order Date", "fieldname": "transaction_date", "fieldtype": "Date", "width": 120},
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
        {"label": "Total Amount", "fieldname": "grand_total", "fieldtype": "Currency", "width": 120},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100}
    ]

    # 2. Build Conditions
    # Start with docstatus = 1 (Submitted)
    conditions = "docstatus = 1"
    
    # Dynamic Company Filter
    if filters.get("company"):
        conditions += " AND company = %(company)s"

    # 3. SQL Query
    # usage of %%Y-%%m-01 escapes the percent sign for Python
    query = f"""
        SELECT
            name,
            transaction_date,
            customer,
            company,
            grand_total,
            status
        FROM
            `tabSales Order`
        WHERE
            {conditions}
            AND transaction_date = CURDATE()
        ORDER BY
            transaction_date DESC
    """

    # 4. Fetch Data
    data = frappe.db.sql(query, filters, as_dict=True)

    return columns, data