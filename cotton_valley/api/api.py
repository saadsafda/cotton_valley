import json
import frappe # type: ignore
from frappe import _ # type: ignore

@frappe.whitelist(allow_guest=True)
def get_country_list():
    return frappe.get_all("Country", fields=["name as id", "country_name as name"])

@frappe.whitelist(allow_guest=True)
def register_customer(data, ip_address=None, lat_long=None, company=None):
    try:
        company = "Cotton Valley" if not company or company == "null" else company
        lat_long = lat_long if lat_long and lat_long != "null" else None
        ip_address = ip_address if ip_address and ip_address != "null" else None
        # Ensure incoming data is a dict (from JSON string)
        if isinstance(data, str):
            data = json.loads(data)

        if frappe.db.exists("Customer", {"custom_email_address": data.get("email")}):
            frappe.local.response["http_status_code"] = 409
            frappe.local.response["message"] = f"{data.get('email')} email is already exist in our company."
            frappe.local.response["status"] = "error"
            return


        # Create Customer
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": data.get("first_name"),
            "custom_last_name": data.get("last_name"),
            "custom_email_address": data.get("email"),
            "custom_cell_phone": data.get("cell_phone"),
            "custom_phone_number": f"{data.get('country_code')}{data.get('phone')}",
            "custom_password": data.get("password"),
            "custom_confirm_password": data.get("password_confirmation"),
            "custom_company_name": data.get("company_name"),
            "custom_store_name": data.get("store_name"),
            "custom_storewarehouse_area_sqft": data.get("square_footage"),
            "tax_id": data.get("federal_tax_id"),
            "website": data.get("website"),
            "custom_manager_name": data.get("manager_name"),
            "custom_manager_number": data.get("manager_number"),
            "custom_how_long_have_you_been_in_years": data.get("years_in_business"),
            "customer_type": "Individual",
            "custom_type_of_buiness": data.get("business_type"),
            "custom_how_did_you_hear_about_us": data.get("hear_about_us"),
            "custom_bank_name": data.get("bank_name"),
            "custom_bank_address": data.get("bank_address"),
            "custom_bank_phone": data.get("bank_phone"),
            "custom_bank_fax": data.get("bank_fax"),
            "custom_bank_account_number": data.get("account_number"),
            "custom_bank_city": data.get("bank_city"),
            "custom_bank_state": data.get("bank_state"),
            "custom_bank_zip_code": data.get("bank_zip_code"),
            "custom_bank_account_type": data.get("account_type"),
            "custom_bank_email": data.get("bank_email"),
            "register_company": company,
            "default_currency": "USD",
            "disabled": 1,  # Customer will be enabled after verification
            "custom_ip_address": ip_address,
            "custom_lat__long": lat_long,
            "no_of_login": "0",
            "no_of_orders": "0",
            "orders_amount": "0.00",
        })

        # References
        if isinstance(data.get("references"), list):
            customer.custom_business_refereances = []
            for ref in data.get("references"):
                customer.append("custom_business_refereances", {
                    "company_name": ref.get("company_name"),
                    "address": ref.get("address"),
                    "city": ref.get("city"),
                    "state": ref.get("state"),
                    "zip": ref.get("zip"),
                    "phone": ref.get("phone"),
                    "fax": ref.get("fax"),
                    "email": ref.get("email"),
                })

        customer.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Send welcome email to the registered customer
        # send_registration_email(customer, company)
        
        # Addresses
        make_customer_address(customer.name, data.get("shipping_address"), address_type="Shipping")
        if data.get("shipping_billing_same"):
            make_customer_address(customer.name, data.get("shipping_address"), address_type="Billing")

        if not data.get("shipping_billing_same") and data.get("billing_address"):
            make_customer_address(customer.name, data.get("billing_address"), address_type="Billing")

        frappe.db.commit()
        return {"status": "success", "message": "Customer registered successfully", "customer_id": customer.name}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Customer Registration Failed")
        return {"status": "error", "message": str(e)}


