# api/products.py
from cotton_valley.api.category import get_category_list
import frappe # type: ignore
from frappe import _ # type: ignore
from cotton_valley.api.website_theme_setting import get_file, get_categories_from_string
import requests
from cotton_valley.secrets import CV_USER, CV_PASSWORD, UDC_USER, UDC_PASSWORD
from cotton_valley.api.common import check_customer_token, get_customer_from_token
from frappe.utils import flt, getdate
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

    conditions = ["i.hide = 0", "i.company = %s"]
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
    filters = {"hide": 0}  # only active products
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
def get_all_products(ids=None, category=None, subcategory=None, brand=None, sortBy=None, search=None, page=None, attribute=None, producttype=None, company=None, price=None, pcsPrice=None):
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
    pcs_price = None if not pcsPrice or pcsPrice == "null" else get_categories_from_string(pcsPrice)

    filters = {"hide": 0}  # only active products

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
    # Stock filtering is handled via raw SQL using:
    # CASE WHEN set_threshold = 1 THEN threshold_stock ELSE available_stock END
    # So we don't add stock filter to ORM filters dict here.

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
        "asc": "website_ranking asc",
        "desc": "website_ranking desc",
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

    
    # --- Stock Expression: use threshold_stock if set_threshold is checked, else available_stock ---
    STOCK_EXPR = "CASE WHEN set_threshold = 1 THEN threshold_stock ELSE available_stock END"

    in_stock_count = 0
    out_of_stock_count = 0
    if search:
        # For search, we need to count in-stock and out-of-stock separately
        stock_data = frappe.db.sql(f"""
            SELECT 
                SUM(CASE WHEN {STOCK_EXPR} > 0 THEN 1 ELSE 0 END) as in_stock,
                SUM(CASE WHEN {STOCK_EXPR} <= 0 THEN 1 ELSE 0 END) as out_of_stock
            FROM `tabItem`
            WHERE item_name LIKE %s OR item_code LIKE %s
        """, (f"%{search}%", f"%{search}%"), as_dict=True)
        if stock_data:
            in_stock_count = stock_data[0]["in_stock"] or 0
            out_of_stock_count = stock_data[0]["out_of_stock"] or 0
    else:
        # For non-search, use raw SQL with conditional stock expression
        # Build base conditions from filters (excluding stock)
        base_conditions = ["hide = 0"]
        base_values = []
        if company:
            base_conditions.append("company = %s")
            base_values.append(company)
        if ids:
            base_conditions.append("name IN %s")
            base_values.append(ids)
        if producttype:
            base_conditions.append("item_group IN %s")
            base_values.append(producttype)
        if brand:
            base_conditions.append("brand IN %s")
            base_values.append(brand)
        if category and "name" in filters:
            base_conditions.append("name IN %s")
            base_values.append(filters["name"][1])
        if subcategory:
            base_conditions.append("custom_sub_category IN %s")
            base_values.append(subcategory)

        base_where = " AND ".join(base_conditions)

        stock_counts = frappe.db.sql(f"""
            SELECT
                SUM(CASE WHEN {STOCK_EXPR} > 0 THEN 1 ELSE 0 END) as in_stock,
                SUM(CASE WHEN {STOCK_EXPR} <= 0 THEN 1 ELSE 0 END) as out_of_stock
            FROM `tabItem`
            WHERE {base_where}
        """, tuple(base_values), as_dict=True)
        if stock_counts:
            in_stock_count = stock_counts[0]["in_stock"] or 0
            out_of_stock_count = stock_counts[0]["out_of_stock"] or 0

    # --- Pagination ---
    limit_start = (page - 1) * 100 if page and page > 0 else None
    limit_page_length = 100 if page else None
    
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
        hide as status,
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
        CASE WHEN set_threshold = 1 THEN threshold_stock ELSE available_stock END as stock
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
        "hide as status",
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
        "set_threshold",
        "threshold_stock",
        "available_stock"
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
                conditions.append(f"CASE WHEN {prefix}set_threshold = 1 THEN {prefix}threshold_stock ELSE {prefix}available_stock END > 0")
            elif attribute == ["out_stock"]:
                conditions.append(f"CASE WHEN {prefix}set_threshold = 1 THEN {prefix}threshold_stock ELSE {prefix}available_stock END <= 0")
        
        conditions.append(f"{prefix}hide = 0")
        
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
        # Standard sorting (asc, desc, a-z, z-a) - use raw SQL to support conditional stock expression
        filter_conditions, filter_values = build_filter_conditions("")
        if filter_conditions is None:
            return {"data": [], "total": 0}

        search_condition = ""
        if search:
            search_condition = f"AND (item_name LIKE %s OR name LIKE %s)"
            filter_values.extend([f"%{search}%", f"%{search}%"])

        where_clause = " AND ".join(filter_conditions)
        limit_clause = build_limit_clause()

        query = f"""
            SELECT {ITEM_FIELDS}
            FROM `tabItem`
            WHERE {where_clause} {search_condition}
            ORDER BY {sort_clause}
            {limit_clause}
        """
        items = frappe.db.sql(query, tuple(filter_values), as_dict=True)
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
                    i.hide as status,
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
                    CASE WHEN i.set_threshold = 1 THEN i.threshold_stock ELSE i.available_stock END as stock,
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
        return {"data": [], "total": total_count, "current_page": page or 1, "per_page": 100}

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

    # OPTIMIZATION: Batch fetch retail prices for all items in ONE query (instead of N queries in loop)
    retail_price_map = {}
    if check_customer_token():
        retail_price_data = frappe.db.sql("""
            SELECT item_code, price_list_rate
            FROM `tabItem Price`
            WHERE item_code IN %s AND price_list = %s
        """, (item_ids, "Retail"), as_dict=True)
        retail_price_map = {p["item_code"]: p["price_list_rate"] for p in retail_price_data}

    # --- Final Assembly ---
    products = []
    for product in items:
        product_id = product["id"]

        # Price - OPTIMIZED: Use pre-fetched retail prices instead of query per item
        if check_customer_token():
            retail_price = retail_price_map.get(product_id, 0)
            customer_price = price_map.get(product_id, 0)

            product["price"] = customer_price if customer_price > 0 else retail_price
            product["sale_price"] = product["price"]
            product["discount"] = 0
        else:
            product["price"] = product["sale_price"] = product["discount"] = 0

        # Stock
        # qty = stock_map.get(product_id, 0)
        qty = flt(product.get("stock", 0))

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
                    if min_price >= product_price <= max_price:
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
                    if min_pcs_price >= pcs_product_price <= max_pcs_price:
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

    product_showing = page * 100 if page and page > 0 else total_count
    from_showing = (product_showing - 100) + 1 if page and page > 0 else 1
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
            "hide as status",
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
            "set_threshold",
            "threshold_stock",
            "available_stock",
        ],
        as_dict=True
    )

    if not product:
        return {"error": "Product not found"}

    # Compute stock based on set_threshold flag
    product["stock"] = flt(product["threshold_stock"]) if product.get("set_threshold") else flt(product.get("available_stock", 0))
    
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
    retail_price_data = frappe.db.sql("""
        SELECT price_list_rate
        FROM `tabItem Price`
        WHERE item_code = %s and price_list = %s
        LIMIT 1
    """, (product_id, "Retail"), as_dict=True)
    retail_price = flt(retail_price_data[0]["price_list_rate"]) if retail_price_data else 0

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

        selected_price = flt(price_data[0]["price_list_rate"]) if price_data else 0
        product["price"] = selected_price if selected_price > 0 else retail_price
    else:
        product["price"] = retail_price

    product["sale_price"] = product["price"]  # adjust if you have discount rules
    product["discount"] = 0  # calculate discount if needed

    # quantity (stock across all warehouses)
    # qty_data = frappe.db.sql("""
    #     SELECT COALESCE(SUM(actual_qty), 0) as qty
    #     FROM `tabBin`
    #     WHERE item_code = %s
    # """, (product_id,), as_dict=True)
    # product["quantity"] = 0 if qty_data[0]["qty"] < 0 else qty_data[0]["qty"] if qty_data else 0
    product["quantity"] = flt(product.get("stock", 0))

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
    product["meta_description"] = product["short_description"] or ""
    product["product_meta_image"] = get_file(product["product_thumbnail_id"]) or ""
    product["product_tags"] = frappe.get_all("Product Tags", filters={"parent": product_id}, fields=["idx", "name1", "color"], order_by="idx asc")

    # thumbnail (first gallery file or image field)

    # OPTIMIZED: Fetch categories with all details in ONE query instead of calling get_category_list per category
    categories = frappe.db.sql("""
        SELECT 
            c.product_category as id,
            pc.title,
            pc.category_image,
            pc.banner_image
        FROM `tabProduct Categoris` c
        INNER JOIN `tabProduct Category` pc ON pc.name = c.product_category
        WHERE c.parent = %s
    """, (product_id,), as_dict=True)

    category_list = []
    for cat in categories:
        category_list.append({
            "id": cat.id,
            "name": cat.title or cat.id,
            "slug": cat.id,
            "category_image": get_file(cat.category_image),
            "banner_image": get_file(cat.banner_image),
            "products_count": 0,
            "subcategories": [],
            "type": "product"
        })

    product["categories"] = category_list
    reviews = []
    product["reviews"] = reviews
    product["reviews_count"] = len(reviews)
    product["rating_count"] = sum([r["rating"] for r in reviews]) / len(reviews) if reviews else 0

    if product["brand"]:
        # OPTIMIZED: Use get_value instead of get_doc to avoid loading full document
        brand_data = frappe.db.get_value("Brand", product["brand"], ["name", "brand", "description", "image"], as_dict=True)
        if brand_data:
            product["store"] = {
                "id": brand_data.name,
                "store_name": brand_data.brand,
                "slug": brand_data.name,
                "description": brand_data.description,
                "store_logo": get_file(brand_data.image)
            }

    # REMOVED DUPLICATE: related_products was fetched twice, keeping only the first one
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
                rgnid = item.get("rgnid")

                # Validate item data
                if not region_name or rate in (None, "") or rgnid in (None, ""):
                    skipped_count += 1
                    continue
                
                try:
                    rate_float = float(rate)
                    if rate_float < 0:
                        skipped_count += 1
                        continue
                except (ValueError, TypeError):
                    errors.append(f"Invalid rate value for region {region_name}: {rate}")
                    skipped_count += 1
                    continue

                # Check if price list exists based on company
                if company == "UDC":
                    price_list = frappe.db.get_value("Price List", {"udc_price_id": rgnid}, "name")
                else:  # Cotton Valley
                    price_list = frappe.db.get_value("Price List", {"price_id": rgnid}, "name")
                
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


