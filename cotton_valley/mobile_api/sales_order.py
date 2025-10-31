import frappe
from frappe.utils import nowdate # type: ignore


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