import frappe
from json import loads
from frappe.desk.desktop import (
    get_workspace_sidebar_items as _original_get_sidebar,
    get_desktop_page as _original_get_desktop_page,
)
from cotton_valley.overrides.workspace_filter import (
    filter_workspace_sidebar,
    filter_home_page,
)


@frappe.whitelist()
def get_workspace_sidebar_items():
    """Override: filter sidebar items based on role."""
    result = _original_get_sidebar()
    return filter_workspace_sidebar(result)


@frappe.whitelist()
def get_desktop_page(page):
    """Override: filter workspace page content based on role."""
    # Extract page name from the JSON input before calling original
    try:
        page_data = loads(page) if isinstance(page, str) else page
        page_name = page_data.get("name", "") or page_data.get("label", "")
    except Exception:
        page_name = ""

    result = _original_get_desktop_page(page)
    return filter_home_page(result, page_name)
