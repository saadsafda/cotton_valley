import frappe
from frappe.utils import flt

from cotton_valley.api.sales_team import get_acting_sales_person


def _set_sales_invoice_customer_fields(si, customer_id, company, erp_si_number):
    # Credit the logged-in rep when they are on this customer's sales team,
    # otherwise fall back to the customer's primary rep.
    sales_person = get_acting_sales_person(customer_id, company)
    account_number = frappe.db.get_value(
        "Customer",
        customer_id,
        "udc_account_number" if company == "UDC" else "account_number",
    )

    si.custom_customer_sales_representative = sales_person
    si.custom_customer_account_number = account_number
    si.erp_si_number = erp_si_number


def _apply_sales_invoice_items(si, items, discount_percentage, sales_order):
    # Rebuild items to ensure updates are applied after reloads.
    si.items = []
    for item in items:
        item_discount_percentage = flt(item.get("discount_percentage"))
        item_discount_amount = flt(item.get("discount_amount"))

        # The incoming rate is the list price, before any discount. Every
        # margin/discount field is computed off price_list_rate and is skipped
        # entirely when it is 0 (see calculate_margin), so send it there and let
        # ERPNext derive the net rate from the discount below.
        price_list_rate = flt(item.get("price_list_rate")) or flt(item.get("rate"))

        item_dict = {
            "item_code": item.get("item_code"),
            "qty": item.get("qty"),
            "price_list_rate": price_list_rate,
            "sales_order": sales_order,
        }

        # margin_type is a markup (rate_with_margin = price_list_rate + margin),
        # not a discount, and it only applies when paired with an amount.
        margin_type = item.get("margin_type")
        margin_rate_or_amount = flt(item.get("margin_rate_or_amount"))
        if margin_type in ("Percentage", "Amount") and margin_rate_or_amount:
            item_dict["margin_type"] = margin_type
            item_dict["margin_rate_or_amount"] = margin_rate_or_amount

        # Discounts stay on the discount fields; ERPNext applies them after the
        # margin. Sending both would let discount_percentage win and overwrite
        # discount_amount, so prefer the percentage when both are supplied.
        if item_discount_percentage:
            # Left with no rate, calculate_item_values derives it from the
            # discount for us.
            item_dict["discount_percentage"] = item_discount_percentage
        elif item_discount_amount:
            # discount_amount is only self-applied for rows carrying a pricing
            # rule, so set the resulting rate here.
            item_dict["discount_amount"] = item_discount_amount
            item_dict["rate"] = price_list_rate - item_discount_amount
        else:
            item_dict["rate"] = price_list_rate

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
def create_sales_invoice(sales_order, items, discount_percentage=0, erp_si_number=''):
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

        # An empty item list leaves si.items empty, and ERPNext's
        # set_payment_schedule() then does items[0] -> IndexError.
        if not items:
            return {
                "status": "error",
                "message": "Cannot create a Sales Invoice without any items."
            }

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

        _set_sales_invoice_customer_fields(si, so.customer, so.company, erp_si_number)

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
