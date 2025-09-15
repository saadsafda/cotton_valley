import frappe # type: ignore
from frappe.utils import nowdate # type: ignore
from cotton_valley.api.customer import get_current_customer
from cotton_valley.api.products import get_product


@frappe.whitelist()
def get_cart():
    customer = get_current_customer()
    if not customer or not customer.get("id"):
        return {"items": [], "total": 0.0, "count": 0}

    print(customer)
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


@frappe.whitelist()
def create_or_update_sales_order(items):
    customer = get_current_customer()
    """
    Create or update a Sales Order from cart.
    items = [
      {"item_code": "ITEM-001", "qty": 2, "rate": 500},
      {"item_code": "ITEM-002", "qty": 1, "rate": 300},
    ]
    """
    items = frappe.parse_json(items)

    if not customer:
        return "Customer not found"

    customer_id = customer["id"]
    so = frappe.get_all(
        "Sales Order",
        filters={"customer": customer_id, "docstatus": 0},
        fields=["name"],
        limit=1,
    )


    if so:
        so_doc = frappe.get_doc("Sales Order", so[0].name)
        so_doc.items = []  # reset items
    else:
        so_doc = frappe.new_doc("Sales Order")
        so_doc.customer = customer_id
        so_doc.transaction_date = nowdate()
        so_doc.delivery_date = nowdate()
        so_doc.order_type = "Shopping Cart"

    for row in items:
        so_doc.append("items", {
            "item_code": row["item_code"],
            "qty": row["qty"],
            "rate": row["rate"],
        })
    so_doc.save(ignore_permissions=True)
    frappe.db.commit()
    return so_doc.name

    