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
   # --- Normalize inputs ---
    category = None if not category or category == "null" else get_categories_from_string(category)
    subcategory = None if not subcategory or subcategory == "null" else get_categories_from_string(subcategory)
    attribute = None if not attribute or attribute == "null" else get_categories_from_string(attribute)
    ids = None if not ids or ids == "null" else ids
    sortBy = None if not sortBy or sortBy == "null" else sortBy
    search = None if not search or search == "null" else search
    page = None if not page or page == "null" else int(page)

    # --- Sort mapping (default: creation asc) ---
    sort_clause = {
        "asc": "i.creation ASC",
        "desc": "i.creation DESC",
        "a-z": "i.item_name ASC",
        "z-a": "i.item_name DESC",
        "low-high": "price_val ASC",
        "high-low": "price_val DESC"
    }.get(sortBy, "i.creation ASC")

    # --- Build dynamic WHERE safely ---
    where_parts = ["i.disabled = 0"]
    params = []

    # ids filter (if provided)
    id_list = []
    if ids:
        # allow ids to be list or comma-separated string
        id_list = ids if isinstance(ids, (list, tuple)) else [x.strip() for x in str(ids).split(",") if x.strip()]
        if id_list:
            where_parts.append(f"i.name IN ({', '.join(['%s'] * len(id_list))})")
            params.extend(id_list)

    # category filter via EXISTS to avoid prefetch
    if category:
        where_parts.append(f"""
            EXISTS (
                SELECT 1
                FROM `tabProduct Categoris` pc
                WHERE pc.parent = i.name
                  AND pc.product_category IN ({', '.join(['%s'] * len(category))})
            )
        """)
        params.extend(category)

    # subcategory filter (custom_sub_category multi-select or link)
    if subcategory:
        where_parts.append(f"i.custom_sub_category IN ({', '.join(['%s'] * len(subcategory))})")
        params.extend(subcategory)

    # search filter
    if search:
        where_parts.append("i.item_name LIKE %s")
        params.append(f"%{search}%")

    # attribute (stock) filter applied in SQL using the stock CTE result
    attribute_filter_sql = ""
    if attribute == ["in_stock"]:
        attribute_filter_sql = " AND COALESCE(b.qty, 0) > 0 "
    elif attribute == ["out_stock"]:
        attribute_filter_sql = " AND COALESCE(b.qty, 0) = 0 "

    where_sql = " AND ".join(where_parts) if where_parts else "1=1"

    # --- Pagination ---
    per_page = 30
    limit_start = (page - 1) * per_page if page and page > 0 else 0
    limit_len = per_page if page else 1000000  # if page is None, return all (same semantics as original)

    # --- Price visibility (guest vs logged in) ---
    include_price = frappe.session.user != "Guest"

    # We’ll compute a *sortable* price value inside SQL even if not exposed to guests
    # For sortable price we use any available Item Price (no price list constraint here, same as your original)
    # Note: exposure to clients is still controlled below.

    # --- Count query (distinct items matching filters) ---
    count_sql = f"""
        SELECT COUNT(*) AS total_count
        FROM (
            SELECT i.name
            FROM `tabItem` i
            LEFT JOIN (
                SELECT item_code, SUM(actual_qty) AS qty
                FROM `tabBin`
                GROUP BY item_code
            ) b ON b.item_code = i.name
            LEFT JOIN (
                SELECT ip.item_code, MAX(ip.price_list_rate) AS price_val
                FROM `tabItem Price` ip
                GROUP BY ip.item_code
            ) p ON p.item_code = i.name
            WHERE {where_sql} {attribute_filter_sql}
            GROUP BY i.name
        ) z
    """
    total_count = frappe.db.sql(count_sql, params, as_dict=True)[0]["total_count"] if count_sql else 0

    # --- Main fetch: base items + stock qty + price_val for sorting ---
    main_sql = f"""
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
            i.brand,
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
            COALESCE(b.qty, 0) AS quantity,
            CASE WHEN COALESCE(b.qty, 0) > 0 THEN 'in_stock' ELSE 'out_of_stock' END AS stock_status,
            COALESCE(p.price_val, 0) AS price_val
        FROM `tabItem` i
        LEFT JOIN (
            SELECT item_code, SUM(actual_qty) AS qty
            FROM `tabBin`
            GROUP BY item_code
        ) b ON b.item_code = i.name
        LEFT JOIN (
            SELECT ip.item_code, MAX(ip.price_list_rate) AS price_val
            FROM `tabItem Price` ip
            GROUP BY ip.item_code
        ) p ON p.item_code = i.name
        WHERE {where_sql} {attribute_filter_sql}
        GROUP BY i.name, b.qty, p.price_val
        ORDER BY {sort_clause}
        LIMIT %s OFFSET %s
    """
    items = frappe.db.sql(main_sql, params + [limit_len, limit_start], as_dict=True)

    if not items:
        return {"data": [], "total": total_count, "current_page": page or 1, "per_page": per_page if page else total_count}

    item_ids = [row["id"] for row in items]

    # --- Batch prices (only expose when not Guest) ---
    price_map = {}
    if include_price:
        price_rows = frappe.db.sql("""
            SELECT item_code, MAX(price_list_rate) AS price_list_rate
            FROM `tabItem Price`
            WHERE item_code IN ({})
            GROUP BY item_code
        """.format(", ".join(["%s"] * len(item_ids))), item_ids, as_dict=True)
        price_map = {r["item_code"]: r["price_list_rate"] for r in price_rows}

    # --- Galleries (ordered) ---
    galleries = frappe.get_all(
        "Product Images",
        filters={"parent": ["in", item_ids]},
        fields=["parent", "list_index", "image"],
        order_by="list_index asc"
    )
    galleries_map = {}
    for g in galleries:
        galleries_map.setdefault(g["parent"], []).append(get_file(g["image"]) if g["image"] else None)

    # --- Categories (hierarchy list for each item) ---
    categories_rows = frappe.db.sql("""
        SELECT c.parent, c.product_category AS id
        FROM `tabProduct Categoris` c
        WHERE c.parent IN ({})
    """.format(", ".join(["%s"] * len(item_ids))), item_ids, as_dict=True)
    categories_map = {}
    for row in categories_rows:
        cat_data = get_category_list(row["id"])["data"]
        if cat_data:
            categories_map.setdefault(row["parent"], []).append(cat_data[0])

    # --- Brands (store info) ---
    brand_ids = [p["brand"] for p in items if p.get("brand")]
    brand_map = {}
    if brand_ids:
        brand_rows = frappe.get_all(
            "Brand",
            filters={"name": ["in", list(set(brand_ids))]},
            fields=["name", "brand", "description", "image"]
        )
        brand_map = {b["name"]: b for b in brand_rows}

    # --- Recommended products (per item) ---
    rec_rows = frappe.get_all(
        "Recommended Products",
        filters={"parent": ["in", item_ids]},
        fields=["parent", "product_name"]
    )
    rec_map = {}
    for r in rec_rows:
        rec_map.setdefault(r["parent"], []).append(r["product_name"])

    # --- Final assembly ---
    products = []
    for p in items:
        pid = p["id"]

        # expose price only for logged-in users; keep sort-only price_val internal
        if include_price:
            p["price"] = price_map.get(pid, 0) or 0
            p["sale_price"] = p["price"]
            p["discount"] = 0
        else:
            p["price"] = p["sale_price"] = p["discount"] = None

        # related products
        p["related_products"] = rec_map.get(pid, [])

        # images
        p["product_thumbnail"] = get_file(p.get("product_thumbnail_id"))
        p["product_galleries"] = galleries_map.get(pid, [])
        p["product_meta_image"] = get_file(p.get("product_thumbnail_id"))

        # categories
        p["categories"] = categories_map.get(pid, [])

        # reviews (same placeholders)
        p["reviews"] = []
        p["reviews_count"] = 0
        p["rating_count"] = 0

        # brand / store
        if p.get("brand"):
            b = brand_map.get(p["brand"])
            if b:
                p["store"] = {
                    "id": b["name"],
                    "store_name": b["brand"],
                    "slug": b["name"],
                    "description": b["description"],
                    "store_logo": get_file(b["image"])
                }

        products.append(p)

    return {
        "data": products,
        "total": total_count,
        "current_page": page or 1,
        "per_page": per_page if page else total_count
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


@frappe.whitelist(allow_guest=True)
def get_all_items(ids=None, category=None, subcategory=None, sortBy=None, search=None, page=None, attribute=None):
    attribute = None if not attribute or attribute == "null" else get_categories_from_string(attribute)
    sortBy = None if not sortBy or sortBy == "null" else sortBy
    search = None if not search or search == "null" else search
    page = None if not page or page == "null" else int(page)
    ids = None if not ids or ids == "null" else get_categories_from_string(ids)

    filters = {"disabled": 0}  # only active products

    if ids:
        filters["name"] = ["in", ids]

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


    

    return {"data": items, "total": total_count, "current_page": page or 1, "per_page": limit_page_length or total_count}


@frappe.whitelist(allow_guest=True)
def get_all_with_stock(ids=None, category=None, subcategory=None, sortBy=None, search=None, page=None, attribute=None):
    attribute = None if not attribute or attribute == "null" else get_categories_from_string(attribute)
    sortBy = None if not sortBy or sortBy == "null" else sortBy
    search = None if not search or search == "null" else search
    page = None if not page or page == "null" else int(page)
    ids = None if not ids or ids == "null" else get_categories_from_string(ids)
    filters = {"disabled": 0}  # only active products

    if ids:
        filters["name"] = ["in", ids]

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
    # Stock
    stock_data = frappe.db.sql("""
        SELECT item_code, SUM(actual_qty) as qty
        FROM `tabBin`
        WHERE item_code in %s
        GROUP BY item_code
    """, (item_ids,), as_dict=True)
    stock_map = {s["item_code"]: s["qty"] for s in stock_data}

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
        product["product_meta_image"] = get_file(product["product_thumbnail_id"])

        # Categories


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
def get_all_with_category_and_stock(ids=None, category=None, subcategory=None, sortBy=None, search=None, page=None, attribute=None):
    category = None if not category or category == "null" else get_categories_from_string(category)
    subcategory = None if not subcategory or subcategory == "null" else get_categories_from_string(subcategory)
    attribute = None if not attribute or attribute == "null" else get_categories_from_string(attribute)
    sortBy = None if not sortBy or sortBy == "null" else sortBy
    search = None if not search or search == "null" else search
    page = None if not page or page == "null" else int(page)
    ids = None if not ids or ids == "null" else get_categories_from_string(ids)

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
