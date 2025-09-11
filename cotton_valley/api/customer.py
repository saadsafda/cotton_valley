import frappe # type: ignore
from frappe.auth import LoginManager # type: ignore
from frappe.exceptions import AuthenticationError # type: ignore
from cotton_valley.api.website_theme_setting import get_file

@frappe.whitelist(allow_guest=True)
def customer_login(email, password):
    try:
        # print("user value", email)
        customer_id = frappe.db.get_value("Customer", {"custom_email_address": email}, "name")
        if not customer_id:
            frappe.local.response["http_status_code"] = 404
            return {"status": "error", "message": "Customer not found"}
        
        if not frappe.db.exists("User", {"name": email}):
            return {"status": "error", "message": "User not found"}
        user = frappe.get_doc("User", email)

        login_manager = LoginManager()
        login_manager.authenticate(user=email, pwd=password)
        login_manager.post_login()

        # Get User

        customer = frappe.get_doc("Customer", customer_id)

        # Prepare token (Bearer)
        access_token = frappe.session.sid  

        return {
            "status": 200,
            "message": "Login successful",
            "access_token": access_token,   # Bearer token
            "token_type": "token",
            "user": {
                "email": user.email,
                "full_name": user.full_name,
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
        frappe.local.login_manager.logout()
        frappe.db.commit() # Ensure session changes are saved

        return {"status": 200, "message": "Logout successful"}

    except Exception as e:
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}

@frappe.whitelist(allow_guest=True)
def get_current_customer():
    try:
        if frappe.session.user == "Guest":
            frappe.local.response["http_status_code"] = 401
            return {"status": "error", "message": "Unauthorized. Please log in."}

        email = frappe.session.user
        print(email, "checking email id")
        customer_id = frappe.db.get_value("Customer", {"custom_email_address": email}, "name")
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
            addresses.append({
                "id": addr_doc.name,
                "title": addr_doc.address_title,
                "street": addr_doc.address_line1,
                "city": addr_doc.city,
                "pincode": addr_doc.pincode,
                "is_default": 1 if addr_doc.name == customer.customer_primary_address else 0,
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


