import frappe
from cotton_valley.api.website_theme_setting import get_file
from datetime import datetime, timedelta

@frappe.whitelist()
def get_all_customers():
    """Fetch all customers from the database."""
    try:
        current_user = frappe.session.user
        
        employee = frappe.db.get_value("Employee", {"user_id": current_user, "status": "Active"}, "name")
        sales_person = None
        
        if employee:
            sales_person = frappe.db.get_value("Sales Person", {"employee": employee, "enabled": 1}, "name")

        # Collect all Sales Person values the current user can access:
        # 1) Sales Person linked to their Employee
        # 2) Additional Sales Person entries from User Permission
        permitted_sales_persons = set()
        if sales_person:
            permitted_sales_persons.add(sales_person)

        user_permission_sales_persons = frappe.get_all(
            "User Permission",
            filters={"user": current_user, "allow": "Sales Person"},
            pluck="for_value"
        )
        permitted_sales_persons.update([sp for sp in user_permission_sales_persons if sp])

        if not permitted_sales_persons:
            return {
                "status": "success",
                "message": "No sales person linked or permitted for current user",
                "data": [],
                "count": 0
            }

        permitted_sales_persons = list(permitted_sales_persons)

        or_filters = {
            "sales_person": ["in", permitted_sales_persons],
            "udc_sales_person": ["in", permitted_sales_persons]
        }

        customers = frappe.get_list("Customer",
            or_filters=or_filters,
            page_length=0,
            fields=["name", "customer_name", "custom_email_address", "custom_phone_number", "image", "disabled",
                    "mode_of_payment", "sales_person", "udc_sales_person", "custom_company_name", "creation", "modified",
                    "customer_primary_address", "account_number", "udc_account_number", "customer_billing_address", "price_list_for_cv", "price_list_for_udc",
                    "no_of_orders", "orders_amount"]
        )

        new_opt_customers = frappe.get_all("Customer",
            filters={"customer_name": "New Opportunity"},
            page_length=0,
            fields=["name", "customer_name", "custom_email_address", "custom_phone_number", "image", "disabled",
                    "mode_of_payment", "sales_person", "udc_sales_person", "custom_company_name", "creation", "modified",
                    "customer_primary_address", "account_number", "udc_account_number", "customer_billing_address", "price_list_for_cv", "price_list_for_udc",
                    "no_of_orders", "orders_amount"]
        )

        customers.extend(new_opt_customers)
        # Keep unique customers by name to avoid duplicates (e.g. New Opportunity already matched above).
        customers = list({c.name: c for c in customers}.values())

        if not customers:
            return {
                "status": "success",
                "message": "No customers found",
                "data": [],
                "count": 0
            }
        
        # Calculate date 90 days ago
        ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        
        # Get all customer IDs for batch query
        customer_ids = [c.name for c in customers]
    
        # Batch query to check last order date for all customers
        last_orders = frappe.db.sql("""
            SELECT customer, MAX(transaction_date) as last_order_date
            FROM `tabSales Order`
            WHERE customer IN %s
            AND docstatus = 1
            GROUP BY customer
        """, (customer_ids,), as_dict=True)
        
        # Create a dictionary for quick lookup
        last_order_map = {order.customer: order.last_order_date for order in last_orders}
        
        # OPTIMIZATION: Batch fetch ALL addresses for ALL customers in ONE query (instead of N+M queries)
        all_addresses = frappe.db.sql("""
            SELECT 
                dl.link_name as customer,
                a.name,
                a.address_title,
                a.address_line1,
                a.address_type,
                a.city,
                a.pincode,
                a.phone,
                a.country,
                a.state
            FROM `tabDynamic Link` dl
            INNER JOIN `tabAddress` a ON a.name = dl.parent
            WHERE dl.link_doctype = 'Customer' 
                AND dl.link_name IN %s
                AND dl.parenttype = 'Address'
        """, (customer_ids,), as_dict=True)
        
        # Group addresses by customer
        addresses_by_customer = {}
        for addr in all_addresses:
            addresses_by_customer.setdefault(addr.customer, []).append(addr)
        
        customer_list = []
        for customer in customers:
            # Check if customer has ordered in last 90 days
            last_order_date = last_order_map.get(customer.name)
            active_customer = customer.disabled
            # if last_order_date:
            #     active_customer = last_order_date.strftime('%Y-%m-%d') >= ninety_days_ago
            
            # --- Base Customer Info ---
            customer_data = {
                "id": customer.name or '',
                "name": customer.customer_name or '',
                "email": customer.custom_email_address or '',
                "country_code": customer.custom_phone_number[:1] if customer.custom_phone_number else '',
                "phone": customer.custom_phone_number or '',
                "profile_image_id": customer.image or '',
                "status": customer.disabled,
                "sales_person": customer.sales_person or '',
                "udc_sales_person": customer.udc_sales_person or '',
                "active_customer": active_customer,
                "mode_of_payment": customer.mode_of_payment or '',
                "company": customer.custom_company_name or '',
                "account_number": customer.account_number or '',
                "udc_account_number": customer.udc_account_number or '',
                "price_list_for_cv": customer.price_list_for_cv or '',
                "price_list_for_udc": customer.price_list_for_udc or '',
                "no_of_orders": customer.no_of_orders or 0,
                "orders_amount": customer.orders_amount or 0.0,
                "last_order_date": last_order_date.strftime('%Y-%m-%d') if last_order_date else '',
                "created_at": customer.creation or '',
                "updated_at": customer.modified or '',
            }
            # --- Addresses (OPTIMIZED: Use pre-fetched data) ---
            addresses = []
            for addr in addresses_by_customer.get(customer.name, []):
                is_default = 0
                if addr.address_type == "Shipping" and addr.name == customer.customer_primary_address:
                    is_default = 1
                if addr.address_type == "Billing" and addr.name == customer.customer_billing_address:
                    is_default = 1

                addresses.append({
                    "id": addr.name or '',
                    "title": addr.address_title or '',
                    "street": addr.address_line1 or '',
                    "address_type": addr.address_type or '',
                    "city": addr.city or '',
                    "pincode": addr.pincode or '',
                    "is_default": is_default or 0,
                    "country_code": customer_data["country_code"] or '',
                    "phone": addr.phone or '',
                    "country": addr.country or '',
                    "state": addr.state or '',
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


@frappe.whitelist()
def create_customer_address(customer_id, address, address_type="Shipping", is_default=0, company=None):
    """
    Create an address for a specific customer.

    Args:
        customer_id (str): Customer document name.
        address (str|dict): Address payload (JSON string or dict).
        address_type (str): Shipping or Billing.
        is_default (int|str|bool): Mark as default for selected type.
        company (str): Optional company name.
    """
    try:
        customer_id = None if not customer_id or customer_id == "null" else customer_id
        company = "Cotton Valley" if not company or company == "null" else company
        address_type = "Shipping" if not address_type or address_type == "null" else address_type
        is_default = frappe.utils.cint(is_default)

        if not customer_id:
            return {
                "status": "error",
                "message": "Customer is required"
            }

        if not frappe.db.exists("Customer", customer_id):
            return {
                "status": "error",
                "message": "Customer not found"
            }

        address = frappe.parse_json(address) if isinstance(address, str) else address
        if not isinstance(address, dict):
            return {
                "status": "error",
                "message": "Invalid address payload"
            }

        address_type = address.get("address_type") or address_type
        if address_type not in ["Shipping", "Billing"]:
            return {
                "status": "error",
                "message": "address_type must be Shipping or Billing"
            }

        address_doc = frappe.get_doc({
            "doctype": "Address",
            "address_title": address.get("address_title") or f"{customer_id}-{address_type}",
            "address_type": address_type,
            "address_line1": address.get("address_line1") or address.get("street"),
            "address_line2": address.get("address_line2"),
            "city": address.get("city"),
            "state": address.get("state"),
            "pincode": address.get("pincode"),
            "country": address.get("country"),
            "phone": address.get("phone"),
            "email_id": address.get("email_id"),
            "company": company,
            "links": [{
                "link_doctype": "Customer",
                "link_name": customer_id
            }]
        })
        address_doc.insert(ignore_permissions=True)

        if is_default and address_type == "Shipping":
            frappe.db.set_value("Customer", customer_id, "customer_primary_address", address_doc.name)
        if is_default and address_type == "Billing":
            frappe.db.set_value("Customer", customer_id, "customer_billing_address", address_doc.name)

        frappe.db.commit()

        return {
            "status": "success",
            "message": "Customer address created successfully",
            "data": {
                "id": address_doc.name,
                "customer_id": customer_id,
                "title": address_doc.address_title or "",
                "address_type": address_doc.address_type or "",
                "street": address_doc.address_line1 or "",
                "city": address_doc.city or "",
                "pincode": address_doc.pincode or "",
                "phone": address_doc.phone or "",
                "country": address_doc.country or "",
                "state": address_doc.state or "",
                "is_default": is_default
            }
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error("Create Customer Address Mobile API Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist()
def edit_customer_address(customer_id, address_id, address, address_type=None, is_default=0, company=None):
    """
    Edit an existing address for a specific customer.

    Args:
        customer_id (str): Customer document name.
        address_id (str): Address document name.
        address (str|dict): Address payload (JSON string or dict).
        address_type (str): Shipping or Billing (optional override).
        is_default (int|str|bool): Mark as default for selected type.
        company (str): Optional company name.
    """
    try:
        customer_id = None if not customer_id or customer_id == "null" else customer_id
        address_id = None if not address_id or address_id == "null" else address_id
        company = "Cotton Valley" if not company or company == "null" else company
        address_type = None if not address_type or address_type == "null" else address_type
        is_default = frappe.utils.cint(is_default)

        if not customer_id:
            return {
                "status": "error",
                "message": "Customer is required"
            }

        if not address_id:
            return {
                "status": "error",
                "message": "Address is required"
            }

        if not frappe.db.exists("Customer", customer_id):
            return {
                "status": "error",
                "message": "Customer not found"
            }

        if not frappe.db.exists("Address", address_id):
            return {
                "status": "error",
                "message": "Address not found"
            }

        has_link = frappe.db.exists("Dynamic Link", {
            "parent": address_id,
            "parenttype": "Address",
            "link_doctype": "Customer",
            "link_name": customer_id
        })
        if not has_link:
            return {
                "status": "error",
                "message": "Address does not belong to this customer"
            }

        address = frappe.parse_json(address) if isinstance(address, str) else address
        if not isinstance(address, dict):
            return {
                "status": "error",
                "message": "Invalid address payload"
            }

        addr_doc = frappe.get_doc("Address", address_id)
        final_address_type = address.get("address_type") or address_type or addr_doc.address_type
        if final_address_type not in ["Shipping", "Billing"]:
            return {
                "status": "error",
                "message": "address_type must be Shipping or Billing"
            }

        addr_doc.address_title = address.get("address_title") or addr_doc.address_title or f"{customer_id}-{final_address_type}"
        addr_doc.address_type = final_address_type
        addr_doc.address_line1 = address.get("address_line1") or address.get("street") or addr_doc.address_line1
        addr_doc.address_line2 = address.get("address_line2") if "address_line2" in address else addr_doc.address_line2
        addr_doc.city = address.get("city") if "city" in address else addr_doc.city
        addr_doc.state = address.get("state") if "state" in address else addr_doc.state
        addr_doc.pincode = address.get("pincode") if "pincode" in address else addr_doc.pincode
        addr_doc.country = address.get("country") if "country" in address else addr_doc.country
        addr_doc.phone = address.get("phone") if "phone" in address else addr_doc.phone
        addr_doc.email_id = address.get("email_id") if "email_id" in address else addr_doc.email_id
        addr_doc.company = address.get("company") or company
        addr_doc.save(ignore_permissions=True)

        if is_default and final_address_type == "Shipping":
            frappe.db.set_value("Customer", customer_id, "customer_primary_address", addr_doc.name)
        if is_default and final_address_type == "Billing":
            frappe.db.set_value("Customer", customer_id, "customer_billing_address", addr_doc.name)

        frappe.db.commit()

        return {
            "status": "success",
            "message": "Customer address updated successfully",
            "data": {
                "id": addr_doc.name,
                "customer_id": customer_id,
                "title": addr_doc.address_title or "",
                "address_type": addr_doc.address_type or "",
                "street": addr_doc.address_line1 or "",
                "city": addr_doc.city or "",
                "pincode": addr_doc.pincode or "",
                "phone": addr_doc.phone or "",
                "country": addr_doc.country or "",
                "state": addr_doc.state or "",
                "is_default": is_default
            }
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error("Edit Customer Address Mobile API Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }
