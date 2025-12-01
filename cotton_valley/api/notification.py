import frappe
from cotton_valley.api.common import get_customer_from_token


@frappe.whitelist(allow_guest=True)
def get_customer_notifications():
    """
    Fetch notifications for the authenticated customer.
    """
    try:
        customer = get_customer_from_token()
        if not customer:
            return {
                "status": "error",
                "message": "Authentication required",
                "data": []
            }

        notifications = frappe.db.sql("""
            SELECT 
                n.message,
                n.date_and_time
            FROM `tabNotifications` n
            WHERE n.parent = %s
            ORDER BY n.created_at DESC
        """, (customer,), as_dict=True)

        return {
            "status": "success",
            "message": "Notifications fetched successfully",
            "data": notifications
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Fetch Customer Notifications Failed")
        return {
            "status": "error",
            "message": str(e),
            "data": []
        }