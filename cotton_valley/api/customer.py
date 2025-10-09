import frappe, secrets # type: ignore
from frappe.auth import LoginManager # type: ignore
from frappe.exceptions import AuthenticationError # type: ignore
from cotton_valley.api.website_theme_setting import get_file
from cotton_valley.api.common import get_customer_from_token
from frappe.utils.data import add_days, now_datetime


@frappe.whitelist(allow_guest=True)
def is_email_exists(email):
    try:
        customer_id = frappe.db.get_value("Customer", {"custom_email_address": email}, "name")
        if customer_id:
            return {"status": "success", "exists": True}
        else:
            return {"status": "error", "exists": False}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@frappe.whitelist(allow_guest=True)
def sale_rep_as_customer(customer_id):
    try:
        customer = frappe.get_doc("Customer", customer_id)
        if customer:
            email = customer.custom_email_address
            password = customer.get_password('custom_password')

            result = customer_login(email, password)
            return {"status": "success", "message": result}
        else:
            return {"status": "error", "message": "Customer not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    

@frappe.whitelist(allow_guest=True)
def customer_login(email, password):
    try:
        customer_id = frappe.db.get_value("Customer", {"custom_email_address": email, "disabled": 1}, "name")
        if customer_id:
            return {"status": "error", "message": "Your account has been disabled. Please contact support."}

        # Find customer by custom email
        customer_id = frappe.db.get_value("Customer", {"custom_email_address": email, "disabled": 0}, "name")
        if not customer_id:
            return {"status": "error", "message": "Customer not found"}
        
        customer = frappe.get_doc("Customer", customer_id)

        # Check password
        if customer.get_password("custom_password") != password:
            return {"status": "error", "message": "Invalid email or password"}

        # Generate token
        token = secrets.token_urlsafe(32)
        valid_till = add_days(now_datetime(), 1)  # 1 day validity

        # Store in Customer Token
        frappe.get_doc({
            "doctype": "Customer Token",
            "customer": customer.name,
            "token": token,
            "valid_till": valid_till,
            "active": 1
        }).insert(ignore_permissions=True)

        return {
            "status": 200,
            "message": "Login successful",
            "access_token": token,   # Bearer token
            "token_type": "token",
            "user": {
                "email": customer.custom_email_address,
                "full_name": customer.customer_name + (" " + customer.custom_last_name if customer.custom_last_name else ""),
                "customer_id": customer.name
            },
            "data": customer.as_dict()
        }
    except AuthenticationError:
        frappe.local.response["http_status_code"] = 404
        return {"status": "error", "message": "Invalid email or password"}
    except Exception as e:
        frappe.local.response["http_status_code"] = 401
        return {"status": "error", "message": str(e)}


@frappe.whitelist(allow_guest=True)
def customer_logout():
    try:
        auth_header = frappe.get_request_header("Customer-Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            frappe.throw("Missing or invalid token", frappe.PermissionError)

        token = auth_header.split(" ")[1]

        token_doc = frappe.db.get_value("Customer Token", {"token": token}, "name")

        customer_token = frappe.get_doc("Customer Token", token_doc)
        customer_token.active = 0
        customer_token.save()

        return {"status": 200, "message": "Logout successful"}

    except Exception as e:
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}

@frappe.whitelist(allow_guest=True)
def get_current_customer():
    try:
        customer_id = get_customer_from_token()
        
        if not customer_id:
            return {"status": "error", "message": "Customer not found"}

        customer = frappe.get_doc("Customer", customer_id)

        # --- Base Customer Info ---
        customer_data = {
            "id": customer.name,
            "name": customer.customer_name,
            "email": customer.custom_email_address,
            "country_code": customer.custom_phone_number[:1] if customer.custom_phone_number else None,
            "phone": customer.custom_phone_number,
            "profile_image_id": customer.image,
            "status": 1 if not customer.disabled else 0,
            "created_at": customer.creation,
            "updated_at": customer.modified,
        }

        if customer.custom_sales_respresentive:
            sales_rep = frappe.get_doc("Sales Person", customer.custom_sales_respresentive)
            sales_employee = {}
            if sales_rep.employee:
                sales_employee = frappe.db.get_value("Employee", {"name": sales_rep.employee}, ["user_id", "cell_number"], as_dict=True)
            customer_data['sales_person'] = {
                "id": sales_rep.name,
                "name": sales_rep.sales_person_name,
                "email": sales_employee.get("user_id", ""),
                "phone": sales_employee.get("cell_number", ""),
            }

        # --- Role ---
        customer_data["role"] = {
            "id": customer.name,
            "name": "consumer",
            "guard_name": "web",
            "system_reserve": "1",
            "created_at": "2023-08-24T08:16:03.000000Z",
            "updated_at": "2023-08-24T08:16:03.000000Z",
            "pivot": {
                "model_id": "19",
                "role_id": "2",
                "model_type": "App\\Models\\User"
            }
        }

        # --- Wallet / Points (custom doctypes) ---
        customer_data["wallet"] = {
            "id": 1,
            "consumer_id": 19,
            "balance": 84.4
        }
        customer_data["point"] = {
            "id": 3,
            "consumer_id": 19,
            "balance": 300
        }

        # --- Addresses ---
        links = frappe.get_all("Dynamic Link",
            filters={"link_doctype": "Customer", "link_name": customer_id},
            fields=["parent"]
        )
        addresses = []
        for link in links:
            addr_doc = frappe.get_doc("Address", link.parent)
            is_default = 0
            if addr_doc.address_type == "Shipping" and addr_doc.name == customer.customer_primary_address:
                is_default = 1

            if addr_doc.address_type == "Billing" and addr_doc.name == customer.customer_billing_address:
                is_default = 1

            addresses.append({
                "id": addr_doc.name,
                "title": addr_doc.address_title,
                "street": addr_doc.address_line1,
                "address_type": addr_doc.address_type,
                "city": addr_doc.city,
                "pincode": addr_doc.pincode,
                "is_default": is_default,
                "country_code": customer_data["country_code"],
                "phone": addr_doc.phone,
                "country": {"id": addr_doc.country, "name": addr_doc.country},
                "state": {"id": addr_doc.state, "name": addr_doc.state},
            })
        customer_data["address"] = addresses

        # --- Profile Image ---
        customer_data["profile_image"] = get_file(customer.image)

        # --- Payment Account (if you have one) ---
        # payment_account = frappe.db.get_value(
        #     "Payment Account", {"customer": customer_id},
        #     ["name", "paypal_email", "bank_name", "bank_account_no"], as_dict=True
        # )
        # if payment_account:
        #     customer_data["payment_account"] = {
        #         "id": payment_account.name,
        #         "user_id": customer_id,
        #         "paypal_email": payment_account.paypal_email,
        #         "bank_name": payment_account.bank_name,
        #         "bank_account_no": payment_account.bank_account_no,
        #     }
        # else:
        customer_data["payment_account"] = {
            "id": 1,
            "user_id": customer_id,
            "paypal_email": None,
            "bank_name": None,
            "bank_holder_name": None,
            "bank_account_no": None,
            "swift": None,
            "ifsc": None,
            "is_default": "0",
            "status": 1,
            "created_at": "2023-09-30T12:55:44.000000Z",
            "updated_at": "2023-09-30T12:55:44.000000Z",
            "deleted_at": None
        }

        return customer_data

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Current Customer Failed")
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}


