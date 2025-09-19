# api/products.py
from cotton_valley.api.category import get_category_list
import frappe # type: ignore
from frappe import _ # type: ignore
from cotton_valley.api.website_theme_setting import get_file, get_categories_from_string
import requests
from cotton_valley.secrets import SAP_USER, SAP_PASSWORD


@frappe.whitelist(allow_guest=True)
def get_all_products(ids=None, category=None, subcategory=None, sortBy=None, search=None, page=None, attribute=None):
    category = None if not category or category == "null" else get_categories_from_string(category)
    subcategory = None if not subcategory or subcategory == "null" else get_categories_from_string(subcategory)
    attribute = None if not attribute or attribute == "null" else get_categories_from_string(attribute)
    sortBy = None if not sortBy or sortBy == "null" else sortBy
    search = None if not search or search == "null" else search
    page = None if not page or page == "null" else int(page)

    filters = {"disabled": 0}
    join_conditions = []
    where_conditions = ["i.disabled = 0"]
    params = []

    # --- Category Filter ---
    if category:
        join_conditions.append("INNER JOIN `tabProduct Categoris` c ON c.parent = i.name")
        where_conditions.append("c.product_category IN %s")
        params.append(tuple(category))

    # --- Basic Filters ---
    if ids:
        where_conditions.append("i.name IN %s")
        params.append(tuple(ids))

    if subcategory:
        where_conditions.append("i.custom_sub_category IN %s")
        params.append(tuple(subcategory))

    if search:
        where_conditions.append("i.item_name LIKE %s")
        params.append(f"%{search}%")

    # --- Stock Filter (early filtering) ---
    stock_join = ""
    if attribute:
        stock_join = "LEFT JOIN (SELECT item_code, SUM(actual_qty) as total_qty FROM `tabBin` GROUP BY item_code) b ON b.item_code = i.name"
        if attribute == ["in_stock"]:
            where_conditions.append("(b.total_qty > 0 OR b.total_qty IS NULL)")
        elif attribute == ["out_stock"]:
            where_conditions.append("(b.total_qty <= 0 OR b.total_qty IS NULL)")

    # --- Sort Options ---
    sort_clause = {
        "asc": "i.creation ASC",
        "desc": "i.creation DESC",
        "a-z": "i.item_name ASC",
        "z-a": "i.item_name DESC",
        "low-high": "ip.price_list_rate ASC",
        "high-low": "ip.price_list_rate DESC"
    }.get(sortBy, "i.creation ASC")

    # Add price join for sorting if needed
    price_join = ""
    if sortBy in ["low-high", "high-low"] and frappe.session.user != "Guest":
        price_join = "LEFT JOIN `tabItem Price` ip ON ip.item_code = i.name"

    # --- Pagination ---
    limit_start = (page - 1) * 30 if page and page > 0 else 0
    limit_clause = f"LIMIT {limit_start}, 30" if page else ""

    # --- Main Query with All Data ---
    main_query = f"""
        SELECT 
            i.name as id,
            i.item_name as name,
            i.custom_short_description as short_description,
            i.description,
            i.item_group as type,
            i.name as sku,
            i.name as slug,
            i.stock_uom as unit,
            i.weight_uom as weight,
            i.custom_case_pack as case_pack,
            i.image as product_thumbnail_id,
            i.disabled as status,
            i.brand,
            i.custom_sub_category as sub_category,
            i.custom_carton_upc as carton_upc,
            i.custom_case_per_pallet as case_per_pallet,
            i.custom_cbm as cbm,
            i.custom_upc as upc_code,
            i.custom_pallet_hi as pallet_hi,
            i.custom_pallet_ti as pallet_ti,
            i.custom_package_width_inch as package_width,
            i.custom_package_length_inch as package_length,
            i.custom_package_height_inch as package_height,
            i.custom_weight_lbs as package_weight,
            i.custom_item_width_inch as item_width,
            i.custom_item_length_inch as item_length,
            i.custom_item_height_inch as item_height,
            i.custom_item_weight_lbs as item_weight,
            i.custom_coming_soon as coming_soon,
            i.custom_new_arrivals as new_arrivals,
            {'ip.price_list_rate as price,' if frappe.session.user != "Guest" else ''}
            COALESCE(stock.total_qty, 0) as quantity,
            CASE WHEN COALESCE(stock.total_qty, 0) > 0 THEN 'in_stock' ELSE 'out_of_stock' END as stock_status
        FROM `tabItem` i
        {' '.join(join_conditions)}
        {stock_join}
        {price_join}
        LEFT JOIN (
            SELECT item_code, SUM(actual_qty) as total_qty 
            FROM `tabBin` 
            GROUP BY item_code
        ) stock ON stock.item_code = i.name
        WHERE {' AND '.join(where_conditions)}
        ORDER BY {sort_clause}
        {limit_clause}
    """

    # Execute main query
    items = frappe.db.sql(main_query, tuple(params), as_dict=True)

    if not items:
        # Get total count for empty results
        count_query = f"""
            SELECT COUNT(DISTINCT i.name) as total
            FROM `tabItem` i
            {' '.join(join_conditions)}
            {stock_join}
            WHERE {' AND '.join(where_conditions)}
        """
        total_count = frappe.db.sql(count_query, tuple(params), as_dict=True)[0]["total"]
        return {"data": [], "total": total_count, "current_page": page or 1, "per_page": 30}

    item_ids = [p["id"] for p in items]

    # --- Optimized Batch Queries ---
    
    # Get total count (only if we have results)
    count_query = f"""
        SELECT COUNT(DISTINCT i.name) as total
        FROM `tabItem` i
        {' '.join(join_conditions)}
        {stock_join}
        WHERE {' AND '.join(where_conditions)}
    """
    total_count = frappe.db.sql(count_query, tuple(params), as_dict=True)[0]["total"]

    # Prices (only if not already fetched in main query)
    price_map = {}
    if frappe.session.user != "Guest" and sortBy not in ["low-high", "high-low"]:
        price_data = frappe.db.sql("""
            SELECT item_code, price_list_rate
            FROM `tabItem Price`
            WHERE item_code IN %s
        """, (tuple(item_ids),), as_dict=True)
        price_map = {p["item_code"]: p["price_list_rate"] for p in price_data}

    # Product Images - Optimized query
    galleries_data = frappe.db.sql("""
        SELECT parent, image, list_index
        FROM `tabProduct Images`
        WHERE parent IN %s
        ORDER BY parent, list_index ASC
    """, (tuple(item_ids),), as_dict=True)
    
    galleries_map = {}
    for g in galleries_data:
        if g["parent"] not in galleries_map:
            galleries_map[g["parent"]] = []
        galleries_map[g["parent"]].append(get_file(g["image"]) if g["image"] else None)

    # Categories - Single query with join
    categories_data = frappe.db.sql("""
        SELECT c.parent, cat.name, cat.category_name, cat.slug, cat.description, cat.image
        FROM `tabProduct Categoris` c
        INNER JOIN `tabProduct Category` cat ON cat.name = c.product_category
        WHERE c.parent IN %s
    """, (tuple(item_ids),), as_dict=True)
    
    categories_map = {}
    for cat in categories_data:
        if cat["parent"] not in categories_map:
            categories_map[cat["parent"]] = []
        categories_map[cat["parent"]].append({
            "id": cat["name"],
            "name": cat["category_name"],
            "slug": cat["slug"],
            "description": cat["description"],
            "image": get_file(cat["image"]) if cat["image"] else None
        })

    # Brands - Single optimized query
    brand_ids = [p["brand"] for p in items if p.get("brand")]
    brand_map = {}
    if brand_ids:
        brands = frappe.db.sql("""
            SELECT name, brand, description, image
            FROM `tabBrand`
            WHERE name IN %s
        """, (tuple(set(brand_ids)),), as_dict=True)
        brand_map = {b["name"]: b for b in brands}

    # Related Products - Single query
    related_data = frappe.db.sql("""
        SELECT parent, product_name
        FROM `tabRecommended Products`
        WHERE parent IN %s
    """, (tuple(item_ids),), as_dict=True)
    
    related_map = {}
    for rel in related_data:
        if rel["parent"] not in related_map:
            related_map[rel["parent"]] = []
        related_map[rel["parent"]].append(rel["product_name"])

    # --- Final Assembly ---
    products = []
    for product in items:
        product_id = product["id"]

        # Price (use from main query if available, otherwise from price_map)
        if frappe.session.user != "Guest":
            if "price" not in product or product["price"] is None:
                product["price"] = price_map.get(product_id, 0)
            product["sale_price"] = product["price"]
            product["discount"] = 0
        else:
            product["price"] = product["sale_price"] = product["discount"] = None

        # Related products
        product["related_products"] = related_map.get(product_id, [])

        # Images
        product["product_thumbnail"] = get_file(product["product_thumbnail_id"])
        product["product_galleries"] = galleries_map.get(product_id, [])
        product["product_meta_image"] = get_file(product["product_thumbnail_id"])

        # Categories
        product["categories"] = categories_map.get(product_id, [])

        # Reviews (kept as empty for now)
        product["reviews"] = []
        product["reviews_count"] = 0
        product["rating_count"] = 0

        # Brand / Store
        if product["brand"] and product["brand"] in brand_map:
            brand_data = brand_map[product["brand"]]
            product["store"] = {
                "id": brand_data["name"],
                "store_name": brand_data["brand"],
                "slug": brand_data["name"],
                "description": brand_data["description"],
                "store_logo": get_file(brand_data["image"])
            }

        products.append(product)

    return {
        "data": products, 
        "total": total_count, 
        "current_page": page or 1, 
        "per_page": 30
    }


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
