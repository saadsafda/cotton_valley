import frappe
import json

@frappe.whitelist()
def get_months(doc):
    """
    Initialize sales target months for a Sales Person document.
    """
    doc = json.loads(doc)
    month_list = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    idx = 1
    for m in month_list:
        mnth = doc.append("sales_target")
        mnth.month = m
        mnth.target_amount = 10000.0 / 12
        mnth.idx = idx
        idx += 1


# -----------------------------------------------------------------------------
# Helpers for hierarchical Sales Person targets (Category -> Subcategory -> Item)
# Used by the Sales Person targets grid (public/js/sales_person.js).
# -----------------------------------------------------------------------------

@frappe.whitelist()
def get_subcategories_for_category(doctype, txt, searchfield, start, page_len, filters):
    """Link query: list Product Subcategories that belong to a given Product Category.

    The mapping is stored in the `SubCategories` child table on `Product Category`.
    """
    product_category = (filters or {}).get("product_category")
    if not product_category:
        return []

    txt = "%{0}%".format(txt or "")
    return frappe.db.sql(
        """
        SELECT ps.name, ps.title
        FROM `tabProduct Subcategory` ps
        INNER JOIN `tabSubCategories` sc
            ON sc.product_subcategory = ps.name
            AND sc.parenttype = 'Product Category'
            AND sc.parent = %(category)s
        WHERE (ps.name LIKE %(txt)s OR ps.title LIKE %(txt)s)
        ORDER BY ps.title ASC
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "category": product_category,
            "txt": txt,
            "start": int(start or 0),
            "page_len": int(page_len or 20),
        },
    )


@frappe.whitelist()
def get_items_for_category(doctype, txt, searchfield, start, page_len, filters):
    """Link query: list Items that belong to a given Product Category.

    Items reference Product Category via the `Product Categoris` child table
    (custom field `custom_product_categories` on Item).
    """
    product_category = (filters or {}).get("product_category")
    if not product_category:
        return []

    txt = "%{0}%".format(txt or "")
    return frappe.db.sql(
        """
        SELECT i.name, i.item_name
        FROM `tabItem` i
        INNER JOIN `tabProduct Categoris` pc
            ON pc.parent = i.name
            AND pc.parenttype = 'Item'
            AND pc.parentfield = 'custom_product_categories'
        WHERE i.hide = 0
            AND pc.product_category = %(category)s
            AND (i.name LIKE %(txt)s OR i.item_name LIKE %(txt)s)
        ORDER BY i.item_name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "category": product_category,
            "txt": txt,
            "start": int(start or 0),
            "page_len": int(page_len or 20),
        },
    )