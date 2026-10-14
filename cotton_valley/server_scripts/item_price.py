import frappe
from frappe import _


def before_insert(doc, method):
    """
    Block Data Import "Insert New Records" rows whose ID already exists.

    Item Price uses hash naming, so on a primary key collision Frappe silently
    retries with a new random name, creating a duplicate instead of failing.
    """
    if not frappe.flags.in_import or not doc.name:
        return

    if frappe.db.exists("Item Price", doc.name):
        frappe.throw(
            _("Item Price {0} already exists. Use Update Existing Records to modify it.").format(
                frappe.bold(doc.name)
            ),
            frappe.DuplicateEntryError,
            title=_("Duplicate ID"),
        )


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
