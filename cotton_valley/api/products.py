# api/products.py
from cotton_valley.api.category import get_category_list
import frappe # type: ignore
from frappe import _ # type: ignore
from cotton_valley.api.website_theme_setting import get_file, get_categories_from_string
import requests
from cotton_valley.secrets import SAP_USER, SAP_PASSWORD
from cotton_valley.api.common import check_customer_token


@frappe.whitelist(allow_guest=True)
def get_product_ids(search=None, company="Cotton Valley"):
    filters = {"disabled": 0}  # only active products
    company = "Cotton Valley" if not company or company == "null" else company
    if company:
        filters["company"] = company

    or_filters = {}
    if search:
        or_filters = {
            "item_name": ["like", f"%{search}%"],
            "name": ["like", f"%{search}%"]
        }

    product_ids = frappe.get_all(
        "Item",
        filters=filters,
        or_filters=or_filters,
        fields=["name as id", "item_name as name"],
        limit_page_length=1000  # limit to 1000 results for performance
    )

    return product_ids


@frappe.whitelist(allow_guest=True)
def get_all_products(ids=None, category=None, subcategory=None, sortBy=None, search=None, page=None, attribute=None, company="Cotton Valley"):
    category = None if not category or category == "null" else get_categories_from_string(category)
    subcategory = None if not subcategory or subcategory == "null" else get_categories_from_string(subcategory)
    attribute = None if not attribute or attribute == "null" else get_categories_from_string(attribute)
    sortBy = None if not sortBy or sortBy == "null" else sortBy
    search = None if not search or search == "null" else search
    page = None if not page or page == "null" else int(page)
    ids = None if not ids or ids == "null" else get_categories_from_string(ids)
    company = "Cotton Valley" if not company or company == "null" else company

    filters = {"disabled": 0}  # only active products

    if ids:
        filters["name"] = ["in", ids]

    if company:
        filters["company"] = company

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
    or_filters = {}
    if search:
        or_filters = {
            "item_name": ["like", f"%{search}%"],
            "name": ["like", f"%{search}%"]
        }

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
    total_count = 0
    if search:
        total_count = frappe.db.sql("""
            SELECT COUNT(*) 
            FROM `tabItem`
            WHERE item_name LIKE %s OR item_code LIKE %s
        """, (f"%{search}%", f"%{search}%"))[0][0]
    else:
        total_count = frappe.db.count("Item", filters=filters)

    # --- Pagination ---
    limit_start = (page - 1) * 30 if page and page > 0 else None
    limit_page_length = 30 if page else None

    # get all items
    items = frappe.get_all(
        "Item",
        filters=filters,
        or_filters=or_filters,
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
    if check_customer_token():
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



    # --- Final Assembly ---
    products = []
    for product in items:
        product_id = product["id"]

        # Price
        if check_customer_token():
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


        # images
        product["product_thumbnail"] = get_file(product["product_thumbnail_id"])
        product["product_galleries"] = galleries_map.get(product_id, [])
        product["product_meta_image"] = get_file(product["product_thumbnail_id"])


        products.append(product)
    product_showing = page * 30 if page and page > 0 else total_count
    from_showing = (product_showing - 30) + 1 if page and page > 0 else 1
    return {"data": products, "total": total_count, "from": from_showing, "to": product_showing, "current_page": page or 1, "per_page": limit_page_length or total_count}


@frappe.whitelist(allow_guest=True)
def get_product(product_id, company="Cotton Valley"):
    company = "Cotton Valley" if not company or company == "null" else company

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

    if check_customer_token():
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
    product["trending_products"] = frappe.get_all("Slides Items", filters={"parent": product_id}, fields=["product"], pluck='product')

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
        category_list.append(get_category_list(cat.id, company)["data"][0])

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

