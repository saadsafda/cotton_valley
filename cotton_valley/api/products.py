# api/products.py
import frappe
from frappe import _

@frappe.whitelist(allow_guest=True)
def get_products(category=None, sortBy=None, search=None):
    category = None if not category or category == "null" else category
    sortBy = None if not sortBy or sortBy == "null" else sortBy
    search = None if not search or search == "null" else search
    
    query = """
        SELECT
            i.name as id,
            i.item_name as name,
            i.description,
            i.image,
            ip.price_list_rate as price,
            ip.currency,
            COALESCE(SUM(bin.actual_qty), 0) as quantity,
            i.stock_uom as unit,
            i.item_group as category
        FROM `tabItem` i
        LEFT JOIN `tabItem Price` ip ON ip.item_code = i.name
        LEFT JOIN `tabBin` bin ON bin.item_code = i.name
        WHERE i.disabled = 0
        GROUP BY i.name
    """
    products = frappe.db.sql(query, as_dict=True)
    print(category, "Print checking")  

    # Apply filters
    if category :
        products = [p for p in products if p["category"] == category]
    if search:
        products = [p for p in products if search.lower() in p["name"].lower()]
    if sortBy == "low-high":
        products = sorted(products, key=lambda x: x["price"] or 0)
    elif sortBy == "high-low":
        products = sorted(products, key=lambda x: -(x["price"] or 0))
    return products


@frappe.whitelist(allow_guest=True)
def get_all_products():
    items = frappe.db.sql("""
        SELECT 
            i.*,
            ip.price_list_rate AS price,
            ip.currency AS currency,
            COALESCE(SUM(b.actual_qty), 0) AS stock_qty,
            GROUP_CONCAT(pi.image ORDER BY pi.idx SEPARATOR ',') AS product_galleries
        FROM 
            `tabItem` i
        LEFT JOIN 
            `tabItem Price` ip 
            ON ip.item_code = i.name 
            AND ip.price_list = %s
        LEFT JOIN 
            `tabBin` b
            ON b.item_code = i.name
        LEFT JOIN
            `tabProduct Images` pi
            ON pi.parent = i.name
        WHERE 
            i.disabled = 0
        GROUP BY 
            i.name, i.item_name, i.image, ip.price_list_rate, ip.currency
    """, ("Standard Selling",), as_dict=True)

    # Convert product_images string → list
    for item in items:
        if item.get("product_galleries"):
            item["product_galleries"] = item["product_galleries"].split(",")
        else:
            item["product_galleries"] = []

    return items

@frappe.whitelist(allow_guest=True)
def get_hot_products():
    items = frappe.db.sql("""
        SELECT 
            i.name AS item_code,
            i.item_name,
            i.image,
            i.is_hot_item,
            i.is_sale_enable,
            i.is_featured,
            i.custom_case_pack AS sku,
            ip.price_list_rate AS price,
            ip.currency AS currency,
            COALESCE(SUM(b.actual_qty), 0) AS stock_qty,
            GROUP_CONCAT(pi.image ORDER BY pi.idx SEPARATOR ',') AS product_galleries
        FROM 
            `tabItem` i
        LEFT JOIN 
            `tabItem Price` ip 
            ON ip.item_code = i.name 
            AND ip.price_list = %s
        LEFT JOIN 
            `tabBin` b
            ON b.item_code = i.name
        LEFT JOIN
            `tabProduct Images` pi
            ON pi.parent = i.name
        WHERE 
            i.disabled = 0 
            AND i.is_hot_item = 1
        GROUP BY 
            i.name, i.item_name, i.image, ip.price_list_rate, ip.currency
    """, ("Standard Selling",), as_dict=True)

    # Convert product_images string → list
    for item in items:
        if item.get("product_galleries"):
            item["product_galleries"] = item["product_galleries"].split(",")
        else:
            item["product_galleries"] = []

    return items