def _safe_getdate(value):
    if value in (None, "", "null"):
        return None
    try:
        return getdate(value)
    except Exception:
        return None


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

    response = requests.get(url, auth=(username, password), timeout=(10, 60))
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
    eta_dt = item_data.get("eta_dt") or item_data.get("ETA_DT")

    field_mapping = {
        "item_name": item_data.get("itmdsc"),
        # "item_group": item_data.get("itmgrpdsc") or "COD",
        "hide": 1 if item_data.get("inactive_yn") == "Y" else 0,
        "custom_pallet_hi": float(item_data.get("pall_hi") or 0),
        "custom_pallet_ti": float(item_data.get("pall_ti") or 0),
        "custom_carton_upc": item_data.get("cart_upc"),
        "custom_upc": item_data.get("itm_chr2"),
        "custom_cbm": float(item_data.get("casecbm") or 0),
        "custom_case_pack": int(item_data.get("itmpack") or 0),
        "custom_case_per_pallet": int(item_data.get("pall_case") or 0),
        "custom_case_pallet_warehouse": int(item_data.get("pall_case") or item_data.get("PALL_CASE") or 0),
        "custom_case_trucking": int(item_data.get("pall_case_tr") or 0),
        "custom_short_description": item_data.get("itmdscpur"),
        "custom_package_length_inch": float(item_data.get("casesizlen") or 0),
        "custom_package_width_inch": float(item_data.get("casesizwid") or 0),
        "custom_package_height_inch": float(item_data.get("casesizthk") or 0),
        "custom_weight_lbs": float(item_data.get("casewt") or 0),
        "available_stock": float(item_data.get("qty_avlbl") or 0),
        "po_qty": float(item_data.get("vpo_bal") or 0),
        "custom_avaerage_sale": float(item_data.get("avg_mnt_sal") or 0),
        "custom_lc": float(item_data.get("purrate") or 0),
        "custom_llc": float(item_data.get("last_llc_per_case") or 0),
        "custom_pcs_container": item_data.get("itm_chr5"),
        "custom_eta_qty": float(item_data.get("eta_qty") or 0),
        "eta": _safe_getdate(eta_dt),
        "custom_vendor_code": item_data.get("last_vndcode") or item_data.get("LAST_VNDCODE"),
        "custom_grade": item_data.get("itmbrk4") or item_data.get("ITMBRK4"),
        "custom_total_stock": float(item_data.get("stk_qty") or item_data.get("STK_QTY") or 0),
    }

    updated = False
    for field, value in field_mapping.items():
        try:
            if value not in [None, "", "null"]:
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
            category_doc = frappe.get_doc({
                "doctype": "Product Category",
                "erp_id": itmclsid,
                "title": itmclsdsc or f"Category {itmclsid}",
                "company": company,
            })
            category_doc.insert(ignore_permissions=True)
            item_doc.custom_product_categories = []
            item_doc.append("custom_product_categories", {
                "product_category": category_doc.name
            })
            updated = True

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
            new_subcat = frappe.get_doc({
                "doctype": "Product Subcategory",
                "erp_id": itmctgid,
                "title": itmctgdsc or f"Subcategory {itmctgid}",
                "company": company
            })
            new_subcat.insert(ignore_permissions=True)

    if updated:
        item_doc.save(ignore_permissions=True)

    frappe.db.commit()

    return f"Item {item_code} and warehouse quantity updated successfully"


