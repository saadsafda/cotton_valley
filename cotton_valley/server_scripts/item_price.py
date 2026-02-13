import frappe


def before_save(doc, method):
    """
    On save of Item Price, if the price list is 'Retail',
    compare the rate with the Item's stock_price field.
    If they differ, update the Item's stock_price to match.
    """
    if doc.price_list != "Retail":
        return

    if not doc.item_code:
        return

    item_stock_price = frappe.db.get_value("Item", doc.item_code, "stock_price")

    if item_stock_price is None:
        return

    # Compare the Item Price rate with the Item's stock_price
    if float(doc.price_list_rate or 0) != float(item_stock_price or 0):
        frappe.db.set_value("Item", doc.item_code, "stock_price", doc.price_list_rate)
