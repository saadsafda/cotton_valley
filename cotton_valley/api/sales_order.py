import frappe # type: ignore
from frappe.utils import nowdate # type: ignore
from cotton_valley.api.customer import get_current_customer

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
        return
    
    so = frappe.get_all(
        "Sales Order",
        filters={"customer": customer.id, "docstatus": 0},
        fields=["name"],
        limit=1,
    )

    if so:
        so_doc = frappe.get_doc("Sales Order", so[0].name)
        so_doc.items = []  # reset items
    else:
        so_doc = frappe.new_doc("Sales Order")
        so_doc.customer = customer
        so_doc.transaction_date = nowdate()

    for row in items:
        so_doc.append("items", {
            "item_code": row["item_code"],
            "qty": row["qty"],
            "rate": row["rate"],
        })

    so_doc.save(ignore_permissions=True)
    return so_doc.name

    