CHUNK_SIZE = 200  # adjust as needed

def _is_valid_value(val):
    return val not in (None, "", "null")

def sync_cv_item_batch(
    batch,
    company="Cotton Valley",
    task_id=None,
    batch_number=None,
    total_batches=None,
    total_items=None,
    items_before_batch=None,
):
    """
    Processes a list of item_codes.
    Commits once at end (or every X items if you want).
    Publishes progress if task_id is provided.
    
    Args:
        batch: List of item codes to process
        company: Company name
        task_id: Unique task identifier for progress tracking
        batch_number: Current batch number (for scheduler multi-batch runs)
        total_batches: Total number of batches (for scheduler multi-batch runs)
        total_items: Total items across all batches (for scheduler multi-batch runs)
        items_before_batch: Items processed before this batch (for variable batch sizes)
    """
    url_base = "https://erp.cottonvalley.us/ords/ctnvly_api/itm/itmapi?ITMID="
    # url_base = "https://sc15.indus-erp.com/ords/ctnvly_api/itm/itmapi?ITMID="
    warehouse = "Stores - CV"
    batch_item_count = len(batch)
    
    # For scheduler runs with multiple batches, calculate overall progress
    is_scheduler_run = batch_number is not None and total_batches is not None
    if not total_items:
        total_items = batch_item_count

    items_before_this_batch = 0
    if is_scheduler_run:
        if items_before_batch is not None:
            items_before_this_batch = int(items_before_batch)
        else:
            items_before_this_batch = (batch_number - 1) * batch_item_count

    processed = 0
    errors = []

    for idx, item_code in enumerate(batch):
        # Calculate progress
        if is_scheduler_run:
            # Overall progress across all batches
            overall_current = items_before_this_batch + idx + 1
            overall_percent = int((overall_current / total_items) * 100) if total_items else 0
        else:
            overall_current = idx + 1
            overall_percent = int((idx / batch_item_count) * 100)
        
        # Publish progress via realtime
        if task_id:
            frappe.publish_realtime(
                "item_sync_progress",
                {
                    "task_id": task_id,
                    "percent": overall_percent,
                    "current": overall_current,
                    "total": total_items,
                    "item_code": item_code,
                    "batch_number": batch_number,
                    "total_batches": total_batches,
                    "status": "running",
                    "company": company
                }
            )
        
        try:
            url = f"{url_base}{item_code}"
            resp = requests.get(url, auth=(CV_USER, CV_PASSWORD), verify=False, timeout=(10, 60))

            if resp.status_code == 404:
                errors.append({"item_code": item_code, "error": "Item not found in external ERP system (404)"})
                continue
            elif resp.status_code != 200:
                errors.append({"item_code": item_code, "error": f"API {resp.status_code}: {resp.text[:300]}"})
                continue

            if not resp.text.strip():
                errors.append({"item_code": item_code, "error": "Empty API response"})
                continue

            try:
                data = resp.json()
            except Exception:
                errors.append({"item_code": item_code, "error": f"Invalid JSON: {resp.text[:300]}"})
                continue

            if not data.get("items"):
                errors.append({"item_code": item_code, "error": "No item found in API response"})
                continue

            if not frappe.db.exists("Item", item_code):
                errors.append({"item_code": item_code, "error": "Item not found in ERPNext"})
                continue

            item_data = data["items"][0]
            item_doc = frappe.get_doc("Item", item_code)


            eta_dt = item_data.get("eta_dt") or item_data.get("ETA_DT")

            field_mapping = {
                "item_name": item_data.get("itmdsc"),
                "hide": 1 if item_data.get("inactive_yn") == "Y" else 0,
                "custom_pallet_hi": float(item_data.get("pall_hi") or 0),
                "custom_pallet_ti": float(item_data.get("pall_ti") or 0),
                "custom_carton_upc": item_data.get("cart_upc"),
                "custom_upc": item_data.get("itm_chr2"),
                "custom_cbm": float(item_data.get("casecbm") or 0),
                "custom_case_pack": int(float(item_data.get("itmpack") or 0)),
                "custom_case_per_pallet": int(float(item_data.get("pall_case") or 0)),
                "custom_case_pallet_warehouse": int(float(item_data.get("pall_case") or item_data.get("PALL_CASE") or 0)),
                "custom_case_trucking": int(float(item_data.get("pall_case_tr") or 0)),
                "custom_short_description": item_data.get("itmdscpur"),
                "custom_package_length_inch": float(item_data.get("casesizlen") or 0),
                "custom_package_width_inch": float(item_data.get("casesizwid") or 0),
                "custom_package_height_inch": float(item_data.get("casesizthk") or 0),
                "custom_weight_lbs": float(item_data.get("casewt") or 0),
                "available_stock": float(item_data.get("qty_avlbl") or 0),
                "po_qty": float(item_data.get("vpo_bal") or 0),
                "custom_avaerage_sale": float(item_data.get("avg_mnt_sal") or 0),
                "custom_lc": float(item_data.get("purrate") or 0),
                "custom_llc": float(item_data.get("last_llc_per_case") or 0),
                "custom_pcs_container": item_data.get("itm_chr5"),
                "custom_eta_qty": float(item_data.get("eta_qty") or 0),
                "eta": _safe_getdate(eta_dt),
                "custom_vendor_code": item_data.get("last_vndcode") or item_data.get("LAST_VNDCODE"),
                "custom_grade": item_data.get("itmbrk4") or item_data.get("ITMBRK4"),
                "custom_total_stock": float(item_data.get("stk_qty") or item_data.get("STK_QTY") or 0),
            }

            # frappe.log_error(f"Processing item {item_code}", f"{item_data.get("qty_avlbl")} available stock")

            updated = False
            invalid_fields = []

            for field, value in field_mapping.items():
                if _is_valid_value(value):
                    item_doc.set(field, value)
                    updated = True
                else:
                    invalid_fields.append((field, value))

            # ✅ Category handling (also fix typo "Product Categoris")
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

                    # ensure child table row exists WITHOUT clearing whole table
                    exists_row = any(
                        row.product_category == category.get("name")
                        for row in (item_doc.get("custom_product_categories") or [])
                    )
                    if not exists_row:
                        item_doc.append("custom_product_categories", {"product_category": category.get("name")})
                        updated = True
                else:
                    errors.append({"item_code": item_code, "error": f"Category ERP ID {itmclsid} not found"})

            # Subcategory
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
                    frappe.get_doc({
                        "doctype": "Product Subcategory",
                        "erp_id": itmctgid,
                        "title": itmctgdsc or f"{itmctgid}",
                        "company": company,
                    }).insert(ignore_permissions=True)
                    item_doc.custom_sub_category = itmctgid
                    updated = True

            if updated:
                item_doc.save(ignore_permissions=True)


            processed += 1

        except Exception as e:
            errors.append({"item_code": item_code, "error": f"Unhandled: {str(e)}"})
    # ✅ Commit once per batch
    frappe.db.commit()

    # Publish completion via realtime
    if task_id:
        # For scheduler runs, only publish 100% complete on the last batch
        if is_scheduler_run:
            is_last_batch = batch_number == total_batches
            final_percent = 100 if is_last_batch else overall_percent
            final_status = "complete" if is_last_batch else "batch_complete"
        else:
            final_percent = 100
            final_status = "complete"
        
        frappe.publish_realtime(
            "item_sync_progress",
            {
                "task_id": task_id,
                "percent": final_percent,
                "current": overall_current if is_scheduler_run else batch_item_count,
                "total": total_items,
                "processed": processed,
                "error_count": len(errors),
                "status": final_status,
                "company": company,
                "batch_number": batch_number,
                "total_batches": total_batches
            }
            )

    # Log summary once
    if errors:
        frappe.log_error(title="CV Batch Sync Errors", message=str(errors[:200]))
        frappe.get_doc({
                "doctype": "Item Value Updates",
                "company": company,
                "title": "CV Batch Sync Errors",
                "message": str(errors[:200])
            }).insert(ignore_permissions=True)

    return {"processed": processed, "errors": len(errors), "task_id": task_id}



