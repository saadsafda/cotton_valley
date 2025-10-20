import frappe


@frappe.whitelist()
def get_all_customers():
    """Fetch all customers from the database."""
    try:
        customers = frappe.get_list(
            "Customer", 
            fields=["name", "customer_name", "account_number", "custom_company_name as customer_company", "price_list_for_cv", "price_list_for_udc"]
        )
        
        if not customers:
            return {
                "status": "success",
                "message": "No customers found",
                "data": []
            }
        
        return {
            "status": "success",
            "message": "Customers fetched successfully",
            "data": customers,
            "count": len(customers)
        }
        
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "status": "error",
            "message": "Customer doctype does not exist"
        }
    except frappe.PermissionError:
        frappe.local.response["http_status_code"] = 403
        return {
            "status": "error",
            "message": "You do not have permission to access customers"
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get All Customers Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "status": "error",
            "message": "An error occurred while fetching customers",
            "error": str(e)
        }

