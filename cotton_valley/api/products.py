# api/products.py
from cotton_valley.api.category import get_category_list
import frappe # type: ignore
from frappe import _ # type: ignore
from cotton_valley.api.website_theme_setting import get_file, get_categories_from_string
import requests
from cotton_valley.secrets import SAP_USER, SAP_PASSWORD



@frappe.whitelist(allow_guest=True)
def get_all_products_sql(
    ids=None,
    category=None,
    subcategory=None,
    sortBy=None,
    search=None,
    page=None,
    attribute=None,
):
    """
    Fetch products using a raw SQL query with dynamic filters. The results
    include prices, stock quantities, categories, recommended products,
    gallery images and brand/store information. Pagination and sorting
    follow the same semantics as the original get_all_products API.
    """
    # Helper to split comma-separated parameters
    def split_param(val):
        return [s.strip() for s in val.split(",") if s.strip()] if val else None

    # Convert inputs into usable lists/values
    id_list = split_param(ids) if ids and ids != "null" else None
    category_list = split_param(category) if category and category != "null" else None
    subcategory_list = split_param(subcategory) if subcategory and subcategory != "null" else None
    attribute_list = split_param(attribute) if attribute and attribute != "null" else None
    sortBy = None if not sortBy or sortBy == "null" else sortBy
    search = None if not search or search == "null" else search
    page = int(page) if page and page != "null" else None

    # Build WHERE conditions and parameter dictionary
    where_clauses = ["i.disabled = 0"]
    params = {}

    # Filter by specific IDs
    if id_list:
        where_clauses.append("i.name IN %(ids)s")
        params["ids"] = tuple(id_list)

    # Category filter via Product Categoris join
    if category_list:
        where_clauses.append("pc.product_category IN %(categories)s")
        params["categories"] = tuple(category_list)

    # Subcategory filter
    if subcategory_list:
        where_clauses.append("i.custom_sub_category IN %(subcategories)s")
        params["subcategories"] = tuple(subcategory_list)

    # Search filter on item_name
    if search:
        where_clauses.append("i.item_name LIKE %(search)s")
        params["search"] = f"%{search}%"

    # Core SELECT with joins and aggregates
    select_sql = """
        SELECT
            i.name AS id,
            i.item_name AS name,
            i.custom_short_description AS short_description,
            i.description,
            i.item_group AS type,
            i.name AS sku,
            i.name AS slug,
            i.stock_uom AS unit,
            i.weight_uom AS weight,
            i.custom_case_pack AS case_pack,
            i.image AS product_thumbnail_id,
            i.disabled AS status,
            i.custom_sub_category AS sub_category,
            i.custom_carton_upc AS carton_upc,
            i.custom_case_per_pallet AS case_per_pallet,
            i.custom_cbm AS cbm,
            i.custom_upc AS upc_code,
            i.custom_pallet_hi AS pallet_hi,
            i.custom_pallet_ti AS pallet_ti,
            i.custom_package_width_inch AS package_width,
            i.custom_package_length_inch AS package_length,
            i.custom_package_height_inch AS package_height,
            i.custom_weight_lbs AS package_weight,
            i.custom_item_width_inch AS item_width,
            i.custom_item_length_inch AS item_length,
            i.custom_item_height_inch AS item_height,
            i.custom_item_weight_lbs AS item_weight,
            i.custom_coming_soon AS coming_soon,
            i.custom_new_arrivals AS new_arrivals,

            -- Price (taking the maximum price_list_rate if multiple)
            COALESCE(MAX(ip.price_list_rate), 0) AS price,
            COALESCE(MAX(ip.price_list_rate), 0) AS sale_price,
            0 AS discount,

            -- Stock quantity
            COALESCE(SUM(stock.actual_qty), 0) AS quantity,

            -- Aggregate recommended products
            GROUP_CONCAT(DISTINCT rp.product_name) AS related_products,

            -- Aggregate categories
            GROUP_CONCAT(DISTINCT pc.product_category) AS categories,

            -- Aggregate gallery image URLs
            GROUP_CONCAT(DISTINCT pi.image) AS product_galleries,

            -- Brand details
            b.name AS brand_id,
            b.brand AS brand_name,
            b.description AS brand_description,
            b.image AS brand_image

        FROM `tabItem` AS i
        LEFT JOIN `tabProduct Categoris` AS pc ON pc.parent = i.name
        LEFT JOIN `tabItem Price` AS ip ON ip.item_code = i.name
        LEFT JOIN `tabBin` AS stock ON stock.item_code = i.name
        LEFT JOIN `tabRecommended Products` AS rp ON rp.parent = i.name
        LEFT JOIN `tabProduct Images` AS pi ON pi.parent = i.name
        LEFT JOIN `tabBrand` AS b ON b.name = i.brand
    """

    # Apply WHERE conditions
    if where_clauses:
        select_sql += "\nWHERE " + " AND ".join(where_clauses)

    # Group by item to aggregate related rows
    select_sql += "\nGROUP BY i.name"

    # Stock status filtering via HAVING
    if attribute_list:
        attrs = set(attribute_list)
        if attrs == {"in_stock"}:
            select_sql += "\nHAVING quantity > 0"
        elif attrs == {"out_stock"}:
            select_sql += "\nHAVING quantity = 0"

    # Sorting
    order_clause = {
        "asc": "i.creation ASC",
        "desc": "i.creation DESC",
        "a-z": "i.item_name ASC",
        "z-a": "i.item_name DESC",
        "low-high": "price ASC",
        "high-low": "price DESC",
    }.get(sortBy, "i.creation ASC")
    select_sql += f"\nORDER BY {order_clause}"

    # Pagination (30 items per page)
    per_page = 30
    if page and page > 0:
        offset = (page - 1) * per_page
        select_sql += "\nLIMIT %(per_page)s OFFSET %(offset)s"
        params["per_page"] = per_page
        params["offset"] = offset

    # Run the query

    # print(select_sql, "checking sql qurry \n\n\n\n")
    rows = frappe.db.sql(select_sql, params, as_dict=True)

    # Determine total record count with the same filters
    count_sql = """
        SELECT COUNT(DISTINCT i.name) AS total
        FROM `tabItem` AS i
        LEFT JOIN `tabProduct Categoris` AS pc ON pc.parent = i.name
    """
    if where_clauses:
        count_sql += "\nWHERE " + " AND ".join(where_clauses)
    total_result = frappe.db.sql(count_sql, params, as_dict=True)
    total_count = total_result[0]["total"] if total_result else 0

    # Post-process rows: split aggregates and call get_file/get_category_list
    products = []
    for row in rows:
        pid = row["id"]
        product = {
            "id": pid,
            "name": row["name"],
            "short_description": row["short_description"],
            "description": row.get("description"),
            "type": row["type"],
            "sku": row["sku"],
            "slug": row["slug"],
            "unit": row.get("unit"),
            "weight": row.get("weight"),
            "case_pack": row.get("case_pack"),
            "product_thumbnail_id": row.get("product_thumbnail_id"),
            "status": row.get("status"),
            "sub_category": row.get("sub_category"),
            "carton_upc": row.get("carton_upc"),
            "case_per_pallet": row.get("case_per_pallet"),
            "cbm": row.get("cbm"),
            "upc_code": row.get("upc_code"),
            "pallet_hi": row.get("pallet_hi"),
            "pallet_ti": row.get("pallet_ti"),
            "package_width": row.get("package_width"),
            "package_length": row.get("package_length"),
            "package_height": row.get("package_height"),
            "package_weight": row.get("package_weight"),
            "item_width": row.get("item_width"),
            "item_length": row.get("item_length"),
            "item_height": row.get("item_height"),
            "item_weight": row.get("item_weight"),
            "coming_soon": row.get("coming_soon"),
            "new_arrivals": row.get("new_arrivals"),
            "price": row.get("price"),
            "sale_price": row.get("sale_price"),
            "discount": row.get("discount"),
        }

        qty = row.get("quantity") or 0
        product["quantity"] = qty
        product["stock_status"] = "in_stock" if qty > 0 else "out_of_stock"

        # Parse comma-separated recommended products
        rel = row.get("related_products")
        product["related_products"] = rel.split(",") if rel else []

        # Parse gallery URLs and map to file objects
        galleries = row.get("product_galleries")
        gallery_urls = galleries.split(",") if galleries else []
        product["product_galleries"] = [get_file(url) if url else None for url in gallery_urls]

        # Thumbnail and meta image
        thumb_url = row.get("product_thumbnail_id")
        product["product_thumbnail"] = get_file(thumb_url)
        product["product_meta_image"] = get_file(thumb_url)

        # Parse categories and resolve via get_category_list
        cat_ids = row.get("categories").split(",") if row.get("categories") else []
        categories_list = []
        for cid in cat_ids:
            cid = cid.strip()
            if cid:
                try:
                    cat_data = get_category_list(cid).get("data")
                    if cat_data:
                        categories_list.append(cat_data[0])
                except Exception:
                    pass
        product["categories"] = categories_list

        # Reviews placeholders
        product["reviews"] = []
        product["reviews_count"] = 0
        product["rating_count"] = 0

        # Brand/store info
        brand_name = row.get("brand_id")
        if brand_name:
            logo_url = row.get("brand_image")
            product["store"] = {
                "id": brand_name,
                "store_name": row.get("brand_name") or brand_name,
                "slug": brand_name,
                "description": row.get("brand_description"),
                "store_logo": get_file(logo_url) if logo_url else None,
            }
        else:
            product["store"] = None

        products.append(product)

    current_page = page or 1
    return {
        "data": products,
        "total": total_count,
        "current_page": current_page,
        "per_page": per_page if page else total_count,
    }




