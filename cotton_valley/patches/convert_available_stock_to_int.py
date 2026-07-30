import frappe


def execute():
	"""Convert Item.available_stock from Data (varchar) to Int.

	Fixture sync (bench migrate) saves the Custom Field record via the normal
	document flow, which blocks Data -> Int changes (frappe.custom.doctype.
	custom_field.custom_field.py / ALLOWED_FIELDTYPE_CHANGE). Converting the
	column and the Custom Field record here, directly via SQL/db.set_value,
	makes the fixture's fieldtype already match on sync, so the block never
	triggers.
	"""
	if not frappe.db.has_column("Item", "available_stock"):
		return

	current_type = frappe.db.sql(
		"""
		select data_type from information_schema.columns
		where table_schema = database()
			and table_name = 'tabItem'
			and column_name = 'available_stock'
		"""
	)
	if current_type and current_type[0][0] == "int":
		return

	non_numeric = frappe.db.sql(
		"""
		select name, available_stock from `tabItem`
		where ifnull(available_stock, '') != ''
			and available_stock not regexp '^-?[0-9]+$'
		"""
	)
	if non_numeric:
		frappe.db.sql(
			"""
			update `tabItem` set available_stock = null
			where ifnull(available_stock, '') != ''
				and available_stock not regexp '^-?[0-9]+$'
			"""
		)
		frappe.log_error(
			title="Available Stock migration: cleared non-numeric values",
			message=f"{non_numeric}",
		)

	frappe.db.sql("alter table `tabItem` modify `available_stock` int(11) default null")

	if frappe.db.exists("Custom Field", "Item-custom_available_stock"):
		frappe.db.set_value(
			"Custom Field", "Item-custom_available_stock", "fieldtype", "Int", update_modified=False
		)

	frappe.db.commit()
