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
def get_product_types_with_count(category=None, subcategory=None, company=None):
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
def get_product_ids(search=None, company=None):
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
def get_all_products(ids=None, category=None, subcategory=None, brand=None, sortBy=None, search=None, page=None, attribute=None, producttype=None, company=None, price=None, pcs_price=None):
    category = None if not category or category == "null" else get_categories_from_string(category)
    subcategory = None if not subcategory or subcategory == "null" else get_categories_from_string(subcategory)
    attribute = None if not attribute or attribute == "null" else get_categories_from_string(attribute)
    producttype = None if not producttype or producttype == "null" else get_categories_from_string(producttype)
    sortBy = None if not sortBy or sortBy == "null" else sortBy
    search = None if not search or search == "null" else search
    page = None if not page or page == "null" else int(page)
    ids = None if not ids or ids == "null" else get_categories_from_string(ids)
    company = "Cotton Valley" if not company or company == "null" else company
    brand = None if not brand or brand == "null" else get_categories_from_string(brand)
    price = None if not price or price == "null" else get_categories_from_string(price)
    pcs_price = None if not pcs_price or pcs_price == "null" else get_categories_from_string(pcs_price)

    filters = {"disabled": 0}  # only active products

    if ids:
        filters["name"] = ["in", ids]

    if company:
        filters["company"] = company

    if producttype:
        filters["item_group"] = ["in", producttype]

    if brand:
        filters["brand"] = ["in", brand]

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
    # --- Stock Filter ---
    if attribute:
        if attribute == ["in_stock"]:
            filters["threshold_stock"] = [">", 0]
        if attribute == ["out_stock"]:
            filters["threshold_stock"] = ["<=", 0]

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
    # Note: "low-high" and "high-low" require special handling as price is in Item Price table
    sort_clause = {
        "asc": "creation asc",
        "desc": "creation desc",
        "a-z": "item_name asc",
        "z-a": "item_name desc",
    }.get(sortBy, None)  # default sort handled separately
    
    # Flag to indicate price-based sorting
    price_sort = sortBy in ["low-high", "high-low"]
    price_sort_direction = "ASC" if sortBy == "low-high" else "DESC" if sortBy == "high-low" else None

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

    
    in_stock_count = 0
    out_of_stock_count = 0
    if search:
        # For search, we need to count in-stock and out-of-stock separately
        stock_data = frappe.db.sql("""
            SELECT 
                SUM(CASE WHEN threshold_stock > 0 THEN 1 ELSE 0 END) as in_stock,
                SUM(CASE WHEN threshold_stock <= 0 THEN 1 ELSE 0 END) as out_of_stock
            FROM `tabItem`
            WHERE item_name LIKE %s OR item_code LIKE %s
        """, (f"%{search}%", f"%{search}%"), as_dict=True)
        if stock_data:
            in_stock_count = stock_data[0]["in_stock"] or 0
            out_of_stock_count = stock_data[0]["out_of_stock"] or 0
    else:
        # For non-search, we can use the filters directly
        in_stock_filters = filters.copy()
        in_stock_filters["threshold_stock"] = [">", 0]
        in_stock_count = frappe.db.count("Item", filters=in_stock_filters)

        out_of_stock_filters = filters.copy()
        out_of_stock_filters["threshold_stock"] = ["<=", 0]
        out_of_stock_count = frappe.db.count("Item", filters=out_of_stock_filters)

    # --- Pagination ---
    limit_start = (page - 1) * 30 if page and page > 0 else None
    limit_page_length = 30 if page else None
    
    # --- Common field definitions (reusable) ---
    ITEM_FIELDS = """
        name as id,
        item_name as name,
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
        tag_name,
        threshold_stock as stock
    """.strip()
    
    ITEM_FIELDS_LIST = [
        "name as id",
        "item_name as name",
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
        "tag_name",
        "threshold_stock as stock"
    ]
    
    # --- Helper function to build filter conditions ---
    def build_filter_conditions(table_alias=""):
        """Build SQL filter conditions and values."""
        prefix = f"{table_alias}." if table_alias else ""
        conditions = []
        values = []
        
        if ids:
            conditions.append(f"{prefix}name IN %s")
            values.append(ids)
        
        if company:
            conditions.append(f"{prefix}company = %s")
            values.append(company)
        
        if producttype:
            conditions.append(f"{prefix}item_group IN %s")
            values.append(producttype)

        if category:
            cat_product_ids = frappe.db.sql("""
                SELECT DISTINCT it.name
                FROM `tabItem` it
                INNER JOIN `tabProduct Categoris` c ON c.parent = it.name
                WHERE c.product_category IN %s
            """, (category,), as_dict=True)
            cat_product_ids = [p["name"] for p in cat_product_ids]
            if not cat_product_ids:
                return None, None  # Signal no products found
            conditions.append(f"{prefix}name IN %s")
            values.append(cat_product_ids)

        if subcategory:
            conditions.append(f"{prefix}custom_sub_category IN %s")
            values.append(subcategory)

        if brand:
            conditions.append(f"{prefix}brand IN %s")
            values.append(brand)

        if attribute:
            if attribute == ["in_stock"]:
                conditions.append(f"{prefix}threshold_stock > 0")
            elif attribute == ["out_stock"]:
                conditions.append(f"{prefix}threshold_stock <= 0")
        
        conditions.append(f"{prefix}disabled = 0")
        
        return conditions, values
    
    # --- Helper function to build limit clause ---
    def build_limit_clause():
        if limit_start is not None and limit_page_length:
            return f"LIMIT {limit_start}, {limit_page_length}"
        elif limit_page_length:
            return f"LIMIT {limit_page_length}"
        return ""
    
    # --- Determine price list for price-based sorting ---
    sort_price_list = "Retail"
    if price_sort and check_customer_token():
        customer = get_customer_from_token()
        if company == "Cotton Valley":
            sort_price_list = frappe.get_value("Customer", customer, "price_list_for_cv") or "Retail"
        elif company == "UDC":
            sort_price_list = frappe.get_value("Customer", customer, "price_list_for_udc") or "Retail"
    
    # --- Fetch items based on sort type ---
    items = []
    
    if sort_clause:
        # Standard sorting (asc, desc, a-z, z-a)
        items = frappe.get_all(
            "Item",
            filters=filters,
            or_filters=or_filters,
            fields=ITEM_FIELDS_LIST,
            order_by=sort_clause,
            limit_start=limit_start,
            limit_page_length=limit_page_length
        )
    else:
        # Build conditions for raw SQL queries (price sort or default sort)
        table_alias = "i" if price_sort else ""
        filter_conditions, filter_values = build_filter_conditions(table_alias)
        
        # Check if category filter returned no products
        if filter_conditions is None:
            return {"data": [], "total": 0}
        
        # Add search condition
        search_condition = ""
        if search:
            prefix = "i." if price_sort else ""
            search_condition = f"AND ({prefix}item_name LIKE %s OR {prefix}name LIKE %s)"
            filter_values.extend([f"%{search}%", f"%{search}%"])
        
        where_clause = " AND ".join(filter_conditions)
        limit_clause = build_limit_clause()
        
        if price_sort:
            # Price-based sorting - requires JOIN with Item Price table
            # Insert price_list at the beginning since it's used in the JOIN clause (before WHERE)
            filter_values.insert(0, sort_price_list)
            
            # Use table alias for all fields
            fields_with_alias = ", ".join([f"i.{f.split(' as ')[0].strip()} as {f.split(' as ')[1].strip()}" 
                                           if ' as ' in f else f"i.{f}" 
                                           for f in ITEM_FIELDS.split(",\n")])
            
            query = f"""
                SELECT 
                    i.name as id,
                    i.item_name as name,
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
                    i.tag_color,
                    i.tag_name,
                    i.threshold_stock as stock,
                    COALESCE(ip.price_list_rate, 0) as sort_price
                FROM `tabItem` i
                LEFT JOIN `tabItem Price` ip ON ip.item_code = i.name AND ip.price_list = %s
                WHERE {where_clause} {search_condition}
                ORDER BY 
                    CASE WHEN ip.price_list_rate IS NULL OR ip.price_list_rate = 0 THEN 1 ELSE 0 END,
                    ip.price_list_rate {price_sort_direction}
                {limit_clause}
            """
        else:
            # Default sort with website_ranking - null/0 values last
            query = f"""
                SELECT {ITEM_FIELDS}
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
    # stock_data = frappe.db.sql("""
    #     SELECT item_code, SUM(actual_qty) as qty
    #     FROM `tabBin`
    #     WHERE item_code in %s
    #     GROUP BY item_code
    # """, (item_ids,), as_dict=True)
    # stock_map = {s["item_code"]: (s["qty"] if s["qty"] >= 0 else 0) for s in stock_data}

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
        # qty = stock_map.get(product_id, 0)
        qty = product.get("stock", 0)

        product["quantity"] = qty
        product["stock_status"] = "in_stock" if qty > 0 else "out_of_stock"

        # Stock Filter
        # if attribute:
        #     if attribute == ["in_stock"] and qty <= 0:
        #         continue
        #     if attribute == ["out_stock"] and qty > 0:
        #         continue

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
        product["product_tags"] = frappe.get_all("Product Tags", filters={"parent": product_id}, fields=["idx", "name1", "color"], order_by="idx asc")

        products.append(product)

    product_showing = page * 30 if page and page > 0 else total_count
    from_showing = (product_showing - 30) + 1 if page and page > 0 else 1
    return {
        "data": products, 
        "total": total_count, 
        "from": from_showing, 
        "to": product_showing, 
        "current_page": page or 1, 
        "per_page": limit_page_length or total_count, 
        "in_stock_count": in_stock_count,
        "out_of_stock_count": out_of_stock_count
    }


@frappe.whitelist(allow_guest=True)
def get_product(product_id, company=None):
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
            "custom_new_arrivals as new_arrivals",
            "threshold_stock as stock",
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
        else:
            price_list = frappe.get_value("Customer", customer, "price_list_for_cv")

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
    # qty_data = frappe.db.sql("""
    #     SELECT COALESCE(SUM(actual_qty), 0) as qty
    #     FROM `tabBin`
    #     WHERE item_code = %s
    # """, (product_id,), as_dict=True)
    # product["quantity"] = 0 if qty_data[0]["qty"] < 0 else qty_data[0]["qty"] if qty_data else 0
    product["quantity"] = product.get("stock", 0)

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
    product["meta_title"] = product["name"]
    product["meta_description"] = product["short_description"]
    product["product_meta_image"] = get_file(product["product_thumbnail_id"])
    product["product_tags"] = frappe.get_all("Product Tags", filters={"parent": product_id}, fields=["idx", "name1", "color"], order_by="idx asc")

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
def get_prices(item_code, company=None):
    """
    Fetch and update item prices from external API.
    Returns success message or raises exception on critical errors.
    """
    try:
        # Validate inputs
        if not item_code:
            frappe.throw("Item code is required")
        
        company = "Cotton Valley" if not company or company == "null" else company
        
        # Configure API endpoint based on company
        url = ""
        username = ""
        password = ""
        
        if company == "Cotton Valley":
            url = f"https://erp.cottonvalley.us/ords/ctnvly_api/itmrate/rgnrate?ITMID={item_code}&INACTIVE_YN=N"
            username = CV_USER
            password = CV_PASSWORD
        elif company == "UDC":
            url = f"https://erp.universaldc.us/ords/unvdst_api/itmrate/rgnrate?ITMID={item_code}&INACTIVE_YN=N"
            username = UDC_USER
            password = UDC_PASSWORD
        else:
            frappe.throw(f"Invalid company: {company}")
        
        # Make API request with timeout
        try:
            response = requests.get(url, auth=(username, password), timeout=30)
        except requests.exceptions.Timeout:
            frappe.throw(f"API request timed out for item {item_code}")
        except requests.exceptions.ConnectionError:
            frappe.throw(f"Failed to connect to API for item {item_code}")
        except requests.exceptions.RequestException as e:
            frappe.throw(f"API request failed: {str(e)}")
        
        # Check if API responded successfully
        if response.status_code != 200:
            frappe.throw(f"API Error {response.status_code}: {response.text}")

        # Check if response is not empty and is JSON
        if not response.text.strip():
            frappe.throw("Empty response from API")

        try:
            data = response.json()
        except Exception as e:
            frappe.throw(f"Invalid JSON response: {response.text[:500]}")

        if not data.get("items"):
            return "No prices found"

        # Track processing results
        updated_count = 0
        created_count = 0
        skipped_count = 0
        errors = []

        for item in data["items"]:
            try:
                region_name = item.get("rgnname")
                rate = item.get("rate")

                # Validate item data
                if not region_name or not rate:
                    skipped_count += 1
                    continue
                
                try:
                    rate_float = float(rate)
                    if rate_float <= 0:
                        skipped_count += 1
                        continue
                except (ValueError, TypeError):
                    errors.append(f"Invalid rate value for region {region_name}: {rate}")
                    skipped_count += 1
                    continue

                # Check if price list exists
                price_list = frappe.db.exists("Price List", region_name)
                if not price_list:
                    skipped_count += 1
                    continue

                # Check if Item Price already exists
                existing = frappe.db.exists("Item Price", {
                    "item_code": item_code,
                    "price_list": price_list
                })

                try:
                    if existing:
                        # Update existing price
                        ip = frappe.get_doc("Item Price", existing)
                        ip.price_list_rate = rate_float
                        ip.save(ignore_permissions=True)
                        updated_count += 1
                    else:
                        # Create new price
                        frappe.get_doc({
                            "doctype": "Item Price",
                            "item_code": item_code,
                            "price_list": price_list,
                            "price_list_rate": rate_float,
                            "currency": "USD"
                        }).insert(ignore_permissions=True)
                        created_count += 1
                except Exception as e:
                    error_msg = f"Failed to save price for {region_name}: {str(e)}"
                    errors.append(error_msg)
                    frappe.log_error(error_msg, f"Price Update Error - {item_code}")
                    continue

            except Exception as e:
                error_msg = f"Error processing item in loop: {str(e)}"
                errors.append(error_msg)
                frappe.log_error(error_msg, f"Price Processing Error - {item_code}")
                continue

        # Commit all changes
        try:
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"Failed to commit price changes for {item_code}: {str(e)}", "Price Commit Error")
            frappe.throw(f"Failed to save price changes: {str(e)}")

        # Build response message
        message_parts = []
        if updated_count > 0:
            message_parts.append(f"{updated_count} updated")
        if created_count > 0:
            message_parts.append(f"{created_count} created")
        if skipped_count > 0:
            message_parts.append(f"{skipped_count} skipped")
        
        result = f"Prices: {', '.join(message_parts)}" if message_parts else "No prices updated"
        
        if errors:
            frappe.log_error("\n".join(errors), f"Price Update Warnings - {item_code}")
            result += f" ({len(errors)} errors logged)"
        
        return result

    except Exception as e:
        # Log unexpected errors
        frappe.log_error(f"Unexpected error in get_prices for {item_code}: {str(e)}", "Price Update Critical Error")
        raise


@frappe.whitelist()
def sync_item_from_api(item_code, company=None):
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
        "custom_upc": item_data.get("itm_chr2"),
        "custom_cbm": float(item_data.get("casecbm") or 0),
        "custom_case_pack": int(item_data.get("itmpack") or 0),
        "custom_case_per_pallet": int(item_data.get("pall_case") or 0),
        "custom_case_trucking": int(item_data.get("pall_case_tr") or 0),
        "custom_short_description": item_data.get("itmdscpur"),
        "custom_package_length_inch": float(item_data.get("casesizlen") or 0),
        "custom_package_width_inch": float(item_data.get("casesizwid") or 0),
        "custom_package_height_inch": float(item_data.get("casesizthk") or 0),
        "custom_weight_lbs": float(item_data.get("casewt") or 0),
    }

    updated = False
    for field, value in field_mapping.items():
        try:
            if value not in [None, "", 0, "0", "null"]:
                item_doc.set(field, value)
                updated = True
            else:
                # Log to Item Value Updates if value is not set
                frappe.get_doc({
                    "doctype": "Item Value Updates",
                    "item_code": item_code,
                    "company": company,
                    "title": f"{item_code} - {field}",
                    "message": f"Value not updated: {value!r} is invalid or empty"
                }).insert(ignore_permissions=True)
        except Exception as e:
            # Log to Item Value Updates if set fails
            frappe.get_doc({
                "doctype": "Item Value Updates",
                "item_code": item_code,
                "company": company,
                "title": f"{item_code} - {field}",
                "message": f"Failed to update: {str(e)}"
            }).insert(ignore_permissions=True)

    # Handle category synchronization based on itmclsid (ERP ID)
    itmclsid = item_data.get("itmclsid")
    itmclsdsc = item_data.get("itmclsdsc")
    
    if itmclsid:
        # Check if category with this ERP ID exists
        category = frappe.db.get_value(
            "Product Category",
            {"erp_id": itmclsid, "company": company},
            ["name", "title"],
            as_dict=True
        )
        
        if category:
            # Category exists - update title if needed and different
            if itmclsdsc and itmclsdsc != category.get("title"):
                frappe.db.set_value("Product Category", category.get("name"), "title", itmclsdsc)
                updated = True
            
            # Check if item already has this category
            existing_category = frappe.db.exists("Product Categoris", {
                "parent": item_code,
                "product_category": category.get("name")
            })
            
            if not existing_category:
                # Add category to item
                try:
                    item_doc.custom_product_categories = []
                    item_doc.append("custom_product_categories", {
                        "product_category": category.get("name")
                    })
                    updated = True
                except AttributeError as e:
                    frappe.log_error("Category Append Error", f"Failed to append category for item {item_code}: {str(e)}. Field 'custom_product_categories' may not exist.")
        else:
            # Category doesn't exist - show the error
            frappe.msgprint(f"Category with ERP ID {itmclsid} not found. Please create it first.")

    # Handle subcategory synchronization based on itmctgid (ERP ID)
    itmctgid = item_data.get("itmctgid")
    itmctgdsc = item_data.get("itmctgdsc")
    
    if itmctgid:
        # Check if subcategory with this ERP ID exists
        subcategory = frappe.db.get_value(
            "Product Subcategory",
            {"erp_id": itmctgid, "company": company},
            ["name", "title"],
            as_dict=True
        )
        
        if subcategory:
            # Subcategory exists - update title if needed and different
            if itmctgdsc and itmctgdsc != subcategory.get("title"):
                frappe.db.set_value("Product Subcategory", subcategory.get("name"), "title", itmctgdsc)
                updated = True
            
            # Update item's subcategory field
            try:
                if item_doc.custom_sub_category != subcategory.get("name"):
                    item_doc.custom_sub_category = subcategory.get("name")
                    updated = True
            except AttributeError as e:
                frappe.log_error(f"Failed to set subcategory for item {item_code}: {str(e)}. Field 'custom_sub_category' may not exist.", "Subcategory Update Error")
        else:
            # Subcategory doesn't exist - show the error
            frappe.msgprint(f"Subcategory with ERP ID {itmctgid} not found. Please create it first.")

    if updated:
        item_doc.save(ignore_permissions=True)
        frappe.db.commit()

    # Update warehouse stock quantity - prefer stk_qty, fallback to qty_avlbl
    qty_avlbl = item_data.get("qty_avlbl")
    
    # Use stk_qty if available, otherwise use qty_avlbl
    qty_avlbl = qty_avlbl if qty_avlbl not in [None, "", "null"] else 0
    
    if qty_avlbl not in [None, "", "null"]:
        try:
            qty_avlbl = qty_avlbl or 0
        except (ValueError, TypeError) as e:
            frappe.log_error(f"Invalid stock quantity value '{qty_avlbl}' for item {item_code}: {str(e)}", "Stock Qty Conversion Error")
            qty_avlbl = 0
        
        warehouse = "Stores - CV" if company == "Cotton Valley" else "Stores - U"

        try:
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
        except Exception as e:
            frappe.log_error(f"Failed to update Bin for item {item_code}, warehouse {warehouse}: {str(e)}", "Bin Update Error")
        
        try:
            item_available_qty = frappe.db.get_value("Item", item_code, "available_stock")
            item_threshold_stock = frappe.db.get_value("Item", item_code, "threshold_stock")
            if item_available_qty == item_threshold_stock:
                frappe.db.set_value("Item", item_code, "threshold_stock", qty_avlbl or 0)
            frappe.db.set_value("Item", item_code, "available_stock", qty_avlbl)
        except Exception as e:
            frappe.log_error(f"Failed to update Item stock fields for {item_code}: {str(e)}", "Item Stock Update Error")

    frappe.db.commit()

    return f"Item {item_code} and warehouse quantity updated successfully"


CHUNK_SIZE = 200  # adjust as needed


@frappe.whitelist()
def scheduler_sync_cv_items_from_api():
    """Sync items from Cotton Valley API"""
    company = "Cotton Valley"
    items = frappe.get_all("Item", filters={"company": company}, pluck="name")
    total = len(items)
    url_base = "https://erp.cottonvalley.us/ords/ctnvly_api/itm/itmapi?ITMID="
    username = CV_USER
    password = CV_PASSWORD
    warehouse = "Stores - CV"
    error_list = []
    processed_count = 0

    for start in range(0, total, CHUNK_SIZE):
        batch = items[start:start + CHUNK_SIZE]
        frappe.log_error("Processing CV", f"Processing CV items {start + 1} to {start + len(batch)}...")

        for item_code in batch:
            try:
                url = f"{url_base}{item_code}"
                response = requests.get(url, auth=(username, password), timeout=30)
                if response.status_code != 200:
                    error_msg = f"API Error {response.status_code}: {response.text}"
                    frappe.log_error(error_msg, f"CV Item: {item_code}")
                    error_list.append({"item_code": item_code, "error": error_msg})
                    continue

                if not response.text.strip():
                    error_msg = "Empty response from API"
                    frappe.log_error(error_msg, f"CV Item: {item_code}")
                    error_list.append({"item_code": item_code, "error": error_msg})
                    continue

                try:
                    data = response.json()
                except Exception as e:
                    error_msg = f"Invalid JSON response: {response.text[:500]}"
                    frappe.log_error(error_msg, f"CV Item: {item_code}")
                    error_list.append({"item_code": item_code, "error": error_msg})
                    continue

                if not data.get("items"):
                    error_msg = "No item found in API response"
                    frappe.log_error(error_msg, f"CV Item: {item_code}")
                    error_list.append({"item_code": item_code, "error": error_msg})
                    continue

                item_data = data["items"][0]

                if not frappe.db.exists("Item", item_code):
                    error_msg = f"Item {item_code} not found in ERPNext"
                    frappe.log_error(error_msg, f"CV Item: {item_code}")
                    error_list.append({"item_code": item_code, "error": error_msg})
                    continue

                item_doc = frappe.get_doc("Item", item_code)

                field_mapping = {
                    "item_name": item_data.get("itmdsc"),
                    "disabled": 1 if item_data.get("inactive_yn") == "Y" else 0,
                    "custom_pallet_hi": float(item_data.get("pall_hi") or 0),
                    "custom_pallet_ti": float(item_data.get("pall_ti") or 0),
                    "custom_carton_upc": item_data.get("cart_upc"),
                    "custom_upc": item_data.get("itm_chr2"),
                    "custom_cbm": float(item_data.get("casecbm") or 0),
                    "custom_case_pack": int(item_data.get("itmpack") or 0),
                    "custom_case_per_pallet": int(item_data.get("pall_case") or 0),
                    "custom_case_trucking": int(item_data.get("pall_case_tr") or 0),
                    "custom_short_description": item_data.get("itmdscpur"),
                    "custom_package_length_inch": float(item_data.get("casesizlen") or 0),
                    "custom_package_width_inch": float(item_data.get("casesizwid") or 0),
                    "custom_package_height_inch": float(item_data.get("casesizthk") or 0),
                    "custom_weight_lbs": float(item_data.get("casewt") or 0),
                }

                updated = False
                for field, value in field_mapping.items():
                    try:
                        if value not in [None, "", 0, "0", "null"]:
                            item_doc.set(field, value)
                            updated = True
                        else:
                            frappe.get_doc({
                                "doctype": "Item Value Updates",
                                "item_code": item_code,
                                "company": company,
                                "title": f"{item_code} - {field}",
                                "message": f"Value not updated: {value!r} is invalid or empty"
                            }).insert(ignore_permissions=True)
                    except Exception as e:
                        frappe.get_doc({
                            "doctype": "Item Value Updates",
                            "item_code": item_code,
                            "company": company,
                            "title": f"{item_code} - {field}",
                            "message": f"Failed to update: {str(e)}"
                        }).insert(ignore_permissions=True)

                itmclsid = item_data.get("itmclsid")
                itmclsdsc = item_data.get("itmclsdsc")
                if itmclsid:
                    category = frappe.db.get_value(
                        "Product Category",
                        {"erp_id": itmclsid, "company": company},
                        ["name", "title"],
                        as_dict=True
                    )
                    if category:
                        if itmclsdsc and itmclsdsc != category.get("title"):
                            frappe.db.set_value("Product Category", category.get("name"), "title", itmclsdsc)
                            updated = True
                        existing_category = frappe.db.exists("Product Categoris", {
                            "parent": item_code,
                            "product_category": category.get("name")
                        })
                        if not existing_category:
                            item_doc.custom_product_categories = []
                            item_doc.append("custom_product_categories", {
                                "product_category": category.get("name")
                            })
                            updated = True
                    else:
                        error_msg = f"Category with ERP ID {itmclsid} not found. Please create it first."
                        frappe.log_error(error_msg, f"CV Item: {item_code}")
                        error_list.append({"item_code": item_code, "error": error_msg})

                itmctgid = item_data.get("itmctgid")
                itmctgdsc = item_data.get("itmctgdsc")
                if itmctgid:
                    subcategory = frappe.db.get_value(
                        "Product Subcategory",
                        {"erp_id": itmctgid, "company": company},
                        ["name", "title"],
                        as_dict=True
                    )
                    if subcategory:
                        if itmctgdsc and itmctgdsc != subcategory.get("title"):
                            frappe.db.set_value("Product Subcategory", subcategory.get("name"), "title", itmctgdsc)
                            updated = True
                        if item_doc.custom_sub_category != subcategory.get("name"):
                            item_doc.custom_sub_category = subcategory.get("name")
                            updated = True
                    else:
                        error_msg = f"Subcategory with ERP ID {itmctgid} not found. Please create it first."
                        frappe.log_error(error_msg, f"CV Item: {item_code}")
                        error_list.append({"item_code": item_code, "error": error_msg})

                if updated:
                    item_doc.save(ignore_permissions=True)
                    frappe.db.commit()

                qty_avlbl = item_data.get("qty_avlbl")
                if qty_avlbl not in [None, "", "null"]:
                    qty_avlbl = int(float(item_data.get("qty_avlbl") or 0))
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
                    item_available_qty = frappe.db.get_value("Item", item_code, "available_stock")
                    item_threshold_stock = frappe.db.get_value("Item", item_code, "threshold_stock")
                    if item_available_qty == item_threshold_stock:
                        frappe.db.set_value("Item", item_code, "threshold_stock", qty_avlbl)
                    frappe.db.set_value("Item", item_code, "available_stock", qty_avlbl)

                frappe.db.commit()
                processed_count += 1
            except Exception as e:
                error_msg = f"Unhandled error for item {item_code}: {str(e)}"
                frappe.log_error(error_msg, f"CV Item: {item_code}")
                error_list.append({"item_code": item_code, "error": error_msg})
                continue

    summary = f"CV Sync - Processed: {processed_count}, Errors: {len(error_list)}"
    if error_list:
        frappe.log_error(str(error_list), "sync_cv_items_from_api error details")
    return summary


@frappe.whitelist()
def scheduler_sync_udc_items_from_api():
    """Sync items from UDC API"""
    items = frappe.get_all("Item", filters={"company": "UDC"}, pluck="name")
    total = len(items)
    company = "UDC"
    url_base = "https://erp.universaldc.us/ords/unvdst_api/itm/itmapi?ITMID="
    username = UDC_USER
    password = UDC_PASSWORD
    warehouse = "Stores - U"
    error_list = []
    processed_count = 0

    for start in range(0, total, CHUNK_SIZE):
        batch = items[start:start + CHUNK_SIZE]
        frappe.log_error("Processing UDC", f"Processing UDC items {start + 1} to {start + len(batch)}...")

        for item_code in batch:
            try:
                url = f"{url_base}{item_code}"
                response = requests.get(url, auth=(username, password), timeout=30)
                if response.status_code != 200:
                    error_msg = f"API Error {response.status_code}: {response.text}"
                    frappe.log_error(error_msg, f"UDC Item: {item_code}")
                    error_list.append({"item_code": item_code, "error": error_msg})
                    continue

                if not response.text.strip():
                    error_msg = "Empty response from API"
                    frappe.log_error(error_msg, f"UDC Item: {item_code}")
                    error_list.append({"item_code": item_code, "error": error_msg})
                    continue

                try:
                    data = response.json()
                except Exception as e:
                    error_msg = f"Invalid JSON response: {response.text[:500]}"
                    frappe.log_error(error_msg, f"UDC Item: {item_code}")
                    error_list.append({"item_code": item_code, "error": error_msg})
                    continue

                if not data.get("items"):
                    error_msg = "No item found in API response"
                    frappe.log_error(error_msg, f"UDC Item: {item_code}")
                    error_list.append({"item_code": item_code, "error": error_msg})
                    continue

                item_data = data["items"][0]

                if not frappe.db.exists("Item", item_code):
                    error_msg = f"Item {item_code} not found in ERPNext"
                    frappe.log_error(error_msg, f"UDC Item: {item_code}")
                    error_list.append({"item_code": item_code, "error": error_msg})
                    continue

                item_doc = frappe.get_doc("Item", item_code)

                field_mapping = {
                    "item_name": item_data.get("itmdsc"),
                    "disabled": 1 if item_data.get("inactive_yn") == "Y" else 0,
                    "custom_pallet_hi": float(item_data.get("pall_hi") or 0),
                    "custom_pallet_ti": float(item_data.get("pall_ti") or 0),
                    "custom_carton_upc": item_data.get("cart_upc"),
                    "custom_upc": item_data.get("itm_chr2"),
                    "custom_cbm": float(item_data.get("casecbm") or 0),
                    "custom_case_pack": int(item_data.get("itmpack") or 0),
                    "custom_case_per_pallet": int(item_data.get("pall_case") or 0),
                    "custom_case_trucking": int(item_data.get("pall_case_tr") or 0),
                    "custom_short_description": item_data.get("itmdscpur"),
                    "custom_package_length_inch": float(item_data.get("casesizlen") or 0),
                    "custom_package_width_inch": float(item_data.get("casesizwid") or 0),
                    "custom_package_height_inch": float(item_data.get("casesizthk") or 0),
                    "custom_weight_lbs": float(item_data.get("casewt") or 0),
                }

                updated = False
                for field, value in field_mapping.items():
                    try:
                        if value not in [None, "", 0, "0", "null"]:
                            item_doc.set(field, value)
                            updated = True
                        else:
                            frappe.get_doc({
                                "doctype": "Item Value Updates",
                                "item_code": item_code,
                                "company": company,
                                "title": f"{item_code} - {field}",
                                "message": f"Value not updated: {value!r} is invalid or empty"
                            }).insert(ignore_permissions=True)
                    except Exception as e:
                        frappe.get_doc({
                            "doctype": "Item Value Updates",
                            "item_code": item_code,
                            "company": company,
                            "title": f"{item_code} - {field}",
                            "message": f"Failed to update: {str(e)}"
                        }).insert(ignore_permissions=True)

                itmclsid = item_data.get("itmclsid")
                itmclsdsc = item_data.get("itmclsdsc")
                if itmclsid:
                    category = frappe.db.get_value(
                        "Product Category",
                        {"erp_id": itmclsid, "company": company},
                        ["name", "title"],
                        as_dict=True
                    )
                    if category:
                        if itmclsdsc and itmclsdsc != category.get("title"):
                            frappe.db.set_value("Product Category", category.get("name"), "title", itmclsdsc)
                            updated = True
                        existing_category = frappe.db.exists("Product Categoris", {
                            "parent": item_code,
                            "product_category": category.get("name")
                        })
                        if not existing_category:
                            item_doc.custom_product_categories = []
                            item_doc.append("custom_product_categories", {
                                "product_category": category.get("name")
                            })
                            updated = True
                    else:
                        error_msg = f"Category with ERP ID {itmclsid} not found. Please create it first."
                        frappe.log_error(error_msg, f"UDC Item: {item_code}")
                        error_list.append({"item_code": item_code, "error": error_msg})

                itmctgid = item_data.get("itmctgid")
                itmctgdsc = item_data.get("itmctgdsc")
                if itmctgid:
                    subcategory = frappe.db.get_value(
                        "Product Subcategory",
                        {"erp_id": itmctgid, "company": company},
                        ["name", "title"],
                        as_dict=True
                    )
                    if subcategory:
                        if itmctgdsc and itmctgdsc != subcategory.get("title"):
                            frappe.db.set_value("Product Subcategory", subcategory.get("name"), "title", itmctgdsc)
                            updated = True
                        if item_doc.custom_sub_category != subcategory.get("name"):
                            item_doc.custom_sub_category = subcategory.get("name")
                            updated = True
                    else:
                        error_msg = f"Subcategory with ERP ID {itmctgid} not found. Please create it first."
                        frappe.log_error(error_msg, f"UDC Item: {item_code}")
                        error_list.append({"item_code": item_code, "error": error_msg})

                if updated:
                    item_doc.save(ignore_permissions=True)
                    frappe.db.commit()

                qty_avlbl = item_data.get("qty_avlbl")
                if qty_avlbl not in [None, "", "null"]:
                    qty_avlbl = int(float(item_data.get("qty_avlbl") or 0))
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
                    item_available_qty = frappe.db.get_value("Item", item_code, "available_stock")
                    item_threshold_stock = frappe.db.get_value("Item", item_code, "threshold_stock")
                    if item_available_qty == item_threshold_stock:
                        frappe.db.set_value("Item", item_code, "threshold_stock", qty_avlbl)
                    frappe.db.set_value("Item", item_code, "available_stock", qty_avlbl)

                frappe.db.commit()
                processed_count += 1
            except Exception as e:
                error_msg = f"Unhandled error for item {item_code}: {str(e)}"
                frappe.log_error(error_msg, f"UDC Item: {item_code}")
                error_list.append({"item_code": item_code, "error": error_msg})
                continue

    summary = f"UDC Sync - Processed: {processed_count}, Errors: {len(error_list)}"
    if error_list:
        frappe.log_error(str(error_list), "sync_udc_items_from_api error details")
    return summary

@frappe.whitelist()
def get_cv_product_prices():
    """Fetch and update prices for Cotton Valley items"""
    items = frappe.get_all("Item", filters={"company": "Cotton Valley"}, pluck="name")
    total = len(items)
    frappe.log_error("Starting CV", f"Starting CV price update for {total} items...")
    url_base = "https://erp.cottonvalley.us/ords/ctnvly_api/itmrate/rgnrate?ITMID="
    username = CV_USER
    password = CV_PASSWORD
    error_count = 0
    processed_count = 0
    try:
        for start in range(0, total, CHUNK_SIZE):
            batch = items[start:start + CHUNK_SIZE]
            frappe.log_error("Processing CV", f"Processing CV items {start + 1} to {start + len(batch)}...")

            for item_code in batch:
                try:
                    url = f"{url_base}{item_code}&INACTIVE_YN=N"
                    response = requests.get(url, auth=(username, password), timeout=30)
                    if response.status_code != 200:
                        frappe.log_error("API Error", f"CV {item_code}: API Error {response.status_code}")
                        error_count += 1
                        continue

                    if not response.text.strip():
                        frappe.log_error("Empty Response", f"CV {item_code}: Empty response")
                        error_count += 1
                        continue

                    try:
                        data = response.json()
                    except Exception as e:
                        frappe.log_error("JSON Decode Error", f"CV {item_code}: JSON decode error: {str(e)}")
                        error_count += 1
                        continue

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

                        try:
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
                                    "currency": "USD"
                                }).insert()
                        except Exception as e:
                            frappe.log_error(frappe.get_traceback(), f"CV {item_code}: Error saving price: {str(e)}")
                            error_count += 1
                            continue

                except Exception as e:
                    frappe.log_error(frappe.get_traceback(), f"CV Error for {item_code}: {str(e)}")
                    error_count += 1
                finally:
                    frappe.db.commit()
                processed_count += 1

            frappe.log_error(f"CV Batch {start // CHUNK_SIZE + 1} completed.", "CV Batch Completed")
    except Exception as e:
        frappe.log_error(f"Critical error in get_cv_product_prices: {str(e)}", "CV Critical Error")
        error_count += 1
    finally:
        frappe.log_error(f"CV Price update job completed. Processed: {processed_count}, Errors: {error_count}", "CV Job Completed")
    return f"CV item prices update attempted. Processed: {processed_count}, Errors: {error_count}"


@frappe.whitelist()
def get_udc_product_prices():
    """Fetch and update prices for UDC items"""
    items = frappe.get_all("Item", filters={"company": "UDC"}, pluck="name")
    total = len(items)
    frappe.log_error("Starting UDC", f"Starting UDC price update for {total} items...")
    url_base = "https://erp.universaldc.us/ords/unvdst_api/itmrate/rgnrate?ITMID="
    username = UDC_USER
    password = UDC_PASSWORD
    error_count = 0
    processed_count = 0
    try:
        for start in range(0, total, CHUNK_SIZE):
            batch = items[start:start + CHUNK_SIZE]
            frappe.log_error("Processing UDC", f"Processing UDC items {start + 1} to {start + len(batch)}...")

            for item_code in batch:
                try:
                    url = f"{url_base}{item_code}&INACTIVE_YN=N"
                    response = requests.get(url, auth=(username, password), timeout=30)
                    if response.status_code != 200:
                        frappe.log_error("API Error", f"UDC {item_code}: API Error {response.status_code}")
                        error_count += 1
                        continue

                    if not response.text.strip():
                        frappe.log_error("Empty Response", f"UDC {item_code}: Empty response")
                        error_count += 1
                        continue

                    try:
                        data = response.json()
                    except Exception as e:
                        frappe.log_error("JSON Decode Error", f"UDC {item_code}: JSON decode error: {str(e)}")
                        error_count += 1
                        continue

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

                        try:
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
                                    "currency": "USD"
                                }).insert()
                        except Exception as e:
                            frappe.log_error(frappe.get_traceback(), f"UDC {item_code}: Error saving price: {str(e)}")
                            error_count += 1
                            continue

                except Exception as e:
                    frappe.log_error(frappe.get_traceback(), f"UDC Error for {item_code}: {str(e)}")
                    error_count += 1
                finally:
                    frappe.db.commit()
                processed_count += 1

            frappe.log_error(f"UDC Batch {start // CHUNK_SIZE + 1} completed.", "UDC Batch Completed")
    except Exception as e:
        frappe.log_error(f"Critical error in get_udc_product_prices: {str(e)}", "UDC Critical Error")
        error_count += 1
    finally:
        frappe.log_error(f"UDC Price update job completed. Processed: {processed_count}, Errors: {error_count}", "UDC Job Completed")
    return f"UDC item prices update attempted. Processed: {processed_count}, Errors: {error_count}"



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


@frappe.whitelist()
def delete_all_item_value_updates():
    """Delete all records from the Item Value Updates doctype."""
    frappe.db.delete("Item Value Updates")
    frappe.db.commit()
    return {"status": "success", "message": "All Item Value Updates records deleted."}
