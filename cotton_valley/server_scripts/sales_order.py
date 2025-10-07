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
        "total_orders": total_orders,
        "total_order_amount": total_amount
    })

    frappe.db.commit()
