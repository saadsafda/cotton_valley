import frappe
from cotton_valley.api.website_theme_setting import get_file
from datetime import datetime, timedelta

@frappe.whitelist()
def get_all_customers():
    """Fetch all customers from the database."""
    try:
        customers = frappe.get_list("Customer",
            fields=["name", "customer_name", "custom_email_address", "custom_phone_number", "image", "disabled",
                    "mode_of_payment", "sales_person", "custom_company_name", "creation", "modified",
                    "customer_primary_address", "account_number", "customer_billing_address", "price_list_for_cv", "price_list_for_udc",
                    "no_of_orders", "orders_amount"]
        )

        new_opt_customers = frappe.get_all("Customer",
            filters={"customer_name": "New Opportunity"},
            fields=["name", "customer_name", "custom_email_address", "custom_phone_number", "image", "disabled",
                    "mode_of_payment", "sales_person", "custom_company_name", "creation", "modified",
                    "customer_primary_address", "account_number", "customer_billing_address", "price_list_for_cv", "price_list_for_udc",
                    "no_of_orders", "orders_amount"]
        )

        customers.extend(new_opt_customers)

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
            active_customer = False
            if last_order_date:
                active_customer = last_order_date.strftime('%Y-%m-%d') >= ninety_days_ago
            
            # --- Base Customer Info ---
            customer_data = {
                "id": customer.name,
                "name": customer.customer_name,
                "email": customer.custom_email_address,
                "country_code": customer.custom_phone_number[:1] if customer.custom_phone_number else None,
                "phone": customer.custom_phone_number,
                "profile_image_id": customer.image,
                "status": 1 if not customer.disabled else 0,
                "active_customer": active_customer,
                "mode_of_payment": customer.mode_of_payment,
                "company": customer.custom_company_name,
                "account_number": customer.account_number,
                "price_list_for_cv": customer.price_list_for_cv,
                "price_list_for_udc": customer.price_list_for_udc,
                "no_of_orders": customer.no_of_orders,
                "orders_amount": customer.orders_amount,
                "created_at": customer.creation,
                "updated_at": customer.modified,
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
                    "id": addr.name,
                    "title": addr.address_title,
                    "street": addr.address_line1,
                    "address_type": addr.address_type,
                    "city": addr.city,
                    "pincode": addr.pincode,
                    "is_default": is_default,
                    "country_code": customer_data["country_code"],
                    "phone": addr.phone,
                    "country": addr.country,
                    "state": addr.state,
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