@frappe.whitelist(allow_guest=True)
def get_all_products(ids=None, category=None, subcategory=None, sortBy=None, search=None, page=None, attribute=None):
    category = None if not category or category == "null" else get_categories_from_string(category)
    subcategory = None if not subcategory or subcategory == "null" else get_categories_from_string(subcategory)
    attribute = None if not attribute or attribute == "null" else get_categories_from_string(attribute)
    sortBy = None if not sortBy or sortBy == "null" else sortBy
    search = None if not search or search == "null" else search
    page = None if not page or page == "null" else int(page)

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
            return {"data": [], "total": 0}  # no products found for this category

        filters["name"] = ["in", product_ids]

    # --- Subcategory Filter ---
    if subcategory:
        filters["custom_sub_category"] = ["in", subcategory]

    # --- Search Filter ---
    if search:
        filters["item_name"] = ["like", f"%{search}%"]

    # --- Sort Options ---
    sort_clause = {
        "asc": "creation asc",
        "desc": "creation desc",
        "a-z": "item_name asc",
        "z-a": "item_name desc",
        "low-high": "price asc",
        "high-low": "price desc"
    }.get(sortBy, "creation asc")

    # --- Total Count ---
    total_count = frappe.db.count("Item", filters=filters)

    # --- Pagination ---
    limit_start = (page - 1) * 30 if page and page > 0 else None
    limit_page_length = 30 if page else None

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
            "disabled as status",
            "brand",
            "custom_sub_category as sub_category",
            "custom_carton_upc as carton_upc",
            "custom_case_per_pallet as case_per_pallet",
            "custom_cbm as cbm",
            "custom_upc as upc_code",
            "custom_pallet_hi as pallet_hi",
            "custom_pallet_ti as pallet_ti",
            "custom_package_width_inch as package_width",
            "custom_package_length_inch as package_length",
            "custom_package_height_inch as package_height",
            "custom_weight_lbs as package_weight",
            "custom_item_width_inch as item_width",
            "custom_item_length_inch as item_length",
            "custom_item_height_inch as item_height",
            "custom_item_weight_lbs as item_weight",
            "custom_coming_soon as coming_soon",
            "custom_new_arrivals as new_arrivals"
        ],
        order_by=sort_clause,
        limit_start=limit_start,
        limit_page_length=limit_page_length
    )

    if not items:
        return {"data": [], "total": total_count, "current_page": page or 1, "per_page": 30}

    item_ids = [p["id"] for p in items]

    # --- Batch Queries ---
    # Prices
    price_map = {}
    if frappe.session.user != "Guest":
        price_data = frappe.db.sql("""
            SELECT item_code, price_list_rate
            FROM `tabItem Price`
            WHERE item_code in %s
        """, (item_ids,), as_dict=True)
        price_map = {p["item_code"]: p["price_list_rate"] for p in price_data}

    # Stock
    stock_data = frappe.db.sql("""
        SELECT item_code, SUM(actual_qty) as qty
        FROM `tabBin`
        WHERE item_code in %s
        GROUP BY item_code
    """, (item_ids,), as_dict=True)
    stock_map = {s["item_code"]: s["qty"] for s in stock_data}

    # Product Images
    galleries_data = frappe.get_all(
        "Product Images",
        filters={"parent": ["in", item_ids]},
        fields=["parent", "list_index", "image"],
        order_by="list_index asc"
    )
    galleries_map = {}
    for g in galleries_data:
        galleries_map.setdefault(g["parent"], []).append(get_file(g["image"]) if g["image"] else None)

    # Categories
    categories_data = frappe.db.sql("""
        SELECT c.parent, c.product_category as id
        FROM `tabProduct Categoris` c
        WHERE c.parent in %s
    """, (item_ids,), as_dict=True)
    categories_map = {}
    for cat in categories_data:
        cat_data = get_category_list(cat["id"])["data"]
        if cat_data:
            categories_map.setdefault(cat["parent"], []).append(cat_data[0])

    # Brands
    brand_ids = [p["brand"] for p in items if p.get("brand")]
    brand_map = {}
    if brand_ids:
        brands = frappe.get_all("Brand", filters={"name": ["in", brand_ids]},
                                fields=["name", "brand", "description", "image"])
        brand_map = {b["name"]: b for b in brands}


    # --- Final Assembly ---
    products = []
    for product in items:
        product_id = product["id"]

        # Price
        if frappe.session.user != "Guest":
            product["price"] = price_map.get(product_id, 0)
            product["sale_price"] = product["price"]
            product["discount"] = 0
        else:
            product["price"] = product["sale_price"] = product["discount"] = None

        # Stock
        qty = stock_map.get(product_id, 0)
        product["quantity"] = qty
        product["stock_status"] = "in_stock" if qty > 0 else "out_of_stock"

        # Stock Filter
        if attribute:
            if attribute == ["in_stock"] and qty <= 0:
                continue
            if attribute == ["out_stock"] and qty > 0:
                continue

        # --- Stock Filter ---
        if attribute:
            # if only "in_stock" selected → only keep items with qty > 0
            if attribute == ["in_stock"] and product["quantity"] <= 0:
                continue
            # if only "out_stock" selected → only keep items with qty = 0
            if attribute == ["out_stock"] and product["quantity"] > 0:
                continue
            # if both are passed, ignore filter (show all)

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
        product["product_galleries"] = galleries_map.get(product_id, [])
        product["product_meta_image"] = get_file(product["product_thumbnail_id"])

        # Categories
        product["categories"] = categories_map.get(product_id, [])

        # reviews
        product["reviews"] = []
        product["reviews_count"] = 0
        product["rating_count"] = 0

        # Brand / Store
        if product["brand"]:
            brand_data = brand_map.get(product["brand"])
            if brand_data:
                product["store"] = {
                    "id": brand_data["name"],
                    "store_name": brand_data["brand"],
                    "slug": brand_data["name"],
                    "description": brand_data["description"],
                    "store_logo": get_file(brand_data["image"])
                }

        products.append(product)

    return {"data": products, "total": total_count, "current_page": page or 1, "per_page": limit_page_length or total_count}


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
            "custom_case_pack as case_pack",
            "image as product_thumbnail_id",
            "disabled as status",
            "brand",
            "custom_sub_category as sub_category",
            "custom_carton_upc as carton_upc",
            "custom_case_per_pallet as case_per_pallet",
            "custom_cbm as cbm",
            "custom_upc as upc_code",
            "custom_pallet_hi as pallet_hi",
            "custom_pallet_ti as pallet_ti",
            "custom_package_width_inch as package_width",
            "custom_package_length_inch as package_length",
            "custom_package_height_inch as package_height",
            "custom_weight_lbs as package_weight",
            "custom_item_width_inch as item_width",
            "custom_item_length_inch as item_length",
            "custom_item_height_inch as item_height",
            "custom_item_weight_lbs as item_weight",
            "custom_coming_soon as coming_soon",
            "custom_new_arrivals as new_arrivals"
        ],
        as_dict=True
    )

    if not product:
        return {"error": "Product not found"}
    
    if product["sub_category"]:
        subcat_data = frappe.db.get_value(
            "Product Subcategory",
            product["sub_category"],
            ["title"],
            as_dict=True
        )
        if subcat_data:
            product["sub_category_name"] = subcat_data.title

    # Example: handle prices (if you have Price List / Item Price doctype)

    if frappe.session.user != "Guest":
        price_data = frappe.db.sql("""
            SELECT price_list_rate
            FROM `tabItem Price`
            WHERE item_code = %s
            LIMIT 1
        """, (product_id,), as_dict=True)
        product["price"] = price_data[0]["price_list_rate"] if price_data else 0
        product["sale_price"] = product["price"]  # adjust if you have discount rules
        product["discount"] = 0  # calculate discount if needed
    else:
        product["price"] = None
        product["sale_price"] = None
        product["discount"] = None

    # quantity (stock across all warehouses)
    qty_data = frappe.db.sql("""
        SELECT COALESCE(SUM(actual_qty), 0) as qty
        FROM `tabBin`
        WHERE item_code = %s
    """, (product_id,), as_dict=True)
    product["quantity"] = qty_data[0]["qty"] if qty_data else 0
    if product["quantity"] > 0:
            product["stock_status"] = "in_stock"
    else:
        product["stock_status"] = "out_of_stock"

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

    if product["brand"]:
        brand_data = frappe.get_doc("Brand", product["brand"])
        product["store"] = {
            "id": brand_data.name,
            "store_name": brand_data.brand,
            "slug": brand_data.name,
            "description": brand_data.description,
            "store_logo": get_file(brand_data.image)
        }


    product["related_products"] = frappe.get_all("Recommended Products", filters={"parent": product_id}, fields=["product_name"], pluck="product_name")
    product["cross_sell_products"] = []

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


