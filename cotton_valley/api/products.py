# api/products.py
from cotton_valley.api.category import get_category_list
import frappe
from frappe import _
from cotton_valley.api.website_theme_setting import get_file, get_categories_from_string


@frappe.whitelist(allow_guest=True)
def get_all_products(ids=None, category=None, subcategory=None, sortBy=None, search=None):
    category = None if not category or category == "null" else get_categories_from_string(category)
    subcategory = None if not subcategory or subcategory == "null" else get_categories_from_string(subcategory)
    sortBy = None if not sortBy or sortBy == "null" else sortBy
    search = None if not search or search == "null" else search
    filters = {"disabled": 0}  # only active products

    if ids:
        filters["name"] = ["in", ids]

    # --- Category Filter ---
    if category:
        # get all product IDs linked to this category
        product_ids = frappe.db.sql("""
            SELECT DISTINCT i.name
            FROM `tabItem` i
            INNER JOIN `tabProduct Categoris` c ON c.parent = i.name
            WHERE c.product_category in %s
        """, (category,), as_dict=True)
        product_ids = [p["name"] for p in product_ids]

        if not product_ids:
            return {"data": []}  # no products found for this category

        filters["name"] = ["in", product_ids]

    # --- Subcategory Filter ---
    if subcategory:
        filters["custom_sub_category"] = ["in", subcategory]

    # --- Search Filter ---
    if search:
        filters["item_name"] = ["like", f"%{search}%"]

    # --- Sort Options ---
    sort_clause = "item_name asc"
    if sortBy == "asc":
        sort_clause = "item_name asc"
    elif sortBy == "desc":
        sort_clause = "item_name desc"
    elif sortBy == "a_z":
        sort_clause = "item_name asc"
    elif sortBy == "z_a":
        sort_clause = "item_name desc"
    elif sortBy == "low_high":
        sort_clause = "price asc"
    elif sortBy == "high_low":
        sort_clause = "price desc"

    # get all items
    items = frappe.get_all(
        "Item",
        filters=filters,  # only active products
        fields=[
            "name as id",
            "item_name as name",
            "custom_short_description as short_description",
            "description",
            "item_group as type",
            "name as sku",
            "name as slug",
            "stock_uom as unit",
            "weight_uom as weight",
            "custom_case_pack as case_pack",
            "image as product_thumbnail_id",
            "disabled as status"
        ],
        order_by=sort_clause
    )

    products = []

    for product in items:
        product_id = product["id"]

        # price
        price_data = frappe.db.sql("""
            SELECT price_list_rate
            FROM `tabItem Price`
            WHERE item_code = %s
            LIMIT 1
        """, (product_id,), as_dict=True)
        product["price"] = price_data[0]["price_list_rate"] if price_data else 0
        product["sale_price"] = product["price"]
        product["discount"] = 0

        # related products
        product["related_products"] = [
            row.product_name for row in frappe.get_all(
                "Recommended Products",
                filters={"parent": product_id},
                fields=["product_name"]
            )
        ]

        # images
        product["product_thumbnail"] = get_file(product["product_thumbnail_id"])
        galleries = frappe.get_all(
            "Product Images",
            filters={"parent": product_id},
            fields=["list_index", "image"],
            order_by="list_index asc"
        )
        product["product_galleries"] = [get_file(g.image) for g in galleries if g.image]
        product["product_meta_image"] = get_file(product["product_thumbnail_id"])

        # categories
        categories = frappe.db.sql("""
            SELECT c.product_category as id
            FROM `tabProduct Categoris` c
            INNER JOIN `tabProduct Category` pc ON pc.name = c.product_category
            WHERE c.parent = %s
        """, (product_id,), as_dict=True)

        category_list = []
        for cat in categories:
            category_data = get_category_list(cat.id)["data"]
            if category_data:
                category_list.append(category_data[0])
        product["categories"] = category_list

        # reviews
        reviews = []  # extend later if needed
        product["reviews"] = reviews
        product["reviews_count"] = len(reviews)
        product["rating_count"] = sum([r["rating"] for r in reviews]) / len(reviews) if reviews else 0

        products.append(product)

    return {"data": products}

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

    if sortBy == "asc":
        products = sorted(products, key=lambda x: x["name"].lower())
    elif sortBy == "desc":
        products = sorted(products, key=lambda x: x["name"].lower(), reverse=True)
    elif sortBy == "a-z":
        products = sorted(products, key=lambda x: x["name"].lower())
    elif sortBy == "z-a":
        products = sorted(products, key=lambda x: x["name"].lower(), reverse=True)
    elif sortBy == "low-high":
        products = sorted(products, key=lambda x: x["price"] or 0)
    elif sortBy == "high-low":
        products = sorted(products, key=lambda x: -(x["price"] or 0))

    return products


# @frappe.whitelist(allow_guest=True)
# def get_product(product_id):
#     # Base product
#     product = frappe.db.get_value(
#         "Item",
#         {"name": product_id},
#         [
#             "name as id",
#             "item_name as name",
#             "description",
#             "custom_short_description as short_description",
#             "image as product_thumbnail",
#             "stock_uom as unit",
#             "item_group as category",
#             "custom_slug as slug",
#             "is_sales_item as is_sale_enable",
#             "is_fixed_asset as is_return",
#             "disabled as status"
#         ],
#         as_dict=True
#     )

#     if not product:
#         return {}

#     # Pricing
#     price_data = frappe.db.get_value(
#         "Item Price",
#         {"item_code": product["id"], "selling": 1},
#         ["price_list_rate", "currency"],
#         as_dict=True
#     )
#     if price_data:
#         product["price"] = float(price_data["price_list_rate"])
#         # Example: add discount/sale_price from custom fields
#         product["sale_price"] = frappe.db.get_value("Item", product["id"], "custom_sale_price") or product["price"]
#         product["discount"] = round(((product["price"] - product["sale_price"]) / product["price"]) * 100, 2) if product["price"] else 0

#     # Stock
#     qty = frappe.db.sql("""SELECT COALESCE(SUM(actual_qty),0) as qty
#                            FROM `tabBin` WHERE item_code=%s""", product["id"], as_dict=True)
#     product["quantity"] = qty[0].qty
#     product["stock_status"] = "in_stock" if qty[0].qty > 0 else "out_of_stock"

#     # Galleries (linked files)
#     galleries = frappe.get_all(
#         "Product Images",
#         filters={"parent": product["id"], "parenttype": "Item"},
#         fields=["image as original_url", "idx", "name"]
#     )

#     product["product_images"] = [
#         {
#             "id": g["name"],
#             "original_url": frappe.utils.get_url(g["original_url"]),
#             "idx": g["idx"]
#         }
#         for g in galleries
#     ]

#     # Duplicate as galleries
#     product["product_galleries"] = product["product_images"]

#     # Categories (using Item Group)
#     product["categories"] = [{
#         "id": product["category"],
#         "name": frappe.db.get_value("Item Group", product["category"], "item_group_name"),
#         "slug": product["category"].lower().replace(" ", "-")
#     }]

#     # Tags (if you store tags in custom child table)
#     product["tags"] = []

#     # Store (map to Company or Supplier)
#     product["store"] = {
#         "id": 1,
#         "store_name": frappe.defaults.get_global_default("company"),
#         "country": frappe.defaults.get_global_default("country"),
#     }

#     # Reviews placeholder
#     product["reviews"] = []

#     return product

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

@frappe.whitelist(allow_guest=True)
def get_product(product_id):
    # get main product info
    product = frappe.db.get_value(
        "Item",
        product_id,
        [
            "name as id",
            "item_name as name",
            "custom_short_description as short_description",
            "description",
            "item_group as type",
            "name as sku",
            "name as slug",
            "stock_uom as unit",
            "weight_uom as weight",
            "image as product_thumbnail_id",
            "disabled as status"
        ],
        as_dict=True
    )

    if not product:
        return {"error": "Product not found"}

    # Example: handle prices (if you have Price List / Item Price doctype)
    price_data = frappe.db.sql("""
        SELECT price_list_rate
        FROM `tabItem Price`
        WHERE item_code = %s
        LIMIT 1
    """, (product_id,), as_dict=True)
    product["price"] = price_data[0]["price_list_rate"] if price_data else 0
    product["sale_price"] = product["price"]  # adjust if you have discount rules
    product["discount"] = 0  # calculate discount if needed

    product["related_products"] = [row.product_name for row in frappe.get_all("Recommended Products", filters={"parent": product_id}, fields=["product_name"])]

    product["product_thumbnail"] = get_file(product["product_thumbnail_id"])
    # galleries (attachments of Item)
    galleries = frappe.get_all(
        "Product Images",
        filters={"parent": product_id},
        fields=["list_index", "image"],
        order_by="list_index asc"
    )
    product["product_galleries"] = [get_file(gallery.image) for gallery in galleries]
    product["product_meta_image"] = get_file(product["product_thumbnail_id"])

    # thumbnail (first gallery file or image field)

    # categories (via Item Category child table, if you have)
    categories = frappe.db.sql("""
        SELECT c.product_category as id
        FROM `tabProduct Categoris` c
        INNER JOIN `tabProduct Category` pc ON pc.name = c.product_category
        WHERE c.parent = %s
    """, (product_id,), as_dict=True)

    category_list = []
    for cat in categories:
        category_list.append(get_category_list(cat.id)["data"][0])

    product["categories"] = category_list

    # tags (via Item Tag child table if you have)
    # tags = frappe.db.sql("""
    #     SELECT t.tag as id, tg.title as name, tg.slug
    #     FROM `tabItem Tag` t
    #     INNER JOIN `tabTag` tg ON tg.name = t.tag
    #     WHERE t.parent = %s
    # """, (product_id,), as_dict=True)
    # product["tags"] = tags

    # reviews (if you have Product Review doctype)
    # reviews = frappe.get_all(
    #     "Product Review",
    #     filters={"product": product_id},
    #     fields=["name as id", "review_text", "rating", "owner as user"]
    # )
    reviews = []
    product["reviews"] = reviews
    product["reviews_count"] = len(reviews)
    product["rating_count"] = sum([r["rating"] for r in reviews]) / len(reviews) if reviews else 0

    # store info (if you have linked supplier/vendor)
    # if frappe.db.exists("Supplier", {"supplier_name": frappe.db.get_value("Item", product_id, "supplier")}):
    #     supplier = frappe.db.get_value(
    #         "Supplier",
    #         {"supplier_name": frappe.db.get_value("Item", product_id, "supplier")},
    #         ["name as id", "supplier_name as store_name", "website as slug", "image as store_logo_id"],
    #         as_dict=True
    #     )
    #     product["store"] = supplier

    return product
