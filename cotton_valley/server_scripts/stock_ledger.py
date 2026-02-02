import frappe
from frappe import enqueue
import time

def update_item_stock_and_price(item_code):
    # Get total available stock from Bin
    # If the Item is tied to a company, only sum warehouses for that company
    item_company = frappe.db.get_value("Item", item_code, "company")
    if item_company:
        qty = frappe.db.sql("""
            SELECT SUM(b.actual_qty)
            FROM `tabBin` b
            INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
            WHERE b.item_code = %s AND w.company = %s
        """, (item_code, item_company))[0][0] or 0
    else:
        qty = frappe.db.sql("""
            SELECT SUM(actual_qty)
            FROM `tabBin`
            WHERE item_code = %s
        """, (item_code,))[0][0] or 0

    # Get latest valuation rate from Stock Ledger Entry
    if item_company:
        rate = frappe.db.sql("""
            SELECT valuation_rate
            FROM `tabStock Ledger Entry`
            WHERE item_code = %s AND company = %s
            ORDER BY posting_date DESC, posting_time DESC
            LIMIT 1
        """, (item_code, item_company))
    else:
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
