import frappe


def execute():
	# Backfill invoices submitted before the on_submit hook set order_status
	frappe.db.sql(
		"""
		UPDATE `tabSales Invoice`
		SET order_status = 'Shipped'
		WHERE docstatus = 1 AND IFNULL(order_status, '') != 'Shipped'
		"""
	)
