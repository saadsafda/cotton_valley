import frappe

from cotton_valley.server_scripts.item import COMPANY_SPECIFIC_FIELDS, COMPANY_WAREHOUSES


def execute():
	for company, warehouse in COMPANY_WAREHOUSES.items():
		if not frappe.db.exists("Company", company) or not frappe.db.exists("Warehouse", warehouse):
			continue

		# Items that already have a default row for their company: just fix the warehouse
		frappe.db.sql(
			"""
			UPDATE `tabItem Default` d
			JOIN `tabItem` i ON i.name = d.parent
			SET d.default_warehouse = %(warehouse)s
			WHERE d.parenttype = 'Item'
				AND i.company = %(company)s
				AND d.company = %(company)s
				AND IFNULL(d.default_warehouse, '') != %(warehouse)s
			""",
			{"company": company, "warehouse": warehouse},
		)

		# Items with no default row for their company: repoint the first row, or add one
		items = frappe.db.sql_list(
			"""
			SELECT i.name FROM `tabItem` i
			WHERE i.company = %(company)s
				AND NOT EXISTS (
					SELECT 1 FROM `tabItem Default` d
					WHERE d.parent = i.name AND d.parenttype = 'Item' AND d.company = %(company)s
				)
			""",
			{"company": company},
		)

		for item in items:
			row = frappe.db.get_value(
				"Item Default", {"parent": item, "parenttype": "Item"}, "name", order_by="idx asc"
			)
			if row:
				values = {"company": company, "default_warehouse": warehouse}
				values.update({field: None for field in COMPANY_SPECIFIC_FIELDS})
				frappe.db.set_value("Item Default", row, values, update_modified=False)
			else:
				frappe.get_doc(
					{
						"doctype": "Item Default",
						"parent": item,
						"parenttype": "Item",
						"parentfield": "item_defaults",
						"idx": 1,
						"company": company,
						"default_warehouse": warehouse,
					}
				).db_insert()

	frappe.db.commit()
