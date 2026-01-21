import frappe

no_cache = 1

def get_context(context):
    context.no_cache = 1
    
    # Check if user is logged in and has permission
    if frappe.session.user == "Guest":
        frappe.throw("Please login to access this page", frappe.PermissionError)
    
    # Only allow System Manager or specific roles
    if not frappe.has_permission("Item", "write"):
        frappe.throw("You don't have permission to access this page", frappe.PermissionError)
    
    return context
