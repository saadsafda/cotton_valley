import frappe

ROLE_NAME = "In house SR"
ALLOWED_SEARCH_DOCTYPES = {"Sales Order", "Sales Invoice", "Customer"}
ALLOWED_WORKSPACES = {"Home", "Dashboard V1"}

def extend_bootinfo(bootinfo):
    """Extend bootinfo to restrict search and visibility for specific roles."""
    if _is_limited_user():
        _restrict_bootinfo(bootinfo)

def _is_limited_user():
    """Check if the current user should be restricted."""
    user = frappe.session.user
    if user == "Administrator":
        return False

    roles = frappe.get_roles()
    if "System Manager" in roles:
        return False

    return ROLE_NAME in roles

def _restrict_bootinfo(bootinfo):
    """Apply strict restrictions to the bootinfo payload for the restricted user."""
    
    # 1. Restrict Doctypes in search (Awesome Bar)
    if "user" in bootinfo and "can_search" in bootinfo.user:
        bootinfo.user.can_search = [
            d for d in bootinfo.user.can_search
            if d in ALLOWED_SEARCH_DOCTYPES
        ]
        
    # 2. Restrict Workspaces in search and sidebar
    if "allowed_workspaces" in bootinfo:
        bootinfo.allowed_workspaces = [
            w for w in bootinfo.allowed_workspaces
            if w.get("name") in ALLOWED_WORKSPACES
            or w.get("title") in ALLOWED_WORKSPACES
        ]
        
    # 3. Strip all reports from search
    if "user" in bootinfo and "all_reports" in bootinfo.user:
        bootinfo.user.all_reports = {}

    # 4. Strip pages from search (except allowed ones if any)
    if "page_info" in bootinfo:
        # We can just empty it or leave specific standard ones
        bootinfo.page_info = {}

    # 5. Strip dashboards from search
    if "dashboards" in bootinfo:
        bootinfo.dashboards = []
