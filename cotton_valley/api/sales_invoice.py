import frappe


@frappe.whitelist(allow_guest=True)
def create_sales_invoice(sales_order, items, discount_percentage=0):
    """
    Create a Sales Invoice from a Sales Order with specified items.
    
    Args:
        sales_order: Sales Order ID
        items: List of items to include in the Sales Invoice
    """
    try:
        if isinstance(items, str):
            items = frappe.parse_json(items)
        # Fetch the Sales Order document
        if not frappe.db.exists("Sales Order", sales_order):
            return {
                "status": "error",
                "message": "Sales Order not found"
            }
        
        so = frappe.get_doc("Sales Order", sales_order)
        
        # Create or update Sales Invoice document
        si_exists = frappe.get_all("Sales Invoice", filters=[["Sales Invoice Item","sales_order","=", sales_order]])

        if len(si_exists) > 0:
            si = frappe.get_doc("Sales Invoice", si_exists[0].name)
            si.items = []  # Clear existing items
        else:
            si = frappe.get_doc({
                "doctype": "Sales Invoice",
                "customer": so.customer,
                "sales_order": sales_order,
                "posting_date": frappe.utils.nowdate(),
                "due_date": frappe.utils.add_days(frappe.utils.nowdate(), 30),
                "company": so.company,
                "items": [],
                "customer_address": so.customer_address,
                "shipping_address_name": so.shipping_address_name
            })

            for member in so.sales_team:
                si.append("sales_team", {
                    "sales_person": member.sales_person,
                    "allocated_percentage": member.allocated_percentage,
                    "allocated_amount": member.allocated_amount
                })

        # Add specified items to Sales Invoice
        for item in items:
            si.append("items", {
                "item_code": item.get("item_code"),
                "qty": item.get("qty"),
                "rate": item.get("rate"),
                "amount": item.get("amount"),
                "sales_order": sales_order
            })
        # Apply discount if provided
        if discount_percentage > 0:
            si.apply_discount_on = "Grand Total"
            si.additional_discount_percentage = discount_percentage
        si.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "status": "success",
            "message": f"Sales Invoice {'updated' if len(si_exists) > 0 else 'created'} successfully",
            "sales_invoice_id": si.name
        }
    
    except Exception as e:
        frappe.log_error("Sales Invoice Creation Failed", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }