import frappe, secrets # type: ignore
from frappe.auth import LoginManager # type: ignore
from frappe.exceptions import AuthenticationError # type: ignore
from cotton_valley.api.website_theme_setting import get_file
from cotton_valley.api.common import get_customer_from_token
from frappe.utils.data import add_days, now_datetime



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
def forgot_password(email, company="Cotton Valley"):
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
            "mode_of_payment": customer.mode_of_payment,
            "company": customer.custom_company_name,
            "created_at": customer.creation,
            "updated_at": customer.modified,
        }

        if customer.sales_person:
            sales_rep = frappe.get_doc("Sales Person", customer.sales_person)
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