@frappe.whitelist(allow_guest=True)
def make_customer_address(customer_id, address_data, address_type="Shipping"):
    try:
        address = frappe.get_doc({
            "doctype": "Address",
            "address_title": f"{customer_id}-{address_type}",
            "address_type": address_type,
            "address_line1": address_data.get("address_line1"),
            "address_line2": address_data.get("address_line2"),
            "city": address_data.get("city"),
            "state": address_data.get("state"),
            "pincode": address_data.get("zip"),
            "country": address_data.get("country"),
            "phone": address_data.get("phone"),
            "email_id": address_data.get("email"),
        })

        address.append("links", {
            "link_doctype": "Customer",
            "link_name": customer_id
        })
        address.insert(ignore_permissions=True)
        if address_type == "Shipping":
            frappe.db.set_value("Customer", customer_id, "customer_primary_address", address.name)

        if address_type == "Billing":
            frappe.db.set_value("Customer", customer_id, "customer_billing_address", address.name)
        frappe.db.commit()

        return {"status": "success", "message": "Customer address created successfully", "address_id": address.name}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Customer Address Creation Failed")
        return {"status": "error", "message": str(e)}

# Register Email For Customer
@frappe.whitelist(allow_guest=True)
def send_registration_email(customer_email, sales_person, firstname, lastname, company):
    """
    Send welcome email to newly registered customer
    Uses Email Template from ERPNext for easy content management
    """
    try:
        if not customer_email:
            frappe.log_error("No email address found for customer", "Registration Email Failed")
            return
        sales_person_email = ""
        if sales_person:
            sales_person_employee = frappe.db.get_value("Sales Person", sales_person, "employee")
            if sales_person_employee:
                sales_person_email = frappe.db.get_value("Employee", sales_person_employee, "user_id")
        
        # Try to get Email Template from ERPNext
        template_name = ""
        if company == "Cotton Valley":
            template_name = "New Registration Message_CVL"
        else:
            template_name = "New Registration Message_UDC"
        email_subject = f"Welcome to {company}!"
        email_message = ""
        
        cc_emails = []
        if frappe.db.exists("Email Template", template_name):
            email_template = frappe.get_doc("Email Template", template_name)
            email_subject = email_template.subject
            
            # Get CC emails from child table
            if email_template.custom_cc_email:
                cc_emails = [row.email for row in email_template.custom_cc_email if row.email]
            
            # Render template with customer data
            context = {
                "firstname": firstname,
                "lastname": lastname,
                "email": customer_email
            }
            response = email_template.response_html if email_template.use_html else email_template.response
            email_message = frappe.render_template(response, context)
        else:
            # Fallback message if template doesn't exist
            email_message = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #333;">Welcome to {company}!</h2>
                    <p>Dear {firstname} {lastname},</p>
                    
                    <p>Thank you for registering with us! We're excited to have you as part of our community.</p>
                    
                    <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #555;">Your Registration Details:</h3>
                        <p><strong>Customer ID:</strong> {firstname}</p>
                        <p><strong>Email:</strong> {customer_email}</p>
                    </div>
                    
                    <p><strong>Note:</strong> Your account is currently pending approval. Our team will review your registration and activate your account shortly. You will receive another email once your account is activated.</p>
                    
                    <p>If you have any questions, please don't hesitate to contact us.</p>
                    
                </div>
            """
        
        # Send the email with CC
        frappe.sendmail(
            recipients=[customer_email, sales_person_email] if sales_person_email else [customer_email],
            cc=cc_emails if cc_emails else None,
            subject=email_subject,
            message=email_message,
            now=True  # Send immediately
        )
        
        frappe.log_error(f"Registration email sent to {customer_email}", "Customer Registration Email")
        
    except Exception as e:
        # Don't fail registration if email fails
        frappe.log_error(f"Failed to send registration email: {str(e)}\n{frappe.get_traceback()}", "Registration Email Failed")



