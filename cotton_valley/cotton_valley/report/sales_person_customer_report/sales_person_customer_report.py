# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.utils import getdate


def execute(filters=None):
	columns = [
		{"label": "Sales Person", "fieldname": "sales_person", "fieldtype": "Data", "width": 180},
		{"label": "Customer", "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
		{"label": "CV Price Level", "fieldname": "cv_price", "fieldtype": "Data", "width": 150},
		{"label": "UDC Price Level", "fieldname": "udc_price", "fieldtype": "Data", "width": 150},
		{"label": "Assigned Price Date (CV)", "fieldname": "cv_assigned_date", "fieldtype": "Datetime", "width": 180},
		{"label": "Assigned Price Date (UDC)", "fieldname": "udc_assigned_date", "fieldtype": "Datetime", "width": 180},
		{"label": "Last Change Date in Price Level", "fieldname": "last_change_date", "fieldtype": "Datetime", "width": 180},
	]

	data = []

	# Build customer query filters
	customer_filters = {}
	
	if filters and filters.get("sales_person"):
		customer_filters["sales_person"] = filters.get("sales_person")
	
	if filters and filters.get("customer"):
		customer_filters["name"] = filters.get("customer")
	
	if filters and filters.get("cv_price_level"):
		customer_filters["price_list_for_cv"] = filters.get("cv_price_level")
	
	if filters and filters.get("udc_price_level"):
		customer_filters["price_list_for_udc"] = filters.get("udc_price_level")

	customers = frappe.db.get_list(
		"Customer",
		filters=customer_filters,
		fields=["name", "sales_person", "customer_name", "price_list_for_cv", "price_list_for_udc"]
	)

	for cust in customers:

		# get change logs from Version table
		versions = frappe.db.get_all(
			"Version",
			filters={"ref_doctype": "Customer", "docname": cust.name},
			fields=["data", "creation"],
			order_by="creation desc"
		)

		cv_assigned_date = None
		udc_assigned_date = None
		last_change_date = None

		for v in versions:
			try:
				changes = json.loads(v.data)
				if "changed" in changes:
					for change in changes["changed"]:
						fieldname, old, new = change
						if fieldname == "price_list_for_cv" and not cv_assigned_date:
							cv_assigned_date = v.creation
							last_change_date = v.creation
						if fieldname == "price_list_for_udc" and not udc_assigned_date:
							udc_assigned_date = v.creation
							last_change_date = v.creation
			except Exception:
				pass

		# Apply date filters
		include_row = True
		
		if filters and last_change_date:
			# Convert last_change_date to date for comparison
			last_change_date_only = getdate(last_change_date)
			
			if filters.get("from_date"):
				from_date = getdate(filters.get("from_date"))
				if last_change_date_only < from_date:
					include_row = False
			
			if filters.get("to_date"):
				to_date = getdate(filters.get("to_date"))
				if last_change_date_only > to_date:
					include_row = False
		
		if include_row:
			data.append({
				"sales_person": cust.sales_person,
				"customer_name": cust.customer_name,
				"cv_price": cust.price_list_for_cv,
				"udc_price": cust.price_list_for_udc,
				"cv_assigned_date": cv_assigned_date,
				"udc_assigned_date": udc_assigned_date,
				"last_change_date": last_change_date,
			})

	return columns, data
