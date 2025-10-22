import frappe
import base64
import os
import mimetypes


def encode_image_to_base64(image_path):
    """
    Encode image file to base64 string with MIME type prefix for Flutter.
    Supports JPEG, JPG, PNG, WebP, GIF, etc.
    Returns base64 encoded string with data URI format or None if image doesn't exist.
    """
    try:
        if not image_path:
            return None
        
        # Get full file path from Frappe
        file_path = frappe.get_site_path('public', 'files', image_path.lstrip('/files'))
        print(file_path, image_path, "checking file path \n\n\n\n\n")

        if not os.path.exists(file_path):
            return None
        
        # Detect MIME type from file extension
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            # Default to image/jpeg if cannot detect
            mime_type = 'image/jpeg'
        
        # Read and encode image
        with open(file_path, 'rb') as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            # Return with data URI format for Flutter
            return f"data:{mime_type};base64,{encoded_string}"
            
    except Exception as e:
        frappe.log_error(f"Error encoding image: {str(e)}", "Image Encoding Error")
        return None


@frappe.whitelist()
def get_all_categories():
    """
    Fetch all categories with their subcategories.
    Returns categories with base64 encoded images for security.
    """
    try:
        categories = frappe.get_all("Product Category",
            fields=["name as id", "title", "category_image", "company"]
        )

        if not categories:
            return {
                "status": "success",
                "message": "No categories found",
                "data": []
            }

        # Get all category IDs for batch query
        category_ids = [cat["id"] for cat in categories]

        # Batch query for subcategories
        subcategories_data = frappe.db.sql("""
            SELECT parent, product_subcategory as id, subcategory_name as name
            FROM `tabSubCategories`
            WHERE parent IN %s
        """, (category_ids,), as_dict=True)

        # Organize subcategories by parent
        subcategories_map = {}
        for subcat in subcategories_data:
            subcategories_map.setdefault(subcat["parent"], []).append({
                "id": subcat["id"],
                "name": subcat["name"]
            })

        # Attach subcategories to categories
        for category in categories:
            category['subcategories'] = subcategories_map.get(category["id"], [])
            
            # Encode category image to base64
            if category.get("category_image"):
                category["category_image_encoded"] = encode_image_to_base64(category["category_image"])
                # Keep original URL as fallback
                category["category_image_url"] = category["category_image"]
            else:
                category["category_image_encoded"] = None
                category["category_image_url"] = None

        return {
            "status": "success",
            "message": "Categories fetched successfully",
            "total": len(categories),
            "data": categories
        }

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "status": "error",
            "message": "Product Category doctype does not exist"
        }
    except frappe.PermissionError:
        frappe.local.response["http_status_code"] = 403
        return {
            "status": "error",
            "message": "You do not have permission to access categories"
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get All Categories Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "status": "error",
            "message": "An error occurred while fetching categories",
            "error": str(e)
        }