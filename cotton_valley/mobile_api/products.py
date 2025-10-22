import frappe


@frappe.whitelist(allow_guest=True)
def get_all_products_with_price_levels():
    """
    Fetch all products with ALL price levels for mobile app.
    Optimized version with batch processing and minimal queries.
    """
    try:
        # Single optimized query to get all data at once
        products_data = frappe.db.sql("""
            SELECT 
                i.name as id,
                i.item_name as name,
                i.custom_short_description as short_description,
                i.description,
                i.item_group as type,
                i.name as sku,
                i.stock_uom as unit,
                i.custom_case_pack as case_pack,
                i.image as product_thumbnail_id,
                i.brand,
                i.custom_sub_category as sub_category,
                i.custom_coming_soon as coming_soon,
                i.custom_new_arrivals as new_arrivals,
                COALESCE(SUM(b.actual_qty), 0) as stock
            FROM `tabItem` i
            LEFT JOIN `tabBin` b ON b.item_code = i.name
            WHERE i.disabled = 0
            GROUP BY i.name
            ORDER BY i.item_name ASC
        """, as_dict=True)

        if not products_data:
            return {
                "status": "success",
                "message": "No products found",
                "data": [],
                "total": 0
            }

        item_ids = [p["id"] for p in products_data]

        # Get ALL prices in one query
        all_prices_data = frappe.db.sql("""
            SELECT item_code, price_list, price_list_rate
            FROM `tabItem Price`
            WHERE item_code IN %s
        """, (item_ids,), as_dict=True)
        
        # Organize prices by item_code
        prices_by_item = {}
        for price in all_prices_data:
            if price["item_code"] not in prices_by_item:
                prices_by_item[price["item_code"]] = {}
            prices_by_item[price["item_code"]][price["price_list"]] = price["price_list_rate"]

        # Get categories in one query
        categories_data = frappe.db.sql("""
            SELECT parent, product_category
            FROM `tabProduct Categoris`
            WHERE parent IN %s
        """, (item_ids,), as_dict=True)
        
        categories_by_item = {}
        for cat in categories_data:
            categories_by_item.setdefault(cat["parent"], []).append(cat["product_category"])

        # Get images in one query
        galleries_data = frappe.db.sql("""
            SELECT parent, image
            FROM `tabProduct Images`
            WHERE parent IN %s
            ORDER BY list_index ASC
        """, (item_ids,), as_dict=True)
        
        galleries_by_item = {}
        for g in galleries_data:
            if g["image"]:
                image_url = frappe.utils.get_url(g["image"])
                galleries_by_item.setdefault(g["parent"], []).append(image_url)

        # Assemble final data
        products = []
        for product in products_data:
            product_id = product["id"]

            # Add price levels
            product["price_levels"] = prices_by_item.get(product_id, {})

            # Add categories
            product["categories"] = categories_by_item.get(product_id, [])

            # Stock status
            product["stock_status"] = "in_stock" if product["stock"] > 0 else "out_of_stock"

            # Images with base64 encoding
            if product["product_thumbnail_id"]:
                product["image_url"] = frappe.utils.get_url(product["product_thumbnail_id"])
            else:
                product["image_url"] = None
                product["image_encoded"] = None
                
            product["images"] = galleries_by_item.get(product_id, [])

            products.append(product)

        return {
            "status": "success",
            "message": "Products fetched successfully",
            "total": len(products),
            "data": products
        }

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "status": "error",
            "message": "Product or related data not found"
        }
    except frappe.PermissionError:
        frappe.local.response["http_status_code"] = 403
        return {
            "status": "error",
            "message": "You do not have permission to access this data"
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get All Products with Price Levels Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "status": "error",
            "message": "An error occurred while fetching products",
            "error": str(e)
        }
    