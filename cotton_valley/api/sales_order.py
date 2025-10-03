import datetime
import frappe # type: ignore
from frappe.utils import nowdate # type: ignore
from cotton_valley.api.customer import get_current_customer
from cotton_valley.api.products import get_product
from cotton_valley.api.website_theme_setting import get_file

@frappe.whitelist(allow_guest=True)
def get_submited_orders(company="Cotton Valley", page=None):
    company = "Cotton Valley" if not company or company == "null" else company
    page = None if not page or page == "null" else int(page)
    # --- Pagination ---
    limit_start = (page - 1) * 10 if page and page > 0 else None
    limit_page_length = 10 if page else None
    customer = get_current_customer()
    if not customer or not customer.get("id"):
        return {"data": [], "total": 0, "from": 0, "to": 0, "current_page": 0, "per_page": 0}

    customer_id = customer["id"]
    total_count = frappe.db.count("Sales Order", filters={"customer": customer_id, "company": company, "docstatus": 1})

    orders = frappe.get_all(
        "Sales Order",
        filters={"customer": customer_id, "company": company, "docstatus": 1},
        fields=["name as order_number", "grand_total as total", "status as payment_status", "creation as created_at", "custom_mode_of_payment as payment_method", "product_type as order_type"],
        order_by="creation desc",
        limit_start=limit_start,
        limit_page_length=limit_page_length
    )
    # Format creation into 12-hour time with AM/PM
    for o in orders:
        o["created_at"] = datetime.strftime(o["created_at"], "%d/%m/%Y %I:%M %p")
    from_showing = limit_start + 1 if limit_start is not None else 1
    to_showing = limit_start + limit_page_length if limit_start is not None else total_count

    return {"data": orders, "total": total_count, "from": from_showing, "to": to_showing, "current_page": page or 1, "per_page": limit_page_length or total_count}


@frappe.whitelist(allow_guest=True)
def get_order_details(order_number):
    customer = get_current_customer()
    if not customer or not customer.get("id"):
        return None

    customer_id = customer["id"]
    so = frappe.get_all(
        "Sales Order",
        filters={"name": order_number, "customer": customer_id, "docstatus": 1},
        fields=["name"],
        limit=1,
    )
    if not so:
        return None

    so_doc = frappe.get_doc("Sales Order", so[0].name)
    items = []
    for item in so_doc.items:
        items.append({
            "id": item.item_code,
            "name": item.item_name,
            "sku": item.item_code,
            "product_thumbnail": get_file(item.image),
            "product_id": item.item_code,
            "quantity": item.qty,
            "sub_total": item.amount,
            "price": item.rate,
        })
    return {
        "order_number": so_doc.name,
        "amount": so_doc.total,
        "total": so_doc.grand_total,
        "payment_status": so_doc.status,
        "created_at": so_doc.transaction_date,
        "payment_method": so_doc.custom_mode_of_payment,
        "billing_address_id": so_doc.customer_address,
        "shipping_address_id": so_doc.shipping_address_name,
        "delivery_description": so_doc.custom_shipping_method,
        "products": items,
        "order_status": {
            "status": so_doc.status,
            "sequence": 2 if so_doc.status == "To Deliver and Bill" else 4 if so_doc.status == "Completed" else 3 if so_doc.status == "Cancelled" else 1,
        }
    }


@frappe.whitelist(allow_guest=True)
def get_cart(company="Cotton Valley"):
    company = "Cotton Valley" if not company or company == "null" else company
    customer = get_current_customer()
    if not customer or not customer.get("id"):
        return {"items": [], "total": 0.0, "count": 0}

    customer_id = customer["id"]
    so = frappe.get_all(
        "Sales Order",
        filters={"customer": customer_id, "docstatus": 0, "company": company},
        fields=["name", "grand_total"],
        limit=1,
    )
    if not so:
        return {"items": [], "total": 0.0, "discount": 0.0, "count": 0}

    so_doc = frappe.get_doc("Sales Order", so[0].name)
    items = []
    for item in so_doc.items:
        product = get_product(item.item_code)
        items.append({
            "id": item.name,
            "product_id": item.item_code,
            "quantity": item.qty,
            "sub_total": item.amount,
            "product": product,
        })
    return {
        "items": items,
        "total": so_doc.grand_total,
        "discount": so_doc.discount_amount,
        "count": len(items),
    }


@frappe.whitelist(allow_guest=True)
def create_or_update_sales_order(items, company="Cotton Valley", submit=False, billing_address_id=None, shipping_address_id=None, delivery_description=None, payment_method=None):
    customer = get_current_customer()
    """
    Create or update a Sales Order from cart.
    items = [
      {"item_code": "ITEM-001", "qty": 2, "rate": 500},
      {"item_code": "ITEM-002", "qty": 1, "rate": 300},
    ]
    """
    items = frappe.parse_json(items)
    company = "Cotton Valley" if not company or company == "null" else company
    billing_address_id = None if not billing_address_id or billing_address_id == "null" else billing_address_id
    shipping_address_id = None if not shipping_address_id or shipping_address_id == "null" else shipping_address_id
    delivery_description = None if not delivery_description or delivery_description == "null" else delivery_description
    payment_method = None if not payment_method or payment_method == "null" else payment_method

    if not customer:
        return "Customer not found"

    customer_id = customer["id"]

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
            so_doc.company = company
            so_doc.product_type = so_type

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

    so_doc.delivery_date = nowdate()
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



@frappe.whitelist(allow_guest=True)
def apply_coupon(code, company="Cotton Valley"):
    company = "Cotton Valley" if not company or company == "null" else company
    if not code or code == "null":
        return {"success": False, "message": "Coupon code is required."}

    customer = get_current_customer()
    if not customer or not customer.get("id"):
        return {"success": False, "message": "Customer not found."}

    customer_id = customer["id"]
    so = frappe.get_all(
        "Sales Order",
        filters={"customer": customer_id, "docstatus": 0, "company": company},
        fields=["name"],
        limit=1,
    )
    if not so:
        return {"success": False, "message": "Sales Order not found."}

    so_doc = frappe.get_doc("Sales Order", so[0].name)
    coupon = frappe.get_all(
        "Coupon Code",
        filters={"coupon_code": code, "valid_from": ("<=", nowdate()), "valid_upto": (">=", nowdate())},
        fields=["name", "max_order_amount", "min_order_amount"],
        limit=1,
    )
    if not coupon:
        return {"success": False, "message": "Invalid or expired coupon code."}

    coupon_doc = frappe.get_doc("Coupon Code", coupon[0].name)
    if so_doc.grand_total < coupon_doc.min_order_amount:
        return {"success": False, "message": f"Minimum purchase amount for this coupon is {coupon_doc.min_order_amount}."}

    if coupon_doc.max_order_amount and so_doc.grand_total > coupon_doc.max_order_amount:
        return {"success": False, "message": f"Maximum purchase amount for this coupon is {coupon_doc.max_order_amount}."}

    so_doc.coupon_code = coupon_doc.name
    so_doc.delivery_date = nowdate()
    so_doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True, "message": f"Coupon applied successfully. You saved {so_doc.discount_amount}!", "discount_amount": so_doc.discount_amount, "new_total": so_doc.grand_total}

