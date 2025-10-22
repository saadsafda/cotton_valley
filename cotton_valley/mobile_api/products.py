import frappe
import base64
import os
import mimetypes
from PIL import Image
from io import BytesIO
from cotton_valley.api.website_theme_setting import get_file


def encode_image_to_base64(image_path, max_width=800, quality=85):
    """
    Encode image file to base64 string with compression and resizing.
    This dramatically reduces payload size while maintaining quality.
    
    Args:
        image_path: Path to the image file
        max_width: Maximum width in pixels (default: 800px for mobile)
        quality: JPEG quality 1-100 (default: 85, good balance)
    
    Returns:
        Base64 encoded string with data URI format or None if image doesn't exist.
    """
    try:
        if not image_path:
            return None
        
        # Get full file path from Frappe
        file_path = frappe.get_site_path('public', 'files', image_path.lstrip('/files/'))
        
        if not os.path.exists(file_path):
            return None
        
        # Open and resize image
        with Image.open(file_path) as img:
            # Convert RGBA to RGB if necessary (for JPEG)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            
            # Resize if width exceeds max_width
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.LANCZOS)
            
            # Save to BytesIO with compression
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            buffer.seek(0)
            
            # Encode to base64
            encoded_string = base64.b64encode(buffer.read()).decode('utf-8')
            return f"data:image/jpeg;base64,{encoded_string}"
            
    except Exception as e:
        frappe.log_error(f"Error encoding image: {str(e)}", "Image Encoding Error")
        return None



@frappe.whitelist(allow_guest=True)
def get_all_products_with_price_levels(limit_start=0, limit_page_length=500):
    """
    Fetch all products with ALL price levels for mobile app.
    Optimized version with batch processing and minimal queries.
    
    Args:
        limit_start: Starting index for pagination (default: 0)
        limit_page_length: Number of records per page (default: 500)
    """
    try:
        # Convert parameters to integers
        limit_start = int(limit_start)
        limit_page_length = int(limit_page_length)
        
        # Single optimized query to get all data at once with pagination
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
            LIMIT %s OFFSET %s
        """, (limit_page_length, limit_start), as_dict=True)

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
                image_encoded = encode_image_to_base64(g["image"])
                galleries_by_item.setdefault(g["parent"], []).append({
                    "url": image_url,
                    "encoded": image_encoded
                })

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
                product["image_encoded"] = encode_image_to_base64(product["product_thumbnail_id"])
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
    