def sync_udc_item_batch(
    batch,
    company="UDC",
    task_id=None,
    batch_number=None,
    total_batches=None,
    total_items=None,
    items_before_batch=None,
):
    """
    Processes a list of item_codes.
    Commits once at end (or every X items if you want).
    Publishes progress if task_id is provided.
    
    Args:
        batch: List of item codes to process
        company: Company name
        task_id: Unique task identifier for progress tracking
        batch_number: Current batch number (for scheduler multi-batch runs)
        total_batches: Total number of batches (for scheduler multi-batch runs)
        total_items: Total items across all batches (for scheduler multi-batch runs)
        items_before_batch: Items processed before this batch (for variable batch sizes)
    """
    url_base = "https://erp.universaldc.us/ords/unvdst_api/itm/itmapi?ITMID="
    warehouse = "Stores - U"
    batch_item_count = len(batch)
    
    # For scheduler runs with multiple batches, calculate overall progress
    is_scheduler_run = batch_number is not None and total_batches is not None
    if not total_items:
        total_items = batch_item_count

    items_before_this_batch = 0
    if is_scheduler_run:
        if items_before_batch is not None:
            items_before_this_batch = int(items_before_batch)
        else:
            items_before_this_batch = (batch_number - 1) * batch_item_count

    processed = 0
    errors = []

    for idx, item_code in enumerate(batch):
        # Calculate progress
        if is_scheduler_run:
            # Overall progress across all batches
            overall_current = items_before_this_batch + idx + 1
            overall_percent = int((overall_current / total_items) * 100) if total_items else 0
        else:
            overall_current = idx + 1
            overall_percent = int((idx / batch_item_count) * 100)
        
        # Publish progress via realtime
        if task_id:
            frappe.publish_realtime(
                "item_sync_progress",
                {
                    "task_id": task_id,
                    "percent": overall_percent,
                    "current": overall_current,
                    "total": total_items,
                    "item_code": item_code,
                    "batch_number": batch_number,
                    "total_batches": total_batches,
                    "status": "running",
                    "company": company
                }
            )
        
        try:
            url = f"{url_base}{item_code}"
            resp = requests.get(url, auth=(UDC_USER, UDC_PASSWORD), verify=False, timeout=(10, 60))

            if resp.status_code == 404:
                errors.append({"item_code": item_code, "error": "Item not found in external ERP system (404)"})
                continue
            elif resp.status_code != 200:
                errors.append({"item_code": item_code, "error": f"API {resp.status_code}: {resp.text[:300]}"})
                continue

            if not resp.text.strip():
                errors.append({"item_code": item_code, "error": "Empty API response"})
                continue

            try:
                data = resp.json()
            except Exception:
                errors.append({"item_code": item_code, "error": f"Invalid JSON: {resp.text[:300]}"})
                continue

            if not data.get("items"):
                errors.append({"item_code": item_code, "error": "No item found in API response"})
                continue

            if not frappe.db.exists("Item", item_code):
                errors.append({"item_code": item_code, "error": "Item not found in ERPNext"})
                continue

            item_data = data["items"][0]
            item_doc = frappe.get_doc("Item", item_code)

            eta_dt = item_data.get("eta_dt") or item_data.get("ETA_DT")

            field_mapping = {
                "item_name": item_data.get("itmdsc"),
                "hide": 1 if item_data.get("inactive_yn") == "Y" else 0,
                "custom_pallet_hi": float(item_data.get("pall_hi") or 0),
                "custom_pallet_ti": float(item_data.get("pall_ti") or 0),
                "custom_carton_upc": item_data.get("cart_upc"),
                "custom_upc": item_data.get("itm_chr2"),
                "custom_cbm": float(item_data.get("casecbm") or 0),
                "custom_case_pack": int(float(item_data.get("itmpack") or 0)),
                "custom_case_per_pallet": int(float(item_data.get("pall_case") or 0)),
                "custom_case_pallet_warehouse": int(float(item_data.get("pall_case") or item_data.get("PALL_CASE") or 0)),
                "custom_case_trucking": int(float(item_data.get("pall_case_tr") or 0)),
                "custom_short_description": item_data.get("itmdscpur"),
                "custom_package_length_inch": float(item_data.get("casesizlen") or 0),
                "custom_package_width_inch": float(item_data.get("casesizwid") or 0),
                "custom_package_height_inch": float(item_data.get("casesizthk") or 0),
                "custom_weight_lbs": float(item_data.get("casewt") or 0),
                "available_stock": float(item_data.get("qty_avlbl") or 0),
                "po_qty": float(item_data.get("vpo_bal") or 0),
                "custom_avaerage_sale": float(item_data.get("avg_mnt_sal") or 0),
                "custom_lc": float(item_data.get("purrate") or 0),
                "custom_llc": float(item_data.get("last_llc_per_case") or 0),
                "custom_pcs_container": item_data.get("itm_chr5"),
                "custom_eta_qty": float(item_data.get("eta_qty") or 0),
                "eta": _safe_getdate(eta_dt),
                "custom_vendor_code": item_data.get("last_vndcode") or item_data.get("LAST_VNDCODE"),
                "custom_grade": item_data.get("itmbrk4") or item_data.get("ITMBRK4"),
                "custom_total_stock": float(item_data.get("stk_qty") or item_data.get("STK_QTY") or 0),
            }

            updated = False
            invalid_fields = []

            for field, value in field_mapping.items():
                if _is_valid_value(value):
                    item_doc.set(field, value)
                    updated = True
                else:
                    invalid_fields.append((field, value))

            # ✅ Category handling (also fix typo "Product Categoris")
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

                    # ensure child table row exists WITHOUT clearing whole table
                    exists_row = any(
                        row.product_category == category.get("name")
                        for row in (item_doc.get("custom_product_categories") or [])
                    )
                    if not exists_row:
                        item_doc.append("custom_product_categories", {"product_category": category.get("name")})
                        updated = True
                else:
                    errors.append({"item_code": item_code, "error": f"Category ERP ID {itmclsid} not found"})

            # Subcategory
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
                    frappe.get_doc({
                        "doctype": "Product Subcategory",
                        "erp_id": itmctgid,
                        "title": itmctgdsc or f"{itmctgid}",
                        "company": company,
                    }).insert(ignore_permissions=True)
                    item_doc.custom_sub_category = itmctgid
                    updated = True

            if updated:
                item_doc.save(ignore_permissions=True)

            processed += 1

        except Exception as e:
            errors.append({"item_code": item_code, "error": f"Unhandled: {str(e)}"})

    # ✅ Commit once per batch
    frappe.db.commit()

    # Publish completion via realtime
    if task_id:
        # For scheduler runs, only publish 100% complete on the last batch
        if is_scheduler_run:
            is_last_batch = batch_number == total_batches
            final_percent = 100 if is_last_batch else overall_percent
            final_status = "complete" if is_last_batch else "batch_complete"
        else:
            final_percent = 100
            final_status = "complete"
        
        frappe.publish_realtime(
            "item_sync_progress",
            {
                "task_id": task_id,
                "percent": final_percent,
                "current": overall_current if is_scheduler_run else batch_item_count,
                "total": total_items,
                "processed": processed,
                "error_count": len(errors),
                "status": final_status,
                "company": company,
                "batch_number": batch_number,
                "total_batches": total_batches
            }
            )

    # Log summary once
    if errors:
        frappe.log_error(title=" UDC Batch Sync Errors", message=str(errors[:200]))
        frappe.get_doc({
                "doctype": "Item Value Updates",
                "company": company,
                "title": "UDC Batch Sync Errors",
                "message": str(errors[:200])
            }).insert(ignore_permissions=True)

    return {"processed": processed, "errors": len(errors), "task_id": task_id}


