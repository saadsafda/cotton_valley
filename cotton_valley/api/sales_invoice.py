import frappe


def _apply_sales_invoice_items(si, items, discount_percentage, sales_order):
    # Rebuild items to ensure updates are applied after reloads.
    si.items = []
    for item in items:
        item_dict = {
            "item_code": item.get("item_code"),
            "qty": item.get("qty"),
            "rate": item.get("rate"),
            "amount": item.get("amount"),
            "sales_order": sales_order,
        }
        if item.get("discount_percentage"):
            item_dict["discount_percentage"] = item.get("discount_percentage")
        if item.get("discount_amount"):
            item_dict["discount_amount"] = item.get("discount_amount")
        si.append("items", item_dict)
    if discount_percentage > 0:
        si.apply_discount_on = "Grand Total"
        si.additional_discount_percentage = discount_percentage


def _save_sales_invoice_with_retry(si, items, discount_percentage, sales_order):
    for _ in range(2):
        try:
            si.save(ignore_permissions=True)
            return
        except Exception as e:
            message = str(e)
            if "Document has been modified after you have opened it" in message:
                if not si.is_new():
                    si.reload()
                    _apply_sales_invoice_items(si, items, discount_percentage, sales_order)
                    continue
            raise


@frappe.whitelist()
def create_sales_invoice(sales_order, items, discount_percentage=0):
    """
    Create a Sales Invoice from a Sales Order with specified items.
    
    Args:
        sales_order: Sales Order ID
        items: List of items to include in the Sales Invoice. Each item can have:
               - item_code: Item code
               - qty: Quantity
               - rate: Rate per unit
               - amount: Total amount
               - discount_percentage (optional): Item-wise discount percentage
               - discount_amount (optional): Item-wise discount amount
        discount_percentage: Global discount percentage (applied to Grand Total)
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

        _apply_sales_invoice_items(si, items, discount_percentage, sales_order)
        _save_sales_invoice_with_retry(si, items, discount_percentage, sales_order)
        frappe.db.commit()

        so.db_set("order_status", "Shipped", update_modified=True)
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
    

@frappe.whitelist(allow_guest=True)
def delete_sales_invoice(sales_order):
    try:
        # Fetch the Sales Order document
        if not frappe.db.exists("Sales Order", sales_order):
            return {
                "status": "error",
                "message": "Sales Order not found"
            }
        
        si_exists = frappe.get_all("Sales Invoice", filters=[["Sales Invoice Item","sales_order","=", sales_order]])
        if len(si_exists) == 0:
            return {
                "status": "error",
                "message": "Sales Invoice not found for the given Sales Order"
            }
        
        si = frappe.get_doc("Sales Invoice", si_exists[0].name)
        si.delete()
        frappe.db.commit()
        return {
            "status": "success",
            "message": "Sales Invoice deleted successfully"
        }
    except Exception as e:
        frappe.log_error("Sales Invoice Deletion Failed", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }
