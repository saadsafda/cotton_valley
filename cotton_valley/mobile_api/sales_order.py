import frappe
from frappe.utils import nowdate # type: ignore


@frappe.whitelist()
def get_sales_person_orders(filters=None, limit_page_length=20, limit_start=0):
    """
    Get all sales orders for the current logged-in sales person.
    
    Args:
        filters: Optional JSON string with filters like {"docstatus": 1, "company": "Cotton Valley"}
        limit_page_length: Number of records per page (default: 20)
        limit_start: Starting record offset (default: 0)
        
    Returns:
        dict: Sales orders with customer details and statistics
    """
    try:
        limit_page_length = int(limit_page_length)
        limit_start = int(limit_start)
        # Get current user
        current_user = frappe.session.user
        
        if not current_user or current_user == "Guest":
            return {
                "status": "error",
                "message": "Authentication required"
            }
        
        # Get employee for current user
        employee = frappe.db.get_value(
            "Employee",
            {"user_id": current_user, "status": "Active"},
            "name"
        )
        
        if not employee:
            return {
                "status": "error",
                "message": "Current user is not an active employee"
            }
        
        # Get sales person linked to this employee
        sales_person = frappe.db.get_value(
            "Sales Person",
            {"employee": employee, "enabled": 1},
            "name"
        )
        
        if not sales_person:
            return {
                "status": "error",
                "message": "Employee is not a sales person"
            }
        
        # Parse filters if provided
        additional_filters = {}
        if filters:
            additional_filters = frappe.parse_json(filters) if isinstance(filters, str) else filters
        
        # Build filters for sales orders
        base_filters = {
            "custom_customer_sales_representative": sales_person
        }
        base_filters.update(additional_filters)
        
        # Get sales orders
        sales_orders = frappe.get_all(
            "Sales Order",
            filters=base_filters,
            fields=[
                "name", "customer", "customer_name", "transaction_date", 
                "delivery_date", "status", "docstatus", "grand_total", "currency",
                "company", "custom_mode_of_payment", "custom_notes",
                "custom_customer_sales_representative as sales_representative", "from_app", "order_type",
                "creation", "modified", "owner"
            ],
            order_by="creation desc",
            limit_page_length=limit_page_length,
            limit_start=limit_start
        )
        
        # Enrich with customer details
        for order in sales_orders:
            # Get customer details
            customer_details = frappe.db.get_value(
                "Customer",
                order.customer,
                ["custom_email_address", "custom_phone_number", "custom_company_name", "image"],
                as_dict=True
            )
            
            if customer_details:
                order["customer_email"] = customer_details.get("custom_email_address")
                order["customer_phone"] = customer_details.get("custom_phone_number")
                order["customer_company"] = customer_details.get("custom_company_name")
                order["customer_image"] = customer_details.get("image")
            
            # Get items for this sales order
            items = frappe.get_all(
                "Sales Order Item",
                filters={"parent": order.name},
                fields=[
                    "name", "item_code", "item_name", "description",
                    "qty", "rate", "amount", "uom", "warehouse",
                    "delivery_date", "idx", "custom_case_pack as case_pack"
                ],
                order_by="idx asc"
            )
            
            # Enrich items with product details
            for item in items:
                # Get item image and additional details
                item_details = frappe.db.get_value(
                    "Item",
                    item.item_code,
                    ["image", "stock_uom", "item_group", "brand"],
                    as_dict=True
                )
                if item_details:
                    item["image"] = item_details.get("image")
                    item["item_group"] = item_details.get("item_group")
                    item["brand"] = item_details.get("brand")
            
            order["items"] = items
            order["item_count"] = len(items)
            
            # Format status
            if order.docstatus == 0:
                order["status_label"] = "Draft"
            elif order.docstatus == 1:
                order["status_label"] = order.status
            elif order.docstatus == 2:
                order["status_label"] = "Cancelled"
        
        # Get total count for pagination
        total_count = frappe.db.count("Sales Order", base_filters)
        
        # Get summary statistics
        stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_orders,
                SUM(CASE WHEN docstatus = 0 THEN 1 ELSE 0 END) as draft_orders,
                SUM(CASE WHEN docstatus = 1 THEN 1 ELSE 0 END) as submitted_orders,
                SUM(CASE WHEN docstatus = 2 THEN 1 ELSE 0 END) as cancelled_orders,
                SUM(CASE WHEN docstatus = 1 THEN grand_total ELSE 0 END) as total_value
            FROM `tabSales Order`
            WHERE custom_customer_sales_representative = %s
        """, (sales_person,), as_dict=True)
        
        return {
            "status": "success",
            "sales_person": sales_person,
            "data": sales_orders,
            "pagination": {
                "total_count": total_count,
                "limit_start": limit_start,
                "limit_page_length": limit_page_length,
                "has_more": (limit_start + limit_page_length) < total_count
            },
            "statistics": stats[0] if stats else {}
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Sales Person Orders Failed")
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist()
def create_or_update_sales_order(items, customer, notes="", submit_datetime=nowdate(), company="Cotton Valley", submit=False, billing_address_id=None, shipping_address_id=None, delivery_description=None, payment_method=None, client_ip=None, client_latitude=None, client_longitude=None):
    """
    Create or update a Sales Order from cart.
    items = [
      {"item_code": "ITEM-001", "qty": 2, "rate": 500},
      {"item_code": "ITEM-002", "qty": 1, "rate": 300},
    ]
    """
    items = frappe.parse_json(items)

    customer = None if not customer or customer == "null" else customer
    company = "Cotton Valley" if not company or company == "null" else company
    billing_address_id = None if not billing_address_id or billing_address_id == "null" else billing_address_id
    shipping_address_id = None if not shipping_address_id or shipping_address_id == "null" else shipping_address_id
    delivery_description = None if not delivery_description or delivery_description == "null" else delivery_description
    payment_method = None if not payment_method or payment_method == "null" else payment_method
    client_ip = None if not client_ip or client_ip == "null" else client_ip
    client_latitude = None if not client_latitude or client_latitude == "null" else client_latitude
    client_longitude = None if not client_longitude or client_longitude == "null" else client_longitude

    if not customer:
        return "Customer not found"

    customer_id = customer

    if submit and company != "Cotton Valley":
        so = frappe.get_all(
            "Sales Order",
            filters={"customer": customer_id, "docstatus": 0, "company": company},
            fields=["name"],
            limit=1,
        )

        if so:
            draft_doc = frappe.get_doc("Sales Order", so[0].name)
            # delete draft cart after extracting items
            frappe.delete_doc("Sales Order", draft_doc.name, ignore_permissions=True)
            frappe.db.commit()
        
        regular_items = [i for i in items if i.get("product_type") == "Regular"]
        cod_items = [i for i in items if i.get("product_type") == "COD"]

        created_orders = []

        def make_so(item_list, so_type):
            if not item_list:
                return None
            so_doc = frappe.new_doc("Sales Order")
            so_doc.customer = customer_id
            so_doc.order_type = "Shopping Cart"
            so_doc.delivery_date = nowdate()
            so_doc.submit_datetime = submit_datetime
            so_doc.company = company
            so_doc.custom_notes = notes
            so_doc.product_type = so_type
            so_doc.from_app = True
            if client_ip:
                so_doc.customer_ip = client_ip
            if client_latitude and client_longitude:
                so_doc.customer_lat__long = f"{client_latitude}, {client_longitude}"

            if billing_address_id:
                so_doc.customer_address = billing_address_id
            if shipping_address_id:
                so_doc.shipping_address_name = shipping_address_id
            if delivery_description:
                so_doc.custom_shipping_method = delivery_description
            if payment_method:
                so_doc.custom_mode_of_payment = payment_method

            for row in item_list:
                so_doc.append("items", {
                    "item_code": row["item_code"],
                    "qty": row["qty"],
                    "rate": row["rate"],
                    "delivery_date": nowdate(),
                })

            so_doc.save(ignore_permissions=True)
            so_doc.submit()
            frappe.db.commit()

            created_orders.append({"type": so_type, "name": so_doc.name})
            return so_doc.name

        if len(regular_items) > 0:
            make_so(regular_items, "Regular")
        if len(cod_items) > 0:
            make_so(cod_items, "COD")

        return created_orders


    so = frappe.get_all(
        "Sales Order",
        filters={"customer": customer_id, "docstatus": 0, "company": company},
        fields=["name"],
        limit=1,
    )

    so_doc = {}
    if so:
        so_doc = frappe.get_doc("Sales Order", so[0].name)
        so_doc.items = []  # reset items
    else:
        so_doc = frappe.new_doc("Sales Order")
        so_doc.customer = customer_id
        so_doc.order_type = "Shopping Cart"
    
    so_doc.custom_notes = notes
    so_doc.from_app = True
    so_doc.delivery_date = nowdate()
    so_doc.submit_datetime = submit_datetime
    so_doc.company = company
    if items is None or len(items) == 0:
        so_doc.delete()
        frappe.db.commit()
        return None
    
    if billing_address_id:
        so_doc.customer_address = billing_address_id
    if shipping_address_id:
        so_doc.shipping_address_name = shipping_address_id
    if delivery_description:
        so_doc.custom_shipping_method = delivery_description
    if payment_method:
        so_doc.custom_mode_of_payment = payment_method

    if client_ip:
        so_doc.customer_ip = client_ip
    if client_latitude and client_longitude:
        so_doc.customer_lat__long = f"{client_latitude}, {client_longitude}"


    for row in items:
        so_doc.append("items", {
            "item_code": row["item_code"],
            "qty": row["qty"],
            "rate": row["rate"],
            "delivery_date": nowdate(),
        })
    so_doc.save(ignore_permissions=True)
    if submit:
        so_doc.submit()
    frappe.db.commit()
    return so_doc.name



@frappe.whitelist()
def get_panding_payments():
    try:
        panding_customer_amount = frappe.get_list(
            "Sales Order",
            filters={
                "docstatus": 1,
                "custom_clear": 0
            },
            fields=["name", "customer", "customer_name", "customer_account_number as account_number", "customer_company_name as company_name", "grand_total", "submit_datetime as date"],
            order_by="submit_datetime desc"
        )

        return {"status": "success", "data": panding_customer_amount}

    except Exception as e:
        frappe.log_error("Get Pending Payments Failed", frappe.get_traceback())
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}
