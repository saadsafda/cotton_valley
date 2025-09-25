import frappe # type: ignore
from frappe.utils import nowdate # type: ignore
from cotton_valley.api.customer import get_current_customer
from cotton_valley.api.products import get_product


@frappe.whitelist(allow_guest=True)
def get_submited_orders(page=None):
    page = None if not page or page == "null" else int(page)
    # --- Pagination ---
    limit_start = (page - 1) * 10 if page and page > 0 else None
    limit_page_length = 10 if page else None
    customer = get_current_customer()
    if not customer or not customer.get("id"):
        return {"data": [], "total": 0, "from": 0, "to": 0, "current_page": 0, "per_page": 0}

    customer_id = customer["id"]
    total_count = frappe.db.count("Sales Order", filters={"customer": customer_id, "docstatus": 1})

    orders = frappe.get_all(
        "Sales Order",
        filters={"customer": customer_id, "docstatus": 1},
        fields=["name as order_number", "grand_total as total", "status as payment_status", "transaction_date as created_at", "custom_mode_of_payment as payment_method"],
        order_by="creation desc",
        limit_start=limit_start,
        limit_page_length=limit_page_length
    )
    from_showing = limit_start + 1 if limit_start is not None else 1
    to_showing = limit_start + limit_page_length if limit_start is not None else total_count

    return {"data": orders, "total": total_count, "from": from_showing, "to": to_showing, "current_page": page or 1, "per_page": limit_page_length or total_count}


@frappe.whitelist(allow_guest=True)
def get_cart():
    customer = get_current_customer()
    if not customer or not customer.get("id"):
        return {"items": [], "total": 0.0, "count": 0}

    customer_id = customer["id"]
    so = frappe.get_all(
        "Sales Order",
        filters={"customer": customer_id, "docstatus": 0},
        fields=["name", "grand_total"],
        limit=1,
    )
    if not so:
        return {"items": [], "total": 0.0, "count": 0}

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
        "total": so[0].grand_total,
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

    so_doc.transaction_date = nowdate()
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
        })
    so_doc.save(ignore_permissions=True)
    if submit:
        so_doc.submit()
    frappe.db.commit()
    return so_doc.name

    