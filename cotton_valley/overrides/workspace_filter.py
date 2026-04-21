import frappe

ROLE_NAME = "In house SR"

ALLOWED_HOME_SHORTCUTS = {
    "CV Customer",
    "CV Sales Order",
    "CV Sales Invoice",
    "UDC Customer",
    "UDC Sales Order",
    "UDC Sales Invoice",
}

ALLOWED_WORKSPACES = {"Home", "Dashboard V1"}


def _is_limited_user():
    """Check if the current user should be filtered.

    Only apply filtering to users who have the 'In house SR' role
    but do NOT have Administrator or System Manager privileges.
    """
    user = frappe.session.user
    if user == "Administrator":
        return False

    roles = frappe.get_roles()
    if "System Manager" in roles:
        return False

    return ROLE_NAME in roles


def filter_workspace_sidebar(pages):
    """Remove sidebar workspaces not in the allowed list for In house SR users."""
    if not _is_limited_user():
        return pages

    if isinstance(pages, dict) and "pages" in pages:
        pages["pages"] = [
            p for p in pages["pages"]
            if p.get("name") in ALLOWED_WORKSPACES
            or p.get("title") in ALLOWED_WORKSPACES
        ]
    return pages


def filter_home_page(result, page_name):
    """Filter Home workspace shortcuts for In house SR users."""
    if not _is_limited_user():
        return result

    if page_name != "Home":
        return result

    if not isinstance(result, dict):
        return result

    # Filter shortcuts - structure is {"items": [list of shortcut objects]}
    shortcuts = result.get("shortcuts")
    if isinstance(shortcuts, dict) and "items" in shortcuts:
        shortcuts["items"] = [
            s for s in shortcuts["items"]
            if _get_label(s) in ALLOWED_HOME_SHORTCUTS
        ]
    elif isinstance(shortcuts, list):
        result["shortcuts"] = [
            s for s in shortcuts
            if _get_label(s) in ALLOWED_HOME_SHORTCUTS
        ]

    # Filter cards (link cards) - hide all for limited users on Home
    cards = result.get("cards")
    if isinstance(cards, dict) and "items" in cards:
        cards["items"] = []
    elif isinstance(cards, list):
        result["cards"] = []

    return result


def _get_label(item):
    """Get label from a shortcut item (could be dict or Document object)."""
    if hasattr(item, "label"):
        return item.label
    if isinstance(item, dict):
        return item.get("label", "")
    return ""
