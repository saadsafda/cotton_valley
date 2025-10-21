import frappe
from cotton_valley.api.website_theme_setting import get_file

@frappe.whitelist()
def get_all_customers():
    """Fetch all customers from the database."""
    try:
        customers = frappe.get_list("Customer",
            fields=["name", "customer_name", "custom_email_address", "custom_phone_number", "image", "disabled",
                    "mode_of_payment", "sales_person", "custom_company_name", "creation", "modified",
                    "customer_primary_address", "customer_billing_address", "price_list_for_cv", "price_list_for_udc"]
        )
        
        if not customers:
            return {
                "status": "success",
                "message": "No customers found",
                "data": []
            }
        customer_list = []
        for customer in customers:
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
                "price_list_for_cv": customer.price_list_for_cv,
                "price_list_for_udc": customer.price_list_for_udc,
                "created_at": customer.creation,
                "updated_at": customer.modified,
            }
            # --- Addresses ---
            links = frappe.get_all("Dynamic Link",
                filters={"link_doctype": "Customer", "link_name": customer.name},
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
                    "country": addr_doc.country,
                    "state": addr_doc.state,
                })
            customer_data["address"] = addresses

            # --- Profile Image ---
            customer_data["profile_image"] = get_file(customer.image)

            customer_list.append(customer_data)

        return {
            "status": "success",
            "message": "Customers fetched successfully",
            "data": customer_list,
            "count": len(customer_list)
        }
        
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "status": "error",
            "message": "Customer doctype does not exist"
        }
    except frappe.PermissionError:
        frappe.local.response["http_status_code"] = 403
        return {
            "status": "error",
            "message": "You do not have permission to access customers"
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get All Customers Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "status": "error",
            "message": "An error occurred while fetching customers",
            "error": str(e)
        }

