import frappe
from frappe.permissions import add_permission, update_permission_property

ROLE = "In House SR Catalog"

# Doctype permissions needed to run the catalog reports and their Link filters
DOCTYPE_PERMISSIONS = {
	"Item": ["read", "report"],
	"Company": ["read"],
	"Price List": ["read"],
	"Item Group": ["read"],
	"Product Category": ["read"],
	"Product Subcategory": ["read"],
	"Customer": ["select"],
}


def execute():
	if not frappe.db.exists("Role", ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 1}).insert(
			ignore_permissions=True
		)

	for doctype, ptypes in DOCTYPE_PERMISSIONS.items():
		if not frappe.db.exists("DocType", doctype):
			continue

		add_permission(doctype, ROLE, 0, ptypes[0])
		for ptype in ptypes[1:]:
			update_permission_property(doctype, ROLE, 0, ptype, 1)

		# Custom DocPerm defaults read to 1; drop it for select-only rules
		if "read" not in ptypes:
			update_permission_property(doctype, ROLE, 0, "read", 0)

	frappe.clear_cache()
