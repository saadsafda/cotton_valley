import frappe

def update_customer_order_summary(doc, method):
    if not doc.customer:
        return

    # Get all submitted sales orders of this customer
    sales_orders = frappe.get_all(
        "Sales Order",
        filters={"customer": doc.customer, "docstatus": 1},
        fields=["grand_total", "transaction_date"]
    )

    total_orders = len(sales_orders)
    total_amount = sum([so.grand_total for so in sales_orders])

    # doc.total_orders = total_orders
    # doc.total_order_amount = total_amount
    doc.custom_last_order_date = max((so.transaction_date for so in sales_orders), default=None)

    # Update Customer fields
    frappe.db.set_value("Customer", doc.customer, {
        "no_of_orders": total_orders,
        "orders_amount": total_amount,
        "last_order_date": doc.custom_last_order_date
    })

    frappe.db.commit()

    make_delivery_note_on_submit(doc, method)


def make_delivery_note_on_submit(doc, method):
    try:
        dn = frappe.new_doc("Delivery Note")
        dn.customer = doc.customer
        dn.company = doc.company
        dn.posting_date = frappe.utils.nowdate()
        dn.set_warehouse = doc.set_warehouse or None

        for item in doc.items:
            dn.append("items", {
                "item_code": item.item_code,
                "qty": item.qty,
                "rate": item.rate,
                "against_sales_order": doc.name,
                "so_detail": item.name,
                "warehouse": item.warehouse,
            })

        dn.save(ignore_permissions=True)
        dn.submit()
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Auto Delivery Note Creation Failed")
