# Copyright (c) 2026, Saad and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{"label": "Year", "fieldname": "year", "fieldtype": "Data", "width": 100},
		{"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
		{"label": "Customer Name", "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
		{"label": "No. of Orders", "fieldname": "no_of_orders", "fieldtype": "Int", "width": 140},
		{"label": "Orders Amount", "fieldname": "orders_amount", "fieldtype": "Currency", "width": 160},
	]

	conditions = "IFNULL(imported, 0) = 0"
	if filters and filters.get("company"):
		conditions += " AND register_company = %(company)s"

	data = frappe.db.sql(
		f"""
		SELECT
			YEAR(creation) AS year,
			name AS customer,
			customer_name,
			CAST(NULLIF(no_of_orders, '') AS UNSIGNED) AS no_of_orders,
			CAST(NULLIF(orders_amount, '') AS DECIMAL(18,2)) AS orders_amount
		FROM `tabCustomer`
		WHERE {conditions}
		ORDER BY year, customer_name
		""",
		filters,
		as_dict=True,
	)

	return columns, data
