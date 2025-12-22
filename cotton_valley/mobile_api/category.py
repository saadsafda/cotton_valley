import frappe

@frappe.whitelist()
def get_all_categories(company=None):
    """
    Fetch all categories with their subcategories.
    Returns categories with base64 encoded images for security.
    """
    try:
        company = None if not company or company == "null" else company
        filters = {}
        if company:
            filters = {"company": company}
        else:
            filters = {}
        categories = frappe.get_all("Product Category",
            filters=filters,
            fields=["name as id", "title", "category_image", "company", "app_ranking"],
            order_by="app_ranking asc"
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
            SELECT parent, product_subcategory as id, subcategory_name as name, image, app_ranking
            FROM `tabSubCategories`
            WHERE parent IN %s
        """, (category_ids,), as_dict=True)

        # Organize subcategories by parent
        subcategories_map = {}
        for subcat in subcategories_data:
            app_ranking = frappe.db.get_value("Product Subcategory", subcat["id"], "app_ranking")
            subcategories_map.setdefault(subcat["parent"], []).append({
                "id": subcat["id"],
                "name": subcat["name"],
                "image": frappe.utils.get_url(subcat["image"]) if subcat.get("image") else None,
                "app_ranking": app_ranking
            })

        # Attach subcategories to categories
        for category in categories:
            category['subcategories'] = subcategories_map.get(category["id"], [])
            
            # Encode category image to base64
            if category.get("category_image"):
                # Keep original URL as fallback
                category["category_image_url"] = frappe.utils.get_url(category["category_image"])
            else:
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