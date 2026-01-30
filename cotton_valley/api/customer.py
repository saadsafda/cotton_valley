import requests
import frappe, secrets # type: ignore
from frappe.auth import LoginManager # type: ignore
from frappe.exceptions import AuthenticationError # type: ignore
from cotton_valley.api.website_theme_setting import get_file
from cotton_valley.api.common import get_customer_from_token
from frappe.utils.data import add_days, now_datetime
from cotton_valley.secrets import CV_USER, CV_PASSWORD, UDC_USER, UDC_PASSWORD



@frappe.whitelist(allow_guest=True)
def customer_bank_account():
    try:
        customer_id = get_customer_from_token()
        if not customer_id:
            return {"status": "error", "message": "Customer not found"}

        payment_account = frappe.db.get_value(
            "Customer", {"name": customer_id},
            ["custom_bank_name", "custom_bank_address", "custom_bank_phone", "custom_bank_fax", "custom_bank_account_number",
             "custom_bank_city", "custom_bank_state", "custom_bank_zip_code", "custom_bank_account_type", "custom_bank_email"], as_dict=True
        )
        if payment_account:
            return {"status": "success", "data": {
                "bank_name": payment_account.custom_bank_name,
                "bank_address": payment_account.custom_bank_address,
                "bank_phone": payment_account.custom_bank_phone,
                "bank_fax": payment_account.custom_bank_fax,
                "bank_account_number": payment_account.custom_bank_account_number,
                "bank_city": payment_account.custom_bank_city,
                "bank_state": payment_account.custom_bank_state,
                "bank_zip_code": payment_account.custom_bank_zip_code,
                "bank_account_type": payment_account.custom_bank_account_type,
                "bank_email": payment_account.custom_bank_email,
            }}
        else:
            return {"status": "error", "message": "No bank account found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@frappe.whitelist(allow_guest=True)
def update_customer_bank_account(bank_name, bank_address, bank_phone, bank_fax, bank_account_number,
                                 bank_city, bank_state, bank_zip_code, bank_account_type, bank_email):
    try:
        customer_id = get_customer_from_token()
        if not customer_id:
            return {"status": "error", "message": "Customer not found"}

        customer = frappe.get_doc("Customer", customer_id)
        customer.custom_bank_name = bank_name
        customer.custom_bank_address = bank_address
        customer.custom_bank_phone = bank_phone
        customer.custom_bank_fax = bank_fax
        customer.custom_bank_account_number = bank_account_number
        customer.custom_bank_city = bank_city
        customer.custom_bank_state = bank_state
        customer.custom_bank_zip_code = bank_zip_code
        customer.custom_bank_account_type = bank_account_type
        customer.custom_bank_email = bank_email
        customer.save(ignore_permissions=True)

        return {"status": "success", "message": "Bank account updated successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


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
def change_password(current_password, new_password):
    """
    Change customer password.
    
    Args:
        current_password: Current password
        new_password: New password
        
    Returns:
        dict: Status and message
    """
    try:
        # Get customer from token
        customer_id = get_customer_from_token()
        if not customer_id:
            return {"status": "error", "message": "Customer not found. Please login again."}

        # Get customer document
        customer = frappe.get_doc("Customer", customer_id)
        
        # Verify current password
        stored_password = customer.get_password("custom_password")
        if stored_password != current_password:
            return {"status": "error", "message": "Current password is incorrect"}
        
        # Validate new password
        if not new_password or len(new_password) < 8:
            return {"status": "error", "message": "New password must be at least 8 characters long"}

        if new_password == current_password:
            return {"status": "error", "message": "New password must be different from current password"}
        
        # Update password
        customer.custom_password = new_password
        customer.custom_confirm_password = new_password
        customer.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "status": "success", 
            "message": "Password changed successfully"
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Change Password Error")
        return {"status": "error", "message": str(e)}


@frappe.whitelist(allow_guest=True)
def forgot_password(email, company=None):
    """
    Send password reset token to customer email.
    
    Args:
        email: Customer email address
        company: Company name (default: "Cotton Valley")
        
    Returns:
        dict: Status and message
    """
    try:
        # Validate input
        if not email:
            return {"status": "error", "message": "Email is required"}
        
        company = "Cotton Valley" if not company or company == "null" else company
        
        # Find customer by email
        filters = {
            "custom_email_address": email,
            "disabled": 0
        }
        
        customer_id = frappe.db.get_value("Customer", filters, "name")
        
        if not customer_id:
            return {"status": "error", "message": "No account found with this email address"}
        
        customer = frappe.get_doc("Customer", customer_id)
        
        # Generate reset token (valid for 30 minutes)
        reset_token = secrets.token_urlsafe(32)
        reset_token_expiry = add_days(now_datetime(), 0.020833333)  # 30 minutes
        
        # Store reset token in customer document
        customer.custom_reset_token = reset_token
        customer.custom_reset_token_expiry = reset_token_expiry
        customer.save(ignore_permissions=True)
        frappe.db.commit()
        template_name = ""
        if company == "Cotton Valley":
            template_name = "Password Reset - CVL"
        else:
            template_name = "Password Reset - UDC"
        
        # Send email with reset token/link using Email Template
        try:
            # Generate reset link
            reset_link = f"http://localhost:3000/en/auth/update-password?token={reset_token}"
            
            # Try to get Email Template from ERPNext
            try:
                email_template = frappe.get_doc("Email Template", template_name)
                
                # Prepare template arguments
                template_args = {
                    "doc": customer,
                    "customer_name": customer.customer_name,
                    "company": company,
                    "reset_token": reset_token,
                    "reset_link": reset_link,
                    "expiry_minutes": 30
                }
                
                # Render template with Jinja
                subject = frappe.render_template(email_template.subject, template_args)
                response = email_template.response_html if email_template.use_html else email_template.response
                message = frappe.render_template(response, template_args)
                
            except frappe.DoesNotExistError:
                # Fallback to default message if template doesn't exist
                frappe.log_error("Email Template 'Password Reset Request' not found. Using default message.", "Forgot Password Email Template Missing")
                
                subject = f"Password Reset Request - {company}"
                message = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #333;">Password Reset Request</h2>
                    <p>Hello {customer.customer_name},</p>
                    <p>You have requested to reset your password for your {company} account.</p>
                    <div style="background-color: #f5f5f5; padding: 20px; margin: 20px 0;">
                        <a href="{reset_link}" style="display: inline-block; padding: 10px 15px; background-color: #007bff; color: #fff; text-decoration: none; border-radius: 5px;">Reset Password</a>
                    </div>
                    <p><strong>This token will expire in 30 minutes.</strong></p>
                    <p>If you did not request this password reset, please ignore this email or contact support.</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                    <p style="color: #666; font-size: 12px;">This is an automated message, please do not reply to this email.</p>
                </div>
                """

            frappe.sendmail(
                recipients=[email],
                subject=subject,
                message=message,
                now=True
            )
            
        except Exception as email_error:
            frappe.log_error(frappe.get_traceback(), "Forgot Password Email Error")
            return {
                "status": "error", 
                "message": "Failed to send reset token. Please try again later."
            }
        
        return {
            "status": "success",
            "message": "Password reset token has been sent to your email",
            "data": {
                "email": email,
                "token_expires_in_minutes": 30
            }
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Forgot Password Error")
        return {"status": "error", "message": str(e)}


@frappe.whitelist(allow_guest=True)
def reset_password(reset_token, new_password):
    """
    Reset password using reset token.
    
    Args:
        reset_token: Token received via email
        new_password: New password
        
    Returns:
        dict: Status and message
    """
    try:
        if not reset_token or not new_password:
            return {"status": "error", "message": "Reset token and new password are required"}
        
        # Validate new password
        if len(new_password) < 8:
            return {"status": "error", "message": "Password must be at least 8 characters long"}
        
        # Find customer with this reset token
        customer_id = frappe.db.get_value(
            "Customer", 
            {"custom_reset_token": reset_token, "disabled": 0}, 
            "name"
        )
        
        if not customer_id:
            return {"status": "error", "message": "Invalid or expired reset token"}
        
        customer = frappe.get_doc("Customer", customer_id)
        
        # Check if token is expired
        if customer.custom_reset_token_expiry and now_datetime() > customer.custom_reset_token_expiry:
            return {"status": "error", "message": "Reset token has expired. Please request a new one."}
        
        # Update password
        customer.custom_password = new_password
        customer.custom_confirm_password = new_password
        
        # Clear reset token
        customer.custom_reset_token = None
        customer.custom_reset_token_expiry = None
        
        customer.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "status": "success",
            "message": "Password has been reset successfully. You can now login with your new password."
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Reset Password Error")
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
def get_current_customer(company=None):
    try:
        company = "Cotton Valley" if not company or company == "null" else company
        customer_id = get_customer_from_token()
        
        if not customer_id:
            return {"status": "error", "message": "Customer not found"}

        customer = frappe.get_doc("Customer", customer_id)

        # --- Base Customer Info ---
        customer_data = {
            "id": customer.name,
            "name": customer.customer_name,
            "first_name": customer.customer_name,
            "last_name": customer.custom_last_name,
            "email": customer.custom_email_address,
            "country_code": customer.custom_phone_number[:1] if customer.custom_phone_number else None,
            "phone": customer.custom_phone_number,
            "cell_phone": customer.custom_cell_phone,
            "profile_image_id": customer.image,
            "status": 1 if not customer.disabled else 0,
            "mode_of_payment": customer.udc_mode_of_payment if company == "UDC" else customer.mode_of_payment,
            "company": customer.custom_company_name,
            "created_at": customer.creation,
            "updated_at": customer.modified,
        }

        sales_rep = None
        if company == "UDC":
            sales_rep = frappe.get_doc("Sales Person", customer.udc_sales_person) if customer.udc_sales_person else None
        else:
            sales_rep = frappe.get_doc("Sales Person", customer.sales_person) if customer.sales_person else None

        if sales_rep:
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
            filters={"link_doctype": "Customer", "link_name": customer_id, "parenttype": "Address"},
            fields=["parent"]
        )
        addresses = []
        for link in links:
            addr_doc = frappe.get_doc("Address", link.parent)
            if addr_doc.disabled:
                continue
            if addr_doc.company != company:
                continue
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

        # --- Payment Account (Placeholder) ---
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



@frappe.whitelist()
def fetch_customer_data(customer_id, company="Cotton Valley"):
    """
    Fetch customer data from external API and update local Customer record.
    Args:
        customer_id: Customer ID
        company: Company name ("Cotton Valley" or "UDC")
    """

    try:
        customer = frappe.get_doc("Customer", customer_id)
        if not customer:
            frappe.log_error(f"Customer not found: {customer_id}", "Fetch Customer Data Error")
            return {"status": "error", "message": "Customer not found"}

        url_base = f"https://erp.cottonvalley.us/ords/ctnvly_api/stp/cstdata?SBSID_C={customer.cv_customer_id}"
        username = CV_USER
        password = CV_PASSWORD

        if company == "UDC":
            url_base = f"https://erp.universaldc.us/ords/unvdst_api/stp/cstdata?SBSID_C={customer.udc_customer_id}"
            # url_base = f"https://sc14.indus-erp.com/ords/unvdst_api/stp/cstdata?SBSID_C={customer.udc_customer_id}"

            username = UDC_USER
            password = UDC_PASSWORD

        try:
            response = requests.get(url_base, auth=(username, password), verify=False)
        except requests.exceptions.SSLError as ssl_err:
            frappe.log_error("Fetch Customer Data SSL Error", f"SSL error when connecting to external API: {ssl_err}")
            return {
                "status": "error",
                "message": "Could not connect to external service due to SSL certificate verification failure. Please contact support or try again later."
            }
        except requests.exceptions.RequestException as req_err:
            frappe.log_error("Fetch Customer Data Request Error", f"Request error when connecting to external API: {req_err}")
            return {
                "status": "error",
                "message": f"Could not connect to external service: {req_err}"
            }

        if response.status_code == 200:
            data = response.json()
            item_data = data.get("items", [])[0] if data.get("items") else {}
            # Map API columns to Customer fields
            field_mapping = {
                "custom_store_name": item_data.get("sbsname"),              # Store Name
                "customer_name": item_data.get("sbsname_shr"),     # First Name / Last Name
                "custom_phone_number": item_data.get("phone"),          # Phone Number
                "custom_cell_phone": item_data.get("mobile"),           # Cell Phone
            }
            if company == "Cotton Valley":
                field_mapping["price_list_for_cv"] = fetch_price_list_name(item_data.get("rgnid"), item_data.get("rgnname"))  # Price List for CV (Name)
                field_mapping["sales_person"] = fetch_sales_rep(item_data.get("sprid"), item_data.get("sprname"))        # Sales Representative (Name)
                field_mapping["mode_of_payment"] = fetch_mode_of_payment(item_data.get("paytermid"), item_data.get("paytermdsc"))      # Mode of Payment
                field_mapping["account_number"] = item_data.get("sbsname_lcl")  # Account Number
            elif company == "UDC":
                field_mapping["price_list_for_udc"] = fetch_price_list_name(item_data.get("rgnid"), item_data.get("rgnname"))  # Price List for UDC (Name)
                field_mapping["udc_sales_person"] = fetch_sales_rep(item_data.get("sprid"), item_data.get("sprname"))        # Sales Representative (Name)
                field_mapping["udc_mode_of_payment"] = fetch_mode_of_payment(item_data.get("paytermid"), item_data.get("paytermdsc"))      # Mode of Payment
                field_mapping["udc_account_number"] = item_data.get("sbsname_lcl")  # Account Number UDC

            # Set values on customer doc
            for field, value in field_mapping.items():
                if hasattr(customer, field):
                    setattr(customer, field, value)
            customer.save(ignore_permissions=True)
            # Sync addresses from dlvdadr array
            if "dlvdadr" in item_data:
                sync_customer_addresses(customer_id, item_data.get("dlvdadr", []), company)

            return {"status": "success", "message": "Customer data fetched and updated successfully"}
        else:
            frappe.log_error(f"Failed to fetch data. Status code: {response.status_code}\nResponse: {response.text}", "Fetch Customer Data Error")
            return {"status": "error", "message": f"Failed to fetch data. Status code: {response.status_code}"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Fetch Customer Data Error")
        return {"status": "error", "message": str(e)}


def sync_customer_addresses(customer_id, addresses_data, company="Cotton Valley"):
    """
    Sync customer addresses from API response.
    Updates existing addresses or creates new ones based on rowid/udc_address_id.
    
    Args:
        customer_id: Customer ID
        addresses_data: List of address dictionaries from API
    """
    try:
        for addr_data in addresses_data:
            rowid = str(addr_data.get("rowid", ""))
            if not rowid:
                continue
            # Map API fields to Address doctype fields
            address_type = addr_data.get("rectyp", "Shipping")
            # Normalize address type
            if "billing" in address_type.lower():
                address_type = "Billing"
            elif "shipping" in address_type.lower() or "multi" in address_type.lower():
                address_type = "Shipping"
            else:
                address_type = "Shipping"
            # Check if address with this udc_address_id already exists for this customer
            existing_address = None
            if company == "Cotton Valley":
                existing_address = frappe.db.sql("""
                    SELECT a.name 
                    FROM `tabAddress` a
                    INNER JOIN `tabDynamic Link` dl ON dl.parent = a.name
                    WHERE a.cv_address_id = %s 
                    AND dl.link_doctype = 'Customer' 
                    AND dl.link_name = %s
                    AND dl.parenttype = 'Address'
                    LIMIT 1
                """, (rowid, customer_id), as_dict=True)
            elif company == "UDC":
                existing_address = frappe.db.sql("""
                    SELECT a.name 
                    FROM `tabAddress` a
                    INNER JOIN `tabDynamic Link` dl ON dl.parent = a.name
                    WHERE a.udc_address_id = %s 
                    AND dl.link_doctype = 'Customer' 
                    AND dl.link_name = %s
                    AND dl.parenttype = 'Address'
                    LIMIT 1
                """, (rowid, customer_id), as_dict=True)
            try:
                if existing_address:
                    # Update existing address
                    address_doc = frappe.get_doc("Address", existing_address[0].name)
                    update_address_fields(address_doc, addr_data, address_type)
                    address_doc.save(ignore_permissions=True)
                    frappe.logger().info(f"Updated address {address_doc.name} for customer {customer_id}")
                else:
                    # Create new address
                    create_new_address(customer_id, addr_data, address_type, rowid, company)
            except Exception as addr_e:
                frappe.log_error(frappe.get_traceback(), f"Sync Address Error for customer {customer_id} rowid {rowid}")
        frappe.db.commit()
        return {"status": "success", "message": "Addresses synced successfully"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Sync Customer Addresses Error")
        return {"status": "error", "message": str(e)}


def fetch_sales_rep(sprid, sprname, company="Cotton Valley"):
    """
    Fetch sales representative based on ID and name.
    
    Args:
        sprid: Sales Representative ID from API
        sprname: Sales Representative Name from API
    Returns:
        str: Sales Representative name
    """
    existing_spr = None
    new_spr = None
    if company == "Cotton Valley":
        existing_spr = frappe.db.sql("""
            SELECT name FROM `tabSales Person`
            WHERE sales_person_id = %s
            LIMIT 1
        """, (sprid,), as_dict=True)
    elif company == "UDC":
        existing_spr = frappe.db.sql("""
            SELECT name FROM `tabSales Person`
            WHERE udc_sales_person_id = %s
            LIMIT 1
        """, (sprid,), as_dict=True)

    if not existing_spr:
        # Create new Sales Person if not exists
        sales_person_fields = {
            "doctype": "Sales Person",
            "sales_person_name": sprname,
        }
        if company == "Cotton Valley":
            sales_person_fields["sales_person_id"] = sprid
        elif company == "UDC":
            sales_person_fields["udc_sales_person_id"] = sprid

        new_spr = frappe.get_doc(sales_person_fields)
        new_spr.insert(ignore_permissions=True)

    return existing_spr[0].name if existing_spr else new_spr.name

def fetch_mode_of_payment(paytermid, paytermdsc, company="Cotton Valley"):
    """
    Fetch mode of payment based on payment term ID and description.
    
    Args:
        paytermid: Payment Term ID from API
        paytermdsc: Payment Term Description from API
    Returns:
        str: Mode of Payment
    """
    existing_mop = None
    new_mop = None
    if company == "Cotton Valley":
        existing_mop = frappe.db.sql("""
            SELECT name FROM `tabMode of Payment`
            WHERE mode_id = %s
            LIMIT 1
        """, (paytermid,), as_dict=True)
    elif company == "UDC":
        existing_mop = frappe.db.sql("""
            SELECT name FROM `tabMode of Payment`
            WHERE udc_mode_id = %s
            LIMIT 1
        """, (paytermid,), as_dict=True)

    if not existing_mop:
        # Create new Mode of Payment if not exists
        mop_fields = {
            "doctype": "Mode of Payment",
            "mode_of_payment": paytermdsc,
        }
        if company == "Cotton Valley":
            mop_fields["mode_id"] = paytermid
        elif company == "UDC":
            mop_fields["udc_mode_id"] = paytermid

        new_mop = frappe.get_doc(mop_fields)
        new_mop.insert(ignore_permissions=True)

    return existing_mop[0].name if existing_mop else new_mop.name


def fetch_price_list_name(rgnid, rgnname, company="Cotton Valley"):
    """
    Fetch price list name based on region ID and name.
    
    Args:
        rgnid: Region ID from API
        rgnname: Region Name from API
    Returns:
        str: Price List name
    """
    existing_pl = None
    new_pl = None
    if company == "Cotton Valley":
        existing_pl = frappe.db.sql("""
            SELECT name FROM `tabPrice List`
            WHERE price_id = %s
            LIMIT 1
        """, (rgnid,), as_dict=True)
    elif company == "UDC":
        existing_pl = frappe.db.sql("""
            SELECT name FROM `tabPrice List`
            WHERE udc_price_id = %s
            LIMIT 1
        """, (rgnid,), as_dict=True)

    if not existing_pl:
        # Create new Price List if not exists
        pl_fields = {
            "doctype": "Price List",
            "price_list_name": rgnname,
            "selling": 1,
            "buying": 1
        }
        if company == "Cotton Valley":
            pl_fields["price_id"] = rgnid
        elif company == "UDC":
            pl_fields["udc_price_id"] = rgnid

        new_pl = frappe.get_doc(pl_fields)
        new_pl.insert(ignore_permissions=True)
    

    return existing_pl[0].name if existing_pl else new_pl.name


def update_address_fields(address_doc, addr_data, address_type):
    """
    Update address document fields from API data.
    
    Args:
        address_doc: Address document object
        addr_data: Address data from API
        address_type: Type of address (Billing/Shipping)
    """
    # Map API columns to Address fields
    address_doc.address_type = address_type  # rectyp (Billing/Shipping) handled in caller
    address_doc.address_line1 = addr_data.get("adr", "").strip()  # Address Details
    address_doc.city = addr_data.get("ctyname", "").strip() or "Unknown"  # City (default if missing)
    address_doc.pincode = addr_data.get("postcd", "").strip()       # Zip Code
    address_doc.state = addr_data.get("prvname", "").strip()        # State (Name)
    address_doc.country = addr_data.get("cntname", "").strip() or "UNITED STATES"  # Country
    address_doc.phone = addr_data.get("phone", "").strip()          # Phone Number
    # address_doc.custom_state_code = addr_data.get("prvid", "").strip()  # State (ID)


def create_new_address(customer_id, addr_data, address_type, rowid, company="Cotton Valley"):
    """
    Create a new address document linked to customer.
    
    Args:
        customer_id: Customer ID
        addr_data: Address data from API
        address_type: Type of address (Billing/Shipping)
        rowid: UDC address ID from API
    """
    customer = frappe.get_doc("Customer", customer_id)
    
    # Create address title
    address_title = f"{customer.customer_name}"
    
    new_address = frappe.get_doc({
        "doctype": "Address",
        "address_title": address_title,
        "address_type": address_type,
        "address_line1": addr_data.get("adr", "").strip(),
        "city": addr_data.get("ctyname", "").strip() or "Unknown",
        "pincode": addr_data.get("postcd", "").strip(),
        "state": addr_data.get("prvname", "").strip(),
        "country": addr_data.get("cntname", "").strip() or "UNITED STATES",
        "company": company,
        "phone": addr_data.get("phone", "").strip(),
        "links": [
            {
                "link_doctype": "Customer",
                "link_name": customer_id
            }
        ]
    })
    if company == "Cotton Valley":
        new_address.cv_address_id = rowid
    elif company == "UDC":
        new_address.udc_address_id = rowid
    
    # Add state code if needed
    if addr_data.get("prvid"):
        new_address.custom_state_code = addr_data.get("prvid", "").strip()
    
    new_address.insert(ignore_permissions=True)
    frappe.logger().info(f"Created new address {new_address.name} for customer {customer_id}")
    
    return new_address.name

