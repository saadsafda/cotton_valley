import frappe

ROLE_ALLOWED_HOME_SHORTCUTS = {
    "In house SR": {
        "CV Customer",
        "CV Sales Order",
        "CV Sales Invoice",
        "UDC Customer",
        "UDC Sales Order",
        "UDC Sales Invoice",
    },
    "In house SR Product": {
        "CV Product",
        "UDC Product",
    },
}

ALLOWED_WORKSPACES = {"Home", "Dashboard V1"}


def _get_allowed_shortcuts():
    """Return the set of Home shortcuts allowed for the current user, or None if unrestricted.

    Only restricts users who hold one of the roles in ROLE_ALLOWED_HOME_SHORTCUTS
    and do NOT have Administrator or System Manager privileges. A user matching
    more than one restricted role sees the union of their allowed shortcuts.
    """
    user = frappe.session.user
    if user == "Administrator":
        return None

    roles = frappe.get_roles()
    if "System Manager" in roles:
        return None

    allowed = set()
    matched = False
    for role_name, shortcuts in ROLE_ALLOWED_HOME_SHORTCUTS.items():
        if role_name in roles:
            matched = True
            allowed |= shortcuts

    return allowed if matched else None


def filter_workspace_sidebar(pages):
    """Remove sidebar workspaces not in the allowed list for restricted users."""
    if _get_allowed_shortcuts() is None:
        return pages

    if isinstance(pages, dict) and "pages" in pages:
        pages["pages"] = [
            p for p in pages["pages"]
            if p.get("name") in ALLOWED_WORKSPACES
            or p.get("title") in ALLOWED_WORKSPACES
        ]
    return pages


def filter_home_page(result, page_name):
    """Filter Home workspace shortcuts for restricted users."""
    allowed_shortcuts = _get_allowed_shortcuts()
    if allowed_shortcuts is None:
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
            if _get_label(s) in allowed_shortcuts
        ]
    elif isinstance(shortcuts, list):
        result["shortcuts"] = [
            s for s in shortcuts
            if _get_label(s) in allowed_shortcuts
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
