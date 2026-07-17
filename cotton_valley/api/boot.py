import frappe

ROLE_ALLOWED_SEARCH_DOCTYPES = {
    "In house SR": {"Sales Order", "Sales Invoice", "Customer"},
    "In house SR Product": {"Item"},
}
ALLOWED_WORKSPACES = {"Home", "Dashboard V1"}

def extend_bootinfo(bootinfo):
    """Extend bootinfo to restrict search and visibility for specific roles."""
    allowed_search_doctypes = _get_allowed_search_doctypes()
    if allowed_search_doctypes is not None:
        _restrict_bootinfo(bootinfo, allowed_search_doctypes)

def _get_allowed_search_doctypes():
    """Return allowed search doctypes for the current user, or None if unrestricted."""
    user = frappe.session.user
    if user == "Administrator":
        return None

    roles = frappe.get_roles()
    if "System Manager" in roles:
        return None

    allowed = set()
    matched = False
    for role_name, doctypes in ROLE_ALLOWED_SEARCH_DOCTYPES.items():
        if role_name in roles:
            matched = True
            allowed |= doctypes

    return allowed if matched else None

def _restrict_bootinfo(bootinfo, allowed_search_doctypes):
    """Apply strict restrictions to the bootinfo payload for the restricted user."""

    # 1. Restrict Doctypes in search (Awesome Bar)
    if "user" in bootinfo and "can_search" in bootinfo.user:
        bootinfo.user.can_search = [
            d for d in bootinfo.user.can_search
            if d in allowed_search_doctypes
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
