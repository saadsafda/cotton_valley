import frappe
from frappe import _

def on_login(login_manager):
    """
    Block users with 'Sales Person' role from logging in via the web frontend (desk).
    They can still authenticate through API (token/API key auth) because
    API key authentication in Frappe does NOT trigger the on_login hook —
    it bypasses LoginManager entirely.
    """
    user = login_manager.user
    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
    for_mobile_app = frappe.db.get_value("Sales Person", {"employee": employee}, "only_for_mobile_app")

    if for_mobile_app and "Sales Person" in frappe.db.get_all("Has Role", filters={"parent": user}, pluck="role"):
        frappe.throw(
            _("You are not allowed to login from the web interface. Please use the mobile app."),
            title=_("Access Denied")
        )