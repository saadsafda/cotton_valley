import frappe
from cotton_valley.api.website_theme_setting import get_file


@frappe.whitelist(allow_guest=True)
def get_all_products_with_price_levels():
    """
    Fetch all products with ALL price levels for mobile app.
    Returns all products with all available prices from different price lists.
    Mobile app will filter by customer's price level on client side.
    """
    try:
        filters = {"disabled": 0}  # only active products

        # Get all items (no pagination, no filters)
        items = frappe.get_all(
            "Item",
            filters=filters,
            fields=[
                "name as id",
                "item_name as name",
                "custom_short_description as short_description",
                "description",
                "item_group as type",
                "name as sku",
                "stock_uom as unit",
                "custom_case_pack as case_pack",
                "image as product_thumbnail_id",
                "brand",
                "custom_sub_category as sub_category",
                "custom_coming_soon as coming_soon",
                "custom_new_arrivals as new_arrivals"
            ],
            order_by="item_name asc"
        )

        if not items:
            return {
                "status": "success",
                "message": "No products found",
                "data": [],
                "total": 0
            }

        item_ids = [p["id"] for p in items]

        # Get ALL prices for ALL price lists
        all_prices_data = frappe.db.sql("""
            SELECT ip.item_code, ip.price_list, ip.price_list_rate, pl.name as price_list_name
            FROM `tabItem Price` ip
            INNER JOIN `tabPrice List` pl ON pl.name = ip.price_list
            WHERE ip.item_code IN %s
        """, (item_ids,), as_dict=True)
        
        # Organize prices by item_code
        prices_by_item = {}
        for price in all_prices_data:
            if price["item_code"] not in prices_by_item:
                prices_by_item[price["item_code"]] = {}
            prices_by_item[price["item_code"]][price["price_list"]] = price["price_list_rate"]

        # Batch query for stock
        stock_data = frappe.db.sql("""
            SELECT item_code, SUM(actual_qty) as qty
            FROM `tabBin`
            WHERE item_code in %s
            GROUP BY item_code
        """, (item_ids,), as_dict=True)
        stock_map = {s["item_code"]: s["qty"] for s in stock_data}

        # Batch query for images
        galleries_data = frappe.get_all(
            "Product Images",
            filters={"parent": ["in", item_ids]},
            fields=["parent", "list_index", "image"],
            order_by="list_index asc"
        )
        galleries_map = {}
        for g in galleries_data:
            galleries_map.setdefault(g["parent"], []).append(get_file(g["image"]) if g["image"] else None)

        # Final assembly
        products = []
        for product in items:
            product_id = product["id"]

            # on creating I missed "e" in table name
            products_categories = frappe.get_all("Product Categoris", fields=["product_category"], filters={"parent": product_id}, pluck="product_category")
            product["categories"] = products_categories
            # Add ALL price levels for this product
            product["price_levels"] = prices_by_item.get(product_id, {})

            # Stock
            qty = stock_map.get(product_id, 0)
            product["quantity"] = qty
            product["stock_status"] = "in_stock" if qty > 0 else "out_of_stock"

            # Images
            product["product_thumbnail"] = get_file(product["product_thumbnail_id"])
            product["product_galleries"] = galleries_map.get(product_id, [])

            products.append(product)

        return {
            "status": "success",
            "message": "Products fetched successfully",
            "data": products,
            "total": len(products)
        }

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "status": "error",
            "message": "Customer or related data not found"
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