def sync_cv_price_batch(
    batch,
    company="Cotton Valley",
    task_id=None,
    batch_number=None,
    total_batches=None,
    total_items=None,
    items_before_batch=None,
):
    """
    Process a batch of Cotton Valley item prices from external API.
    Called by scheduler dispatcher, runs in background queue.
    
    Args:
        batch: List of item codes to process
        company: Company name
        task_id: Unique task identifier for progress tracking
        batch_number: Current batch number (for scheduler multi-batch runs)
        total_batches: Total number of batches (for scheduler multi-batch runs)
        total_items: Total items across all batches (for scheduler multi-batch runs)
        items_before_batch: Items processed before this batch (for variable batch sizes)
    """
    url_base = "https://erp.cottonvalley.us/ords/ctnvly_api/itmrate/rgnrate?ITMID="
    username = CV_USER
    password = CV_PASSWORD
    error_count = 0
    processed_count = 0
    batch_item_count = len(batch)
    
    # For scheduler runs with multiple batches, calculate overall progress
    is_scheduler_run = batch_number is not None and total_batches is not None
    if not total_items:
        total_items = batch_item_count

    items_before_this_batch = 0
    if is_scheduler_run:
        if items_before_batch is not None:
            items_before_this_batch = int(items_before_batch)
        else:
            items_before_this_batch = (batch_number - 1) * batch_item_count

    for idx, item_code in enumerate(batch):
        # Calculate progress
        if is_scheduler_run:
            overall_current = items_before_this_batch + idx + 1
            overall_percent = int((overall_current / total_items) * 100) if total_items else 0
        else:
            overall_current = idx + 1
            overall_percent = int((idx / batch_item_count) * 100)
        
        # Publish progress via realtime
        if task_id:
            frappe.publish_realtime(
                "price_sync_progress",
                {
                    "task_id": task_id,
                    "percent": overall_percent,
                    "current": overall_current,
                    "total": total_items,
                    "item_code": item_code,
                    "batch_number": batch_number,
                    "total_batches": total_batches,
                    "status": "running",
                    "company": company
                }
            )
        
        try:
            url = f"{url_base}{item_code}&INACTIVE_YN=N"
            response = requests.get(url, auth=(username, password), timeout=30)
            if response.status_code != 200:
                frappe.log_error("API Error", f"CV Price {item_code}: API Error {response.status_code}")
                error_count += 1
                continue

            if not response.text.strip():
                error_count += 1
                continue

            try:
                data = response.json()
            except Exception as e:
                frappe.log_error("JSON Decode Error", f"CV Price {item_code}: JSON decode error: {str(e)}")
                error_count += 1
                continue

            if not data.get("items"):
                continue

            for item in data["items"]:
                region_name = item.get("rgnname")
                rate = item.get("rate")
                rgnid = item.get("rgnid")

                if not region_name or rate in (None, "") or rgnid in (None, ""):
                    continue

                try:
                    rate_float = float(rate)
                    if rate_float < 0:
                        continue
                except (ValueError, TypeError):
                    continue

                # Fetch price list using price_id for Cotton Valley
                price_list = frappe.db.get_value("Price List", {"price_id": rgnid}, "name")
                if not price_list:
                    continue

                existing = frappe.db.exists("Item Price", {
                    "item_code": item_code,
                    "price_list": price_list
                })

                try:
                    if existing:
                        ip = frappe.get_doc("Item Price", existing)
                        ip.price_list_rate = rate_float
                        ip.save()
                    else:
                        frappe.get_doc({
                            "doctype": "Item Price",
                            "item_code": item_code,
                            "price_list": price_list,
                            "price_list_rate": rate_float,
                            "currency": "USD"
                        }).insert()
                except Exception as e:
                    frappe.log_error(frappe.get_traceback(), f"CV Price {item_code}: Error saving price: {str(e)}")
                    error_count += 1
                    continue

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"CV Price Error for {item_code}: {str(e)}")
            error_count += 1
        finally:
            frappe.db.commit()
        processed_count += 1

    # Publish completion via realtime
    if task_id:
        if is_scheduler_run:
            is_last_batch = batch_number == total_batches
            final_percent = 100 if is_last_batch else overall_percent
            final_status = "complete" if is_last_batch else "batch_complete"
        else:
            final_percent = 100
            final_status = "complete"
        
        frappe.publish_realtime(
            "price_sync_progress",
            {
                "task_id": task_id,
                "percent": final_percent,
                "current": overall_current if is_scheduler_run else batch_item_count,
                "total": total_items,
                "processed": processed_count,
                "error_count": error_count,
                "status": final_status,
                "company": company,
                "batch_number": batch_number,
                "total_batches": total_batches
            }
            )

    frappe.log_error(f"CV Price Batch completed. Processed: {processed_count}, Errors: {error_count}", "CV Price Batch Completed")
    return {"processed": processed_count, "errors": error_count, "task_id": task_id}


