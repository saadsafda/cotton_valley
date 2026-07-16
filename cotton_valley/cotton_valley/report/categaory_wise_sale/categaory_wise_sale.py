# Copyright (c) 2026, Saad and contributors
# For license information, please see license.txt

import frappe


def _resolve_item_category_mapping():
	"""Resolve Item's category child table and linked category field.

	Item categories are stored in Item table-multiselect field `custom_product_categories`.
	This returns the child doctype and the field that links to Product Category.
	"""
	item_meta = frappe.get_meta("Item")
	table_field = item_meta.get_field("custom_product_categories")

	child_dt = table_field.options if table_field and table_field.options else None
	if not child_dt:
		return None, None

	cat_field = None
	child_meta = frappe.get_meta(child_dt)
	for df in child_meta.fields:
		if df.fieldtype == "Link" and df.options == "Product Category":
			cat_field = df.fieldname
			break

	return child_dt, cat_field


def execute(filters=None):
	filters = filters or {}

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns():
	return [
		{"label": "Category ID", "fieldname": "category_id", "fieldtype": "Link", "options": "Product Category", "width": 120},
		{"label": "Category", "fieldname": "category_title", "fieldtype": "Data", "width": 200},
		{"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
		{"label": "Total Qty Sold", "fieldname": "total_quantity_sold", "fieldtype": "Float", "width": 130},
		{"label": "Total Sales Value", "fieldname": "total_sales_value", "fieldtype": "Currency", "width": 150},
	]


def get_data(filters):
	child_dt, cat_field = _resolve_item_category_mapping()

	# If the category mapping is not configured, there is nothing to report on.
	if not child_dt or not cat_field:
		return []

	conditions = ""
	query_values = {}

	if filters.get("company"):
		conditions += " AND so.company = %(company)s"
		query_values["company"] = filters.get("company")

	query = """
		SELECT
			p.name AS category_id,
			p.title AS category_title,
			so.company AS company,
			SUM(soi.qty) AS total_quantity_sold,
			SUM(soi.qty * soi.base_rate) AS total_sales_value
		FROM
			`tabSales Order Item` soi
		JOIN
			`tabSales Order` so ON soi.parent = so.name
		JOIN
			`tab{child_dt}` ic
				ON ic.parent = soi.item_code
				AND ic.parenttype = 'Item'
				AND ic.parentfield = 'custom_product_categories'
		JOIN
			`tabProduct Category` p ON p.name = ic.`{cat_field}`
		WHERE
			so.docstatus = 1
			{conditions}
		GROUP BY
			p.name, so.company
		ORDER BY
			total_sales_value DESC
	""".format(child_dt=child_dt, cat_field=cat_field, conditions=conditions)

	return frappe.db.sql(query, query_values, as_dict=True)