@frappe.whitelist()
def get_prices(item_code):
    url = f"https://erp.cottonvalley.us/ords/unvdst/cmitm/itmrate?ITMID={item_code}"
    response = requests.get(url, auth=(SAP_USER, SAP_PASSWORD))
    data = response.json()

    print(data, "Data from API \n\n\n\n\n")  # Debugging line

    if not data.get("items"):
        return "No prices found"

    prices = data["items"][0]

    for key, price_list in prices.items():
        if key == "itmid" or key == "itmdsc" or key == "itmgrpdsc":
            continue

        price_val = prices.get(f"{key}")
        price_list_name = key.replace("'", "")
        price_list = frappe.db.exists("Price List", price_list_name)

        print(price_list_name, price_val, "Price List Name and Value")  # Debugging line

        if not price_val or float(price_val) <= 0:
            continue

        if not price_list:
            continue


        existing = frappe.db.exists("Item Price", {
            "item_code": item_code,
            "price_list": price_list
        })

        if existing:
            ip = frappe.get_doc("Item Price", existing)
            ip.price_list_rate = float(price_val)
            ip.save()
        else:
            frappe.get_doc({
                "doctype": "Item Price",
                "item_code": item_code,
                "price_list": price_list,
                "price_list_rate": float(price_val),
                "currency": "USD"   # or your default currency
            }).insert()

    frappe.db.commit()
    return "Prices updated"



