import frappe
from frappe.utils.data import now_datetime

def get_customer_from_token():
    auth_header = frappe.get_request_header("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        frappe.throw("Missing or invalid token", frappe.PermissionError)

    token = auth_header.split(" ")[1]

    token_doc = frappe.db.get_value(
        "Customer Token",
        {"token": token, "active": 1},
        ["customer", "valid_till"],
        as_dict=True
    )

    if not token_doc:
        frappe.throw("Invalid token", frappe.PermissionError)

    if now_datetime() > token_doc.valid_till:
        frappe.throw("Token expired", frappe.PermissionError)

    return token_doc.customer


def check_customer_token():
    try:
        auth_header = frappe.get_request_header("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return False

        token = auth_header.split(" ")[1]
        token_doc = frappe.db.get_value(
            "Customer Token",
            {"token": token, "active": 1},
            ["customer", "valid_till"],
            as_dict=True
        )

        if not token_doc:
            return False

        if now_datetime() > token_doc.valid_till:
            return False

        return True

    except Exception as e:
        return None