import frappe
from frappe import _

@frappe.whitelist()
def get_tag_info():
    try:
        current_user = frappe.session.user
        
        if not current_user or current_user == "Guest":
            return {
                "status": "error",
                "message": "Authentication required"
            }

        tag_list = frappe.db.get_all(
            "Tag",
            fields=["name", "rank", "company", "product_type", "description", "image"],
            order_by="rank desc"
        )

        if not tag_list:
            return {
                "status": "success",
                "message": "No tags found",
                "data": []
            }

        for tag in tag_list:
            try:

                tag['image'] = frappe.utils.get_url(tag['image']) if tag['image'] else None
                # Fetch data from the Child Table
                tag['products'] = frappe.db.get_all(
                    "Recommended Products", 
                    filters={
                        "parent": tag.get("name"),
                        "parenttype": "Tag",
                        "parentfield": "products"
                    },
                    fields=["product_name"],
                    pluck="product_name",
                    order_by="idx"
                )
                
                # Handle case where no products are found
                if not tag['products']:
                    tag['products'] = []
                    
            except Exception as product_error:
                frappe.log_error(
                    message=f"Error fetching products for tag {tag.get('name')}: {str(product_error)}\n{frappe.get_traceback()}",
                    title="Tag Products Fetch Error"
                )
                tag['products'] = []

        return tag_list

    except Exception as e:
        frappe.log_error(
            message=f"Error in get_tag_info: {str(e)}\n{frappe.get_traceback()}",
            title="Get Tag Info Failed"
        )
        frappe.local.response["http_status_code"] = 500
        return {
            "status": "error",
            "message": str(e)
        }