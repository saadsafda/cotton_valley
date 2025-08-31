import frappe

@frappe.whitelist(allow_guest=True)
def get_categories():
    categories = frappe.get_all("Category", fields=["name", "category_name"])
    return categories