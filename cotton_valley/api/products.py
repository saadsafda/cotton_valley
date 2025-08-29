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
            i.custom_case_pack as case_pack,
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
def get_product(product_id):
    # Base product
    product = frappe.db.get_value(
        "Item",
        {"name": product_id},
        [
            "name as id",
            "item_name as name",
            "description",
            "custom_short_description as short_description",
            "image as product_thumbnail",
            "stock_uom as unit",
            "item_group as category",
            "custom_slug as slug",
            "is_sales_item as is_sale_enable",
            "is_fixed_asset as is_return",
            "disabled as status"
        ],
        as_dict=True
    )

    if not product:
        return {}

    # Pricing
    price_data = frappe.db.get_value(
        "Item Price",
        {"item_code": product["id"], "selling": 1},
        ["price_list_rate", "currency"],
        as_dict=True
    )
    if price_data:
        product["price"] = float(price_data["price_list_rate"])
        # Example: add discount/sale_price from custom fields
        product["sale_price"] = frappe.db.get_value("Item", product["id"], "custom_sale_price") or product["price"]
        product["discount"] = round(((product["price"] - product["sale_price"]) / product["price"]) * 100, 2) if product["price"] else 0

    # Stock
    qty = frappe.db.sql("""SELECT COALESCE(SUM(actual_qty),0) as qty
                           FROM `tabBin` WHERE item_code=%s""", product["id"], as_dict=True)
    product["quantity"] = qty[0].qty
    product["stock_status"] = "in_stock" if qty[0].qty > 0 else "out_of_stock"

    # Galleries (linked files)
    galleries = frappe.get_all(
        "Product Images",
        filters={"parent": product["id"], "parenttype": "Item"},
        fields=["image as original_url", "idx", "name"]
    )

    product["product_images"] = [
        {
            "id": g["name"],
            "original_url": frappe.utils.get_url(g["original_url"]),
            "idx": g["idx"]
        }
        for g in galleries
    ]

    # Duplicate as galleries
    product["product_galleries"] = product["product_images"]

    # Categories (using Item Group)
    product["categories"] = [{
        "id": product["category"],
        "name": frappe.db.get_value("Item Group", product["category"], "item_group_name"),
        "slug": product["category"].lower().replace(" ", "-")
    }]

    # Tags (if you store tags in custom child table)
    product["tags"] = []

    # Store (map to Company or Supplier)
    product["store"] = {
        "id": 1,
        "store_name": frappe.defaults.get_global_default("company"),
        "country": frappe.defaults.get_global_default("country"),
    }

    # Reviews placeholder
    product["reviews"] = []

    return product

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
            i.custom_case_pack as case_pack,
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