def sync_udc_price_batch(
    batch,
    company="UDC",
    task_id=None,
    batch_number=None,
    total_batches=None,
    total_items=None,
    items_before_batch=None,
):
    """
    Process a batch of UDC item prices from external API.
    Called by scheduler dispatcher, runs in background queue.
    
    Args:
        batch: List of item codes to process
        company: Company name
        task_id: Unique task identifier for progress tracking
        batch_number: Current batch number (for scheduler multi-batch runs)
        total_batches: Total number of batches (for scheduler multi-batch runs)
        total_items: Total items across all batches (for scheduler multi-batch runs)
        items_before_batch: Items processed before this batch (for variable batch sizes)
    """
    url_base = "https://erp.universaldc.us/ords/unvdst_api/itmrate/rgnrate?ITMID="
    username = UDC_USER
    password = UDC_PASSWORD
    error_count = 0
    processed_count = 0
    batch_item_count = len(batch)
    
    # For scheduler runs with multiple batches, calculate overall progress
    is_scheduler_run = batch_number is not None and total_batches is not None
    if not total_items:
        total_items = batch_item_count

    items_before_this_batch = 0
    if is_scheduler_run:
        if items_before_batch is not None:
            items_before_this_batch = int(items_before_batch)
        else:
            items_before_this_batch = (batch_number - 1) * batch_item_count

    for idx, item_code in enumerate(batch):
        # Calculate progress
        if is_scheduler_run:
            overall_current = items_before_this_batch + idx + 1
            overall_percent = int((overall_current / total_items) * 100) if total_items else 0
        else:
            overall_current = idx + 1
            overall_percent = int((idx / batch_item_count) * 100)
        
        # Publish progress via realtime
        if task_id:
            frappe.publish_realtime(
                "price_sync_progress",
                {
                    "task_id": task_id,
                    "percent": overall_percent,
                    "current": overall_current,
                    "total": total_items,
                    "item_code": item_code,
                    "batch_number": batch_number,
                    "total_batches": total_batches,
                    "status": "running",
                    "company": company
                }
            )
        
        try:
            url = f"{url_base}{item_code}&INACTIVE_YN=N"
            response = requests.get(url, auth=(username, password), timeout=30)
            if response.status_code != 200:
                frappe.log_error("API Error", f"UDC Price {item_code}: API Error {response.status_code}")
                error_count += 1
                continue

            if not response.text.strip():
                error_count += 1
                continue

            try:
                data = response.json()
            except Exception as e:
                frappe.log_error("JSON Decode Error", f"UDC Price {item_code}: JSON decode error: {str(e)}")
                error_count += 1
                continue

            if not data.get("items"):
                continue

            for item in data["items"]:
                region_name = item.get("rgnname")
                rate = item.get("rate")
                rgnid = item.get("rgnid")

                if not region_name or rate in (None, "") or rgnid in (None, ""):
                    continue

                try:
                    rate_float = float(rate)
                    if rate_float < 0:
                        continue
                except (ValueError, TypeError):
                    continue

                # Fetch price list using udc_price_id for UDC
                price_list = frappe.db.get_value("Price List", {"udc_price_id": rgnid}, "name")
                if not price_list:
                    continue

                existing = frappe.db.exists("Item Price", {
                    "item_code": item_code,
                    "price_list": price_list
                })

                try:
                    if existing:
                        ip = frappe.get_doc("Item Price", existing)
                        ip.price_list_rate = rate_float
                        ip.save(ignore_permissions=True)
                    else:
                        frappe.get_doc({
                            "doctype": "Item Price",
                            "item_code": item_code,
                            "price_list": price_list,
                            "price_list_rate": rate_float,
                            "currency": "USD"
                        }).insert(ignore_permissions=True)
                except Exception as e:
                    frappe.log_error(frappe.get_traceback(), f"UDC Price {item_code}: Error saving price: {str(e)}")
                    error_count += 1
                    continue

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"UDC Price Error for {item_code}: {str(e)}")
            error_count += 1
        finally:
            frappe.db.commit()
        processed_count += 1

    # Publish completion via realtime
    if task_id:
        if is_scheduler_run:
            is_last_batch = batch_number == total_batches
            final_percent = 100 if is_last_batch else overall_percent
            final_status = "complete" if is_last_batch else "batch_complete"
        else:
            final_percent = 100
            final_status = "complete"
        
        frappe.publish_realtime(
            "price_sync_progress",
            {
                "task_id": task_id,
                "percent": final_percent,
                "current": overall_current if is_scheduler_run else batch_item_count,
                "total": total_items,
                "processed": processed_count,
                "error_count": error_count,
                "status": final_status,
                "company": company,
                "batch_number": batch_number,
                "total_batches": total_batches
            }
            )

    frappe.log_error(f"UDC Price Batch completed. Processed: {processed_count}, Errors: {error_count}", "UDC Price Batch Completed")
    return {"processed": processed_count, "errors": error_count, "task_id": task_id}



@frappe.whitelist()
def download_custom_catalog(company=None):
    if not company:
        return []

    rows = frappe.db.sql(
        """
        SELECT DISTINCT ip.price_list
        FROM `tabItem Price` ip
        INNER JOIN `tabItem` i ON i.name = ip.item_code
        WHERE i.company = %(company)s
          AND IFNULL(ip.price_list, '') != ''
        ORDER BY ip.price_list
        """,
        {"company": company},
        as_list=True,
    )

    return [r[0] for r in rows if r and r[0]]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_catalog_price_list_link_options(doctype, txt, searchfield, start, page_len, filters):
    filters = filters or {}
    company = (filters.get("company") or "").strip()

    values = {
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len,
    }

    company_condition = ""
    if company:
        company_condition = " AND i.company = %(company)s "
        values["company"] = company

    return frappe.db.sql(
        f"""
        SELECT DISTINCT pl.name, pl.currency
        FROM `tabPrice List` pl
        INNER JOIN `tabItem Price` ip ON ip.price_list = pl.name
        INNER JOIN `tabItem` i ON i.name = ip.item_code
        WHERE pl.name LIKE %(txt)s
          AND IFNULL(ip.price_list, '') != ''
          {company_condition}
        ORDER BY pl.name
        LIMIT %(start)s, %(page_len)s
        """,
        values,
    )


@frappe.whitelist()
def download_custom_catalog(items, company=None, price_list=None, item_group=None):
    try:
        # Parse the JSON string list of Item Names passed from JS
        if isinstance(items, str):
            item_names = json.loads(items)
        else:
            item_names = items
            
        # Validate input
        if not item_names or not isinstance(item_names, list):
            frappe.throw(_("Invalid items list provided"))

        company = (company or "").strip()
        price_list = (price_list or "").strip()
        item_group = (item_group or "").strip()

        if not company:
            frappe.throw(_("Company is required"))

        if not price_list:
            frappe.throw(_("Price List is required"))

        def get_company_banner_name(raw_company):
            normalized = (raw_company or "").strip().lower()
            mapped = {
                "cotton valley": "COTTON VALLEY LLC",
                "cotton valley llc": "COTTON VALLEY LLC",
                "udc": "UNIVERSAL DISTRIBUTION LLC",
                "universal distribution": "UNIVERSAL DISTRIBUTION LLC",
                "universal distribution llc": "UNIVERSAL DISTRIBUTION LLC",
            }
            return mapped.get(normalized, (raw_company or "").strip().upper())
        
        # 1. Fetch Item Data
        item_filters = {
            "name": ["in", item_names],
            "company": company,
        }

        if item_group:
            item_filters["item_group"] = item_group

        data = frappe.get_all("Item",
            filters=item_filters,
            fields=["image", "item_code", "item_name", "custom_sub_category as subcategory",  
                    "custom_case_pack as case_pack", "custom_package_length_inch as case_length",
                    "custom_package_width_inch as case_width", "custom_package_height_inch as case_height",
                    "custom_weight_lbs as net_weight","custom_pallet_ti as pallet_ti",
                    "custom_pallet_hi as pallet_hi", "custom_case_per_pallet as cases_per_pallet",
                    "stock_price", "custom_carton_upc as item_upc", "custom_cbm as cbm", "available_stock", "company"]
        )
        
        if not data:
            if item_group:
                frappe.throw(_("No items found for Product Type {0}").format(item_group))
            frappe.throw(_("No items found"))
        # 2. Setup Excel
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Catalog")

        # --- STYLES ---
        header_blue = workbook.add_format({'bg_color': "#FF99A3", 'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        header_green = workbook.add_format({'bg_color': "#FF99A3", 'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        header_yellow = workbook.add_format({'bg_color': '#FF99A3', 'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        text_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        text_blue_fmt = workbook.add_format({'bg_color': '#F2DCDB', 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        text_green_fmt = workbook.add_format({'bg_color': '#F2DCDB', 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        price_fmt = workbook.add_format({'bg_color': '#FFFF00', 'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '$0.00'})
        company_header_fmt = workbook.add_format({'bold': True, 'font_size': 11, 'valign': 'vcenter'})
        company_info_fmt = workbook.add_format({'font_size': 16, 'valign': 'vcenter', 'bold': True})
        company_banner_fmt = workbook.add_format({'bg_color': '#3A3F46', 'font_color': '#FFFFFF', 'bold': True, 'font_size': 16, 'valign': 'vcenter', 'align': 'left'})

        # --- COLUMN WIDTHS ---
        worksheet.set_column('A:A', 25)
        worksheet.set_column('B:B', 15)
        worksheet.set_column('C:C', 35)
        worksheet.set_column('D:I', 20)
        worksheet.set_column('J:J', 20)
        worksheet.set_column('K:L', 10)
        worksheet.set_column('M:M', 20)
        worksheet.set_column('N:O', 20)
        worksheet.set_column('P:Q', 20)

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

        company_banner_name = get_company_banner_name(company)
        worksheet.set_row(8, 30)
        worksheet.merge_range(8, 0, 8, 18, company_banner_name, company_banner_fmt)

        # --- HEADERS ---
        headers = [
            "Picture", "Code", "Description", "Category", "SubCategory", 
            "Master Case Pack", "Case-Length(INCH)",  "Case-Width(INCH)", 
            "Case-Height(INCH)", "Net-Weight(LBS)", "TI", "HI", "Cases/Pallet Trucking",
            "Price in Case", "Price in Piece", "Item UPC", "CBM", 
            "Available Stock", "Stock in Pieces"
        ]
        
        start_row = 9
        worksheet.set_row(start_row, 30)
        for col, title in enumerate(headers):
            if col in [13, 14]:  # Price in Case, Price in Piece
                fmt = header_yellow
            elif col in [10, 11]:  # TI, HI
                fmt = header_green
            else:
                fmt = header_blue
            worksheet.write(start_row, col, title, fmt)

        # --- WRITE DATA ---
        row = start_row + 1

        item_codes = [item.item_code for item in data]
        item_price_map = {}

        if item_codes:
            item_prices = frappe.get_all(
                "Item Price",
                filters={
                    "item_code": ["in", item_codes],
                    "price_list": price_list,
                },
                fields=["item_code", "price_list_rate"],
                order_by="valid_from desc, modified desc",
            )

            for entry in item_prices:
                code = entry.get("item_code")
                if code and code not in item_price_map:
                    item_price_map[code] = flt(entry.get("price_list_rate") or 0)

        # Fetch all categories in one query for performance
        all_categories = frappe.db.sql("""
            SELECT c.parent, c.product_category as id, pc.title as title
            FROM `tabProduct Categoris` c
            INNER JOIN `tabProduct Category` pc ON pc.name = c.product_category
            WHERE c.parent IN %(items)s
        """, {"items": item_codes}, as_dict=True)
        
        # Group categories by item code
        categories_map = {}
        for cat in all_categories:
            if cat.parent not in categories_map:
                categories_map[cat.parent] = []
            categories_map[cat.parent].append(cat)
        
        for item in data:
            worksheet.set_row(row, 90)
            categories = categories_map.get(item.item_code, [])
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
            categoryName = categories[0].title if categories and len(categories) > 0 else "-"

            worksheet.write(row, 1, item.get("item_code", "") or "-", text_fmt)
            worksheet.write(row, 2, item.get("item_name", "") or "-", text_fmt)
            worksheet.write(row, 3, categoryName, text_fmt)
            worksheet.write(row, 4, subcategoryName or "-", text_fmt)
            worksheet.write(row, 5, item.get("case_pack", "") or "-", text_fmt)
            worksheet.write(row, 6, item.get("case_length", "") or "-", text_blue_fmt)
            worksheet.write(row, 7, item.get("case_width", "") or "-", text_blue_fmt)
            worksheet.write(row, 8, item.get("case_height", "") or "-", text_blue_fmt)
            worksheet.write(row, 9, item.get("net_weight", "") or "-", text_blue_fmt)
            worksheet.write(row, 10, item.get("pallet_ti", "") or "-", text_green_fmt)
            worksheet.write(row, 11, item.get("pallet_hi", "") or "-", text_green_fmt)
            worksheet.write(row, 12, item.get("cases_per_pallet", "") or "-", text_blue_fmt)

            selected_price = item_price_map.get(item.get("item_code"))
            if selected_price is None:
                worksheet.write_blank(row, 13, None, price_fmt)
                worksheet.write_blank(row, 14, None, price_fmt)
            else:
                case_pack = flt(item.get("case_pack", 0) or 0)
                piece_price = selected_price / case_pack if case_pack else selected_price
                worksheet.write(row, 13, selected_price, price_fmt)
                worksheet.write(row, 14, piece_price, price_fmt)

            worksheet.write(row, 15, item.get("item_upc", "") or "-", text_fmt)
            worksheet.write(row, 16, item.get("cbm", "") or "-", text_fmt)
            worksheet.write(row, 17, item.get("available_stock", "") or "-", text_fmt)
            worksheet.write(row, 18, (flt(item.get("available_stock", 0) or 0) * flt(item.get("case_pack", 1) or 1)), text_fmt)
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