@frappe.whitelist()
def get_product_prices():
    items = frappe.get_all("Item", pluck="name")
    for item_code in items:
        url = f"https://erp.cottonvalley.us/ords/unvdst/cmitm/itmrate?ITMID={item_code}"
        response = requests.get(url, auth=(SAP_USER, SAP_PASSWORD))
        data = response.json()

        print(data, "Data from API \n\n\n\n\n")  # Debugging line

        if not data.get("items"):
            return "No prices found"

        prices = data["items"][0]

        for key, price_list in prices.items():
            if key == "itmid" or key == "itmdsc" or key == "itmgrpdsc":
                continue

            price_val = prices.get(f"{key}")
            price_list_name = key.replace("'", "")
            price_list = frappe.db.exists("Price List", price_list_name)

            print(price_list_name, price_val, "Price List Name and Value")  # Debugging line

            if not price_val or float(price_val) <= 0:
                continue

            if not price_list:
                continue


            existing = frappe.db.exists("Item Price", {
                "item_code": item_code,
                "price_list": price_list
            })

            if existing:
                ip = frappe.get_doc("Item Price", existing)
                ip.price_list_rate = float(price_val)
                ip.save()
            else:
                frappe.get_doc({
                    "doctype": "Item Price",
                    "item_code": item_code,
                    "price_list": price_list,
                    "price_list_rate": float(price_val),
                    "currency": "USD"   # or your default currency
                }).insert()

        frappe.db.commit()
    return "Prices updated"
