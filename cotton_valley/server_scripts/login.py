import frappe
from frappe import _


def _is_mobile_login_request():
    request = getattr(frappe, "request", None)
    form = getattr(frappe, "form_dict", {}) or {}
    headers = getattr(request, "headers", {}) if request else {}

    header_source = (headers.get("X-Login-Source") or headers.get("X-Client-Source") or "").lower()
    form_source = str(form.get("login_source") or form.get("source") or form.get("device") or "").lower()

    if header_source == "mobile" or form_source == "mobile":
        return True

    if form.get("device_id") or form.get("deviceId"):
        return True

    return False


def _is_browser_login_request():
    request = getattr(frappe, "request", None)
    headers = getattr(request, "headers", {}) if request else {}

    referer = (headers.get("Referer") or "").lower()
    if "/login" in referer or "/app" in referer:
        return True

    if headers.get("Sec-Fetch-Mode") or headers.get("Sec-Fetch-Site") or headers.get("Sec-Fetch-Dest"):
        return True

    return False


def on_login(login_manager):
    """
    Block users with 'Sales Person' role from logging in via the web frontend (desk).
    Mobile/API login must explicitly identify itself (header or form param) to bypass.
    """
    user = login_manager.user
    if not user:
        return

    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
    if not employee:
        return

    for_mobile_app = frappe.db.get_value("Sales Person", {"employee": employee}, "only_for_mobile_app")
    if not for_mobile_app:
        return

    roles = frappe.db.get_all("Has Role", filters={"parent": user}, pluck="role")
    if "Sales Person" in roles and not _is_mobile_login_request() and _is_browser_login_request():
        frappe.throw(
            _("You are not allowed to login from the web interface. Please use the mobile app."),
            title=_("Access Denied"),
        )