# api/products.py
from cotton_valley.api.category import get_category_list
import frappe # type: ignore
from frappe import _ # type: ignore
from cotton_valley.api.website_theme_setting import get_file, get_categories_from_string
import requests
from cotton_valley.secrets import CV_USER, CV_PASSWORD, UDC_USER, UDC_PASSWORD
from cotton_valley.api.common import check_customer_token, get_customer_from_token
from frappe.utils import flt
import xlsxwriter
import io
import os
import json


@frappe.whitelist(allow_guest=True)
def make_product_views(product_id):
    # Validate input
    if not frappe.db.exists("Item", product_id):
        return {"status": "error", "message": "Invalid product ID"}

    # Get current value
    current_clicks = frappe.db.get_value("Item", product_id, "custom_no_of_clicks") or 0

    # Increment and update
    frappe.db.set_value("Item", product_id, "custom_no_of_clicks", current_clicks + 1)
    frappe.db.commit()

    return {"status": "success", "message": "Product views updated successfully"}


@frappe.whitelist(allow_guest=True)
def get_product_types_with_count(category=None, subcategory=None, company="Cotton Valley"):
    company = "Cotton Valley" if not company or company == "null" else company
    category = None if not category or category == "null" else get_categories_from_string(category)
    subcategory = None if not subcategory or subcategory == "null" else get_categories_from_string(subcategory)

    conditions = ["i.disabled = 0", "i.company = %s"]
    values = [company]

    if subcategory:
        conditions.append("i.custom_sub_category = %s")
        values.append(subcategory)

    if category:
        # build placeholders for IN clause dynamically
        placeholders = ", ".join(["%s"] * len(category)) if isinstance(category, (list, tuple)) else "%s"
        conditions.append(f"c.product_category IN ({placeholders})")
        if isinstance(category, (list, tuple)):
            values.extend(category)
        else:
            values.append(category)

    query = f"""
        SELECT i.item_group, COUNT(*) as product_count
        FROM `tabItem` i
        INNER JOIN `tabProduct Categoris` c ON c.parent = i.name
        WHERE {" AND ".join(conditions)}
        GROUP BY i.item_group
    """

    return frappe.db.sql(query, tuple(values), as_dict=True)


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
def get_all_products(ids=None, category=None, subcategory=None, sortBy=None, search=None, page=None, attribute=None, producttype=None, company="Cotton Valley", price=None, pcs_price=None):
    category = None if not category or category == "null" else get_categories_from_string(category)
    subcategory = None if not subcategory or subcategory == "null" else get_categories_from_string(subcategory)
    attribute = None if not attribute or attribute == "null" else get_categories_from_string(attribute)
    producttype = None if not producttype or producttype == "null" else get_categories_from_string(producttype)
    sortBy = None if not sortBy or sortBy == "null" else sortBy
    search = None if not search or search == "null" else search
    page = None if not page or page == "null" else int(page)
    ids = None if not ids or ids == "null" else get_categories_from_string(ids)
    company = "Cotton Valley" if not company or company == "null" else company
    price = None if not price or price == "null" else get_categories_from_string(price)
    pcs_price = None if not pcs_price or pcs_price == "null" else get_categories_from_string(pcs_price)

    filters = {"disabled": 0}  # only active products

    if ids:
        filters["name"] = ["in", ids]

    if company:
        filters["company"] = company

    if producttype:
        filters["item_group"] = ["in", producttype]

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
    }.get(sortBy, None)  # default sort handled separately

    print(sort_clause, "SORT CLAUSE")

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

    # get all items - use different query for default sort
    if sort_clause:
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
                "custom_new_arrivals as new_arrivals",
                "tag_color",
                "tag_name"
            ],
            order_by=sort_clause,
            limit_start=limit_start,
            limit_page_length=limit_page_length
        )
    else:
        # Default sort with custom_web_ranking - null/0 values last
        filter_conditions = []
        filter_values = []
        
        if ids:
            filter_conditions.append("name IN %s")
            filter_values.append(ids)
        
        if company:
            filter_conditions.append("company = %s")
            filter_values.append(company)
        
        if producttype:
            filter_conditions.append("item_group IN %s")
            filter_values.append(producttype)
        
        if subcategory:
            filter_conditions.append("custom_sub_category IN %s")
            filter_values.append(subcategory)
        
        filter_conditions.append("disabled = 0")
        
        search_condition = ""
        if search:
            search_condition = "AND (item_name LIKE %s OR name LIKE %s)"
            filter_values.extend([f"%{search}%", f"%{search}%"])
        
        where_clause = " AND ".join(filter_conditions)
        
        limit_clause = ""
        if limit_start is not None and limit_page_length:
            limit_clause = f"LIMIT {limit_start}, {limit_page_length}"
        elif limit_page_length:
            limit_clause = f"LIMIT {limit_page_length}"
        
        query = f"""
            SELECT 
                name as id,
                item_name as name,
                custom_short_description as short_description,
                description,
                item_group as type,
                name as sku,
                name as slug,
                stock_uom as unit,
                weight_uom as weight,
                custom_case_pack as case_pack,
                image as product_thumbnail_id,
                disabled as status,
                brand,
                custom_sub_category as sub_category,
                custom_carton_upc as carton_upc,
                custom_case_per_pallet as case_per_pallet,
                custom_cbm as cbm,
                custom_upc as upc_code,
                custom_pallet_hi as pallet_hi,
                custom_pallet_ti as pallet_ti,
                custom_package_width_inch as package_width,
                custom_package_length_inch as package_length,
                custom_package_height_inch as package_height,
                custom_weight_lbs as package_weight,
                custom_item_width_inch as item_width,
                custom_item_length_inch as item_length,
                custom_item_height_inch as item_height,
                custom_item_weight_lbs as item_weight,
                custom_coming_soon as coming_soon,
                custom_new_arrivals as new_arrivals,
                tag_color,
                tag_name
            FROM `tabItem`
            WHERE {where_clause} {search_condition}
            ORDER BY 
                CASE WHEN website_ranking IS NULL OR website_ranking = 0 THEN 1 ELSE 0 END,
                website_ranking ASC
            {limit_clause}
        """
        
        items = frappe.db.sql(query, tuple(filter_values), as_dict=True)

    if not items:
        return {"data": [], "total": total_count, "current_page": page or 1, "per_page": 30}

    item_ids = [p["id"] for p in items]

    # --- Batch Queries ---
    # Prices
    price_map = {}
    if check_customer_token():
        customer = get_customer_from_token()
        price_list = "Retail"
        if company == "Cotton Valley":
            price_list = frappe.get_value("Customer", customer, "price_list_for_cv") or "Retail"
        elif company == "UDC":
            price_list = frappe.get_value("Customer", customer, "price_list_for_udc") or "Retail"

        if not price_list:
            price_list = "Retail"
        
        price_data = frappe.db.sql("""
            SELECT item_code, price_list_rate
            FROM `tabItem Price`
            WHERE item_code in %s and price_list = %s
        """, (item_ids, price_list), as_dict=True)
        if len(price_data) > 0:
            price_map = {p["item_code"]: p["price_list_rate"] for p in price_data}
        else:
            price_data = frappe.db.sql("""
                SELECT item_code, price_list_rate
                FROM `tabItem Price`
                WHERE item_code in %s and price_list = %s
            """, (item_ids, "Retail"), as_dict=True)
            price_map = {p["item_code"]: p["price_list_rate"] for p in price_data}

    # Stock
    stock_data = frappe.db.sql("""
        SELECT item_code, SUM(actual_qty) as qty
        FROM `tabBin`
        WHERE item_code in %s
        GROUP BY item_code
    """, (item_ids,), as_dict=True)
    stock_map = {s["item_code"]: (s["qty"] if s["qty"] >= 0 else 0) for s in stock_data}

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
            default_price_data = frappe.db.sql("""
                SELECT item_code, price_list_rate
                FROM `tabItem Price`
                WHERE item_code = %s and price_list = %s
                LIMIT 1
            """, (product_id, "Retail"), as_dict=True)
            retail_price = default_price_data[0]["price_list_rate"] if default_price_data else 0
            customer_price = price_map.get(product_id, 0)

            product["price"] = customer_price if customer_price > 0 else retail_price
            product["sale_price"] = product["price"]
            product["discount"] = 0
        else:
            product["price"] = product["sale_price"] = product["discount"] = 0

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

        # --- Price Filter (List Support) ---
        if price:
            product_price = product["price"]
            price_match = False
            
            for price_filter in price:
                # Parse price filter format: "10" (below), "10-20" (range), "100" (above)
                if "-" in str(price_filter):
                    # Range filter: "10-20"
                    min_price, max_price = map(float, str(price_filter).split("-"))
                    if min_price <= product_price <= max_price:
                        price_match = True
                        break
                else:
                    # Single value - treat as "Below X"
                    price_value = float(price_filter)
                    if product_price <= price_value:
                        price_match = True
                        break
            
            if not price_match:
                continue

        # --- PCS Price Filter (List Support) ---
        if pcs_price:
            case_pack = product.get("case_pack", 1)
            # Convert case_pack to float/int if it's a string
            try:
                case_pack = float(case_pack) if case_pack else 1
            except (ValueError, TypeError):
                case_pack = 1
            
            if case_pack and case_pack > 0:
                pcs_product_price = product["price"] / case_pack
            else:
                pcs_product_price = 0
            
            pcs_price_match = False
            
            for pcs_filter in pcs_price:
                # Parse PCS price filter format
                if "-" in str(pcs_filter):
                    # Range filter: "1-2"
                    min_pcs_price, max_pcs_price = map(float, str(pcs_filter).split("-"))
                    if min_pcs_price <= pcs_product_price <= max_pcs_price:
                        pcs_price_match = True
                        break
                else:
                    # Single value - treat as "Below X"
                    pcs_price_value = float(pcs_filter)
                    if pcs_product_price <= pcs_price_value:
                        pcs_price_match = True
                        break
            
            if not pcs_price_match:
                continue


        # images
        product["product_thumbnail"] = get_file(product["product_thumbnail_id"])
        product["product_galleries"] = galleries_map.get(product_id, [])
        product["product_meta_image"] = get_file(product["product_thumbnail_id"])
        product["product_tags"] = frappe.get_all("Product Tags", filters={"parent": product_id}, fields=["idx", "name1", "color"])

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
        customer = get_customer_from_token()
        price_list = "Retail"
        if company == "Cotton Valley":
            price_list = frappe.get_value("Customer", customer, "price_list_for_cv")
        elif company == "UDC":
            price_list = frappe.get_value("Customer", customer, "price_list_for_udc")

        if not price_list:
            price_list = "Retail"

        price_data = frappe.db.sql("""
            SELECT price_list_rate
            FROM `tabItem Price`
            WHERE item_code = %s and price_list = %s
            LIMIT 1
        """, (product_id, price_list), as_dict=True)
        default_price_data = frappe.db.sql("""
            SELECT price_list_rate
            FROM `tabItem Price`
            WHERE item_code = %s and price_list = %s
            LIMIT 1
        """, (product_id, "Retail"), as_dict=True)
        if not price_data and default_price_data:
            price_data = default_price_data

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
    product["quantity"] = 0 if qty_data[0]["qty"] < 0 else qty_data[0]["qty"] if qty_data else 0
    if product["quantity"] > 0:
            product["stock_status"] = "in_stock"
    else:
        product["stock_status"] = "out_of_stock"

    product["related_products"] = frappe.get_all("Recommended Products", filters={"parent": product_id}, fields=["product_name"], pluck="product_name")
    product["trending_products"] = frappe.get_all("Item", filters={"custom_no_of_clicks": [">", 0], "company": company}, fields=["name"], pluck='name', order_by="custom_no_of_clicks desc", limit_page_length=4)

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
        category_list.append(get_category_list(cat.id, company)["data"][0] if get_category_list(cat.id, company)["data"] else {"id": cat.id, "name": cat.id, "slug": cat.id, "category_image": None, "banner_image": None, "products_count": 0, "subcategories": []})

    product["categories"] = category_list
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

    return product


@frappe.whitelist()
def get_prices(item_code, company="Cotton Valley"):
    url = ""
    username = ""
    password = ""
    company = "Cotton Valley" if not company or company == "null" else company
    if company == "Cotton Valley":
        url = f"https://erp.cottonvalley.us/ords/ctnvly_api/itmrate/rgnrate?ITMID={item_code}&INACTIVE_YN=N"
        username = CV_USER
        password = CV_PASSWORD
    elif company == "UDC":
        url = f"https://erp.universaldc.us/ords/unvdst_api/itmrate/rgnrate?ITMID={item_code}&INACTIVE_YN=N"
        username = UDC_USER
        password = UDC_PASSWORD
    response = requests.get(url, auth=(username, password))
    # Check if API responded successfully
    if response.status_code != 200:
        frappe.throw(f"API Error {response.status_code}: {response.text}")

    # Check if response is not empty and is JSON
    if not response.text.strip():
        frappe.throw("Empty response from API")

    try:
        data = response.json()
    except Exception:
        frappe.throw(f"Invalid JSON response: {response.text[:500]}")

    # print(data, "Data from API \n\n\n\n\n")  # Debugging line

    if not data.get("items"):
        return "No prices found"

    for item in data["items"]:
        region_name = item.get("rgnname")
        rate = item.get("rate")

        if not region_name or not rate or float(rate) <= 0:
            continue

        price_list = frappe.db.exists("Price List", region_name)
        if not price_list:
            continue


        existing = frappe.db.exists("Item Price", {
            "item_code": item_code,
            "price_list": price_list
        })

        if existing:
            ip = frappe.get_doc("Item Price", existing)
            ip.price_list_rate = float(rate)
            ip.save()
        else:
            frappe.get_doc({
                "doctype": "Item Price",
                "item_code": item_code,
                "price_list": price_list,
                "price_list_rate": float(rate),
                "currency": "USD"   # or your default currency
            }).insert()

    frappe.db.commit()
    return "Prices updated"


@frappe.whitelist()
def sync_item_from_api(item_code, company="Cotton Valley"):
    url = ""
    username = ""
    password = ""
    company = "Cotton Valley" if not company or company == "null" else company
    if company == "Cotton Valley":
        url = f"https://erp.cottonvalley.us/ords/ctnvly_api/itm/itmapi?ITMID={item_code}"
        username = CV_USER
        password = CV_PASSWORD
    elif company == "UDC":
        url = f"https://erp.universaldc.us/ords/unvdst_api/itm/itmapi?ITMID={item_code}"
        username = UDC_USER
        password = UDC_PASSWORD

    response = requests.get(url, auth=(username, password))
    # Check if API responded successfully
    if response.status_code != 200:
        frappe.throw(f"API Error {response.status_code}: {response.text}")

    # Check if response is not empty and is JSON
    if not response.text.strip():
        frappe.throw("Empty response from API")

    try:
        data = response.json()
    except Exception:
        frappe.throw(f"Invalid JSON response: {response.text[:500]}")

    if not data.get("items"):
        return "No item found"

    item_data = data["items"][0]

    # Check if item exists in ERPNext
    if not frappe.db.exists("Item", item_code):
        return f"Item {item_code} not found in ERPNext"

    item_doc = frappe.get_doc("Item", item_code)

    # Map and update relevant fields
    field_mapping = {
        "item_name": item_data.get("itmdsc"),
        # "item_group": item_data.get("itmgrpdsc") or "COD",
        "disabled": 1 if item_data.get("inactive_yn") == "Y" else 0,
        "custom_pallet_hi": float(item_data.get("pall_hi") or 0),
        "custom_pallet_ti": float(item_data.get("pall_ti") or 0),
        "custom_carton_upc": item_data.get("cart_upc"),
        "custom_cbm": float(item_data.get("casecbm") or 0),
        "custom_case_pack": int(item_data.get("itmpack") or 0),
    }

    updated = False
    for field, value in field_mapping.items():
        if value not in [None, "", 0, "0", "null"]:
            item_doc.set(field, value)
            updated = True

    if updated:
        item_doc.save(ignore_permissions=True)
        frappe.db.commit()

    # Update warehouse stock quantity
    qty_avlbl = item_data.get("qty_avlbl")
    if qty_avlbl not in [None, "", "null"]:
        qty_avlbl = float(item_data.get("qty_avlbl") or 0)
        warehouse = "Stores - CV" if company == "Cotton Valley" else "Stores - U"

        # Check if Bin exists for item and warehouse
        bin_exists = frappe.db.exists("Bin", {"item_code": item_code, "warehouse": warehouse})
        if bin_exists:
            bin_doc = frappe.get_doc("Bin", bin_exists)
            bin_doc.actual_qty = qty_avlbl
            bin_doc.save(ignore_permissions=True)
        else:
            frappe.get_doc({
                "doctype": "Bin",
                "item_code": item_code,
                "warehouse": warehouse,
                "actual_qty": qty_avlbl
            }).insert(ignore_permissions=True)

    frappe.db.commit()

    return f"Item {item_code} and warehouse quantity updated successfully"


CHUNK_SIZE = 500  # adjust as needed

@frappe.whitelist()
def get_product_prices():
    items = frappe.get_all("Item", pluck="name")
    total = len(items)
    frappe.logger().info(f"Starting price update for {total} items...")
    username = ""
    password = ""
    # Process in chunks
    for start in range(0, total, CHUNK_SIZE):
        batch = items[start:start + CHUNK_SIZE]
        frappe.logger().info(f"Processing items {start + 1} to {start + len(batch)}...")

        for item_code in batch:
            company = frappe.get_value("Item", item_code, "company")
            if company == "Cotton Valley":
                url = f"https://erp.cottonvalley.us/ords/ctnvly_api/itmrate/rgnrate?ITMID={item_code}&INACTIVE_YN=N"
                username = CV_USER
                password = CV_PASSWORD
            elif company == "UDC":
                url = f"https://erp.universaldc.us/ords/unvdst_api/itmrate/rgnrate?ITMID={item_code}&INACTIVE_YN=N"
                username = UDC_USER
                password = UDC_PASSWORD
            else:
                continue  # skip if company is not recognized
            try:
                response = requests.get(url, auth=(username, password), timeout=30)
                if response.status_code != 200:
                    frappe.logger().error(f"{item_code}: API Error {response.status_code}")
                    continue

                # Check if response is not empty and is JSON
                if not response.text.strip():
                    frappe.logger().warning(f"{item_code}: Empty response")
                    continue


                data = response.json()
                if not data.get("items"):
                    continue

                for item in data["items"]:
                    region_name = item.get("rgnname")
                    rate = item.get("rate")

                    if not region_name or not rate or float(rate) <= 0:
                        continue

                    price_list = frappe.db.exists("Price List", region_name)
                    if not price_list:
                        continue


                    existing = frappe.db.exists("Item Price", {
                        "item_code": item_code,
                        "price_list": price_list
                    })

                    if existing:
                        ip = frappe.get_doc("Item Price", existing)
                        ip.price_list_rate = float(rate)
                        ip.save()
                    else:
                        frappe.get_doc({
                            "doctype": "Item Price",
                            "item_code": item_code,
                            "price_list": price_list,
                            "price_list_rate": float(rate),
                            "currency": "USD"   # or your default currency
                        }).insert()

                frappe.db.commit()
            except Exception as e:
                frappe.logger().error(f"Error for {item_code}: {str(e)}")

        frappe.logger().info(f"Batch {start // CHUNK_SIZE + 1} completed.")
    return "All item prices updated successfully."



@frappe.whitelist()
def download_custom_catalog(items):
    try:
        # Parse the JSON string list of Item Names passed from JS
        if isinstance(items, str):
            item_names = json.loads(items)
        else:
            item_names = items
            
        # Validate input
        if not item_names or not isinstance(item_names, list):
            frappe.throw(_("Invalid items list provided"))
        
        # 1. Fetch Item Data
        data = frappe.get_all("Item", 
            filters={"name": ["in", item_names]},
            fields=["image", "item_code", "item_name", "custom_sub_category as subcategory",  
                    "custom_case_pack as case_pack", "custom_package_length_inch as case_length",
                    "custom_package_width_inch as case_width", "custom_package_height_inch as case_height",
                    "custom_weight_lbs as net_weight", "custom_case_per_pallet as cases_per_pallet",
                    "stock_price", "custom_carton_upc as item_upc", "custom_cbm as cbm", "available_stock"]
        )
        
        if not data:
            frappe.throw(_("No items found"))

        # 2. Setup Excel
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Catalog")

        # --- STYLES ---
        header_blue = workbook.add_format({'bg_color': '#9FC5E8', 'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        header_yellow = workbook.add_format({'bg_color': '#FFFF00', 'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        text_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        text_blue_fmt = workbook.add_format({'bg_color': '#9FC5E8', 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        price_fmt = workbook.add_format({'bg_color': '#FFFF00', 'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '$0.00'})
        company_header_fmt = workbook.add_format({'bold': True, 'font_size': 11, 'valign': 'vcenter'})
        company_info_fmt = workbook.add_format({'font_size': 16, 'valign': 'vcenter', 'bold': True})

        # --- COLUMN WIDTHS ---
        worksheet.set_column('A:A', 25)
        worksheet.set_column('B:B', 15)
        worksheet.set_column('C:C', 35)
        worksheet.set_column('D:J', 20)
        worksheet.set_column('K:K', 25)
        worksheet.set_column('L:M', 20)
        worksheet.set_column('N:N', 30)
        worksheet.set_column('O:Q', 20)

        # --- COMPANY HEADER ---
        worksheet.set_row(0, 60)
        worksheet.merge_range('A1:B1', '', None)
        
        # Add company logo if available
        logo_path = frappe.get_site_path("public", "files", "CottonValley_UDC_logo.jpg")
        if os.path.exists(logo_path):
            worksheet.insert_image('A1', logo_path, {'x_scale': 1, 'y_scale': 1, 'x_offset': 10, 'y_offset': 5})
        
        # Company information
        worksheet.write('A2', 'Universal Distribution LLC 326 APPLEGARTH ROAD MONROE, NJ 08831 | Cotton Valley LLC, 96 Distribution Blvd, Edison NJ 08817', company_info_fmt)
        worksheet.write('A3', '(732) 248 4276 | (732) 248-4276', company_info_fmt)
        worksheet.write('A4', ' info@universaldc.com | info@cottonvalley.net', company_info_fmt)
        worksheet.write('A5', 'universaldc.com | cottonValley.net', company_info_fmt)

        # --- HEADERS ---
        headers = [
            "Picture", "Code", "Description", "Category", "SubCategory", 
            "Master Case Pack", "Case-Length(INCH)",  "Case-Width(INCH)", 
            "Case-Height(INCH)", "Net-Weight(LBS)", "Cases/Pallet Trucking",
            "Price in Case", "Price in Piece", "Item UPC", "CBM", 
            "Available Stock", "Stock in Pieces"
        ]
        
        start_row = 10
        worksheet.set_row(start_row, 30)
        for col, title in enumerate(headers):
            fmt = header_yellow if col in [11, 12] else header_blue
            worksheet.write(start_row, col, title, fmt)

        # --- WRITE DATA ---
        row = start_row + 1
        
        for item in data:
            worksheet.set_row(row, 90)
            categories = frappe.db.sql("""
                SELECT c.product_category as id, pc.title as title
                FROM `tabProduct Categoris` c
                INNER JOIN `tabProduct Category` pc ON pc.name = c.product_category
                WHERE c.parent = %s
            """, (item.item_code,), as_dict=True)
            # A: Image Handling
            if item.get("image"):
                try:
                    file_name = item.image.split("/")[-1]
                    image_path = frappe.get_site_path("public", "files", file_name)

                    if os.path.exists(image_path):
                        # Get image dimensions to calculate proper scaling
                        from PIL import Image
                        img = Image.open(image_path)
                        img_width, img_height = img.size
                        
                        # Define target container size (in pixels)
                        target_width = 140
                        target_height = 90
                        
                        # Calculate scale to fit within container while maintaining aspect ratio
                        width_scale = target_width / img_width
                        height_scale = target_height / img_height
                        scale = min(width_scale, height_scale)  # Use smaller scale to fit within bounds
                        
                        # Calculate final dimensions
                        final_width = img_width * scale
                        final_height = img_height * scale
                        
                        # Calculate centering offsets
                        x_offset = 15 + (target_width - final_width) / 2
                        y_offset = 5 + (target_height - final_height) / 2
                        
                        worksheet.insert_image(row, 0, image_path, {
                            'x_scale': scale,
                            'y_scale': scale,
                            'x_offset': x_offset,
                            'y_offset': y_offset,
                            'object_position': 2,
                            'positioning': 1
                        })
                    else:
                        worksheet.write(row, 0, "No File", text_fmt)
                except Exception as e:
                    frappe.log_error(f"Image insert error: {str(e)}", "Catalog Image Error")
                    worksheet.write(row, 0, "Error", text_fmt)
            else:
                worksheet.write(row, 0, "", text_fmt)

            # B-H: Data columns
            subcategoryName = frappe.db.get_value("Product Subcategory", item.get("subcategory"), "title") if item.get("subcategory") else "-"

            worksheet.write(row, 1, item.get("item_code", "") or "-", text_fmt)
            worksheet.write(row, 2, item.get("item_name", "") or "-", text_fmt)
            worksheet.write(row, 3, str(categories[0].title) or "-", text_fmt)  # Category placeholder
            worksheet.write(row, 4, subcategoryName or "-", text_fmt)
            worksheet.write(row, 5, item.get("case_pack", "") or "-", text_fmt)
            worksheet.write(row, 6, item.get("case_length", "") or "-", text_blue_fmt)
            worksheet.write(row, 7, item.get("case_width", "") or "-", text_blue_fmt)
            worksheet.write(row, 8, item.get("case_height", "") or "-", text_blue_fmt)
            worksheet.write(row, 9, item.get("net_weight", "") or "-", text_blue_fmt)
            worksheet.write(row, 10, item.get("cases_per_pallet", "") or "-", text_blue_fmt)
            worksheet.write(row, 11, (flt(item.get("stock_price", 0)) or 1), price_fmt)
            worksheet.write(row, 12, (flt(item.get("stock_price", 0) or 1) / flt(item.get("case_pack", 1) or 1)), price_fmt)
            worksheet.write(row, 13, item.get("item_upc", "") or "-", text_fmt)
            worksheet.write(row, 14, item.get("cbm", "") or "-", text_fmt)
            worksheet.write(row, 15, item.get("available_stock", "") or "-", text_fmt)
            worksheet.write(row, 16, (flt(item.get("available_stock", 0) or 0) * flt(item.get("case_pack", 1) or 1)), text_fmt)
            row += 1

        workbook.close()
        output.seek(0)

        # --- PROPER FRAPPE RESPONSE FOR DOWNLOAD ---
        file_content = output.read()
        filename = f'Catalog_{frappe.utils.today()}.xlsx'
        
        frappe.local.response.filename = filename
        frappe.local.response.filecontent = file_content
        frappe.local.response.type = "download"
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Catalog Download Error")
        frappe.throw(_("Error generating catalog: {0}").format(str(e)))
