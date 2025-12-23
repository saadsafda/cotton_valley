import frappe
from frappe import enqueue
import time

def update_item_stock_and_price(item_code):
    # Get total available stock from Bin
    qty = frappe.db.sql("""
        SELECT SUM(actual_qty)
        FROM `tabBin`
        WHERE item_code = %s
    """, (item_code,))[0][0] or 0

    # Get latest valuation rate from Stock Ledger Entry
    rate = frappe.db.sql("""
        SELECT valuation_rate
        FROM `tabStock Ledger Entry`
        WHERE item_code = %s
        ORDER BY posting_date DESC, posting_time DESC
        LIMIT 1
    """, (item_code,))
    valuation_rate = rate[0][0] if rate else 0
    threshold_stock = frappe.db.get_value("Item", item_code, "threshold_stock") or 0
    available_stock = frappe.db.get_value("Item", item_code, "available_stock") or 0
    if threshold_stock == int(float(available_stock)):
        frappe.db.set_value("Item", item_code, "threshold_stock", int(float(qty)))
    # Update item fields
    frappe.db.set_value("Item", item_code, {
        "available_stock": int(float(qty)),
        "stock_price": valuation_rate
    })

def on_submit(doc, method):
    if doc.item_code:
        enqueue(
            "cotton_valley.server_scripts.stock_ledger.delayed_update",
            item_code=doc.item_code,
            queue='short',
            timeout=60
        )

def delayed_update(item_code):
    # Wait a moment to ensure ERPNext finishes Bin updates
    time.sleep(2)
    update_item_stock_and_price(item_code)