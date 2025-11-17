import frappe
import csv
import json
from io import StringIO
from frappe import _
from typing import List

# --- START OF HELPER FUNCTION (Modified to handle separate fields and aliases) ---
def _generate_csv_file(data, actual_fields, header_aliases, filename, forSO=True):
    """Helper function to create a frappe.File document from data, fields, and aliases."""
    try:
        csv_buffer = StringIO()
        writer = csv.writer(csv_buffer)

        # 1. Write the explicit header row using the aliases
        writer.writerow(header_aliases)

        # Get indices for empty columns (only if they exist in header_aliases)
        if forSO:
            empty_columns = {
                "Shipping Phone": None,
                "Billing Phone": None,
                "Referring Page": None,
                "Entry Point": None,
                "Shipping": None,
                "Card Number": None,
                "Card Expiry": None,
                "Comments": None,
                "Link From": None,
                "Warning": None,
                "Auth Code": None,
                "AVS Code": None,
                "Gift Message": None
            }
            
            # Build a list of (index, None) tuples for columns that exist
            inserts_to_make = []
            for col_name in empty_columns.keys():
                try:
                    idx = header_aliases.index(col_name)
                    inserts_to_make.append(idx)
                except ValueError:
                    # Column doesn't exist in header_aliases, skip it
                    pass
            
            # Sort indices in descending order to insert from right to left
            inserts_to_make.sort(reverse=True)

        # 2. Write data rows using the actual field names to fetch values
        for row in data:
            fetched_values = [row.get(f) for f in actual_fields]
            
            # Insert None values at the appropriate positions
            if forSO:
                for idx in inserts_to_make:
                    fetched_values.insert(idx, None)
            
            writer.writerow(fetched_values)

        csv_content = csv_buffer.getvalue().encode('utf-8')

        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "attached_to_doctype": "Sales Order",
            "attached_to_name": frappe.generate_hash(),
            "content": csv_content,
            "is_private": 0,
        })
        file_doc.flags.ignore_permissions = True
        file_doc.insert()
        return file_doc.file_url

    except Exception as e:
        frappe.log_error(title=f"CSV Generation Failed: {filename}", message=str(e))
        return None
# --- END OF HELPER FUNCTION ---


@frappe.whitelist()
def export_dual_company_sales_orders(selected_so_names=None):

    # 0a. Handle input (keep your type handling logic)
    if isinstance(selected_so_names, str):
        try:
            selected_so_names = json.loads(selected_so_names)
        except json.JSONDecodeError:
            selected_so_names = [] # Handle case where JSON is malformed

    # --- 0. Define Dynamic Filters ---
    so_filters = {"docstatus": 1} 
    if selected_so_names and len(selected_so_names) > 0:
        so_filters["name"] = ["in", selected_so_names]


    # 1. Define the Companies and File Names (Unchanged)
    export_configs = {
        "Cotton Valley": [
            {"type": "All", "filename_base": "cotton_valley_all"} 
        ],
        "UDC": [
            {"type": "COD", "filename_base": "udc_cod", "order_type_filter": "COD"},
            {"type": "Regular", "filename_base": "udc_regular", "order_type_filter": "Regular"},
        ],
    }

    # 2. Define the fields to be exported (FIXED: Separate actual fields and aliases)
    
    # 2a. Header Fields
    actual_header_fields = ["name", "transaction_date", 
                            "submit_datetime", "customer_account_number",
                            "shipping_address_details", "shipping_city",
                            "shipping_state", "shipping_country",
                            "shipping_zip_code", "customer_name",
                            "billing_address_details", "billing_city", 
                            "state", "country", "zip_code", 
                            "custom_customer_email", "custom_mode_of_payment",
                            "grand_total", "custom_notes", "company", "product_type"] # Added company & order_type for filtering
    
    header_aliases = ["Order ID", "Date", 
                      "Numeric Time", "Account",
                      "Shipping Address 1", "Ship City",
                      "Ship State", "Ship Country",
                      "Ship Zip",  "Bill Name", "Billing Address 1",
                      "Bill City", "Bill State", "Bill Country", "Bill Zip", 
                      "Email", "Payment Method", "Total", "Notes",
                      "Company", "Order Type", "Billing Phone",
                      "Shipping Address 2", "Billing Address 2", "Shipping Phone",
                      "Referring Page", "Entry Point", "Shipping", "Card Number",
                      "Card Expiry", "Comments", "Link From", "Warning", "Auth Code",
                      "AVS Code", "Gift Message",] # Added Company & Order Type aliases

    # 2b. Item Fields
    actual_item_fields = ["parent", "idx", "item_code", "item_name", "qty", "rate"]
    item_aliases = ["Order ID", "Line ID", "Product ID", "Item Name", "Quantity", "Unit Price"]

    
    # 3. Fetch all Sales Order Headers and Items (Using actual_fields)
    all_sales_orders = frappe.get_all(
        "Sales Order",
        filters=so_filters,
        fields=actual_header_fields,
    )
    
    if not all_sales_orders:
        return []

    all_items = frappe.get_all(
        "Sales Order Item",
        filters={"parent": ["in", [so.name for so in all_sales_orders]]},
        fields=actual_item_fields,
        order_by="idx"
    )

    # 4. Process and Generate Files
    file_urls = []

    for company_name, configs in export_configs.items():
        
        for config in configs:
            
            target_so_names = []
            header_data = []
            
            # 4a. Filter Sales Order Headers 
            for so in all_sales_orders:
                is_company_match = so.get("company") == company_name
                
                order_type_filter = config.get("order_type_filter")
                
                is_type_match = True
                if order_type_filter:
                    # ✅ FIXED: Assuming the field is 'order_type' on Sales Order DocType
                    is_type_match = so.get("product_type") == order_type_filter 
                
                if is_company_match and is_type_match:
                    header_data.append(so)
                    target_so_names.append(so.name)

            if not header_data:
                frappe.log_error(title=f"No SOs for {company_name}", message=f"No filtered Sales Orders found for {company_name} ({config['type']}).")
                continue

            # 4b. Filter Sales Order Items (Unchanged)
            item_data = [
                item for item in all_items if item.get("parent") in target_so_names
            ]

            # --- FILE GENERATION (Passing actual fields and aliases) ---
            file_urls.append(
                _generate_csv_file(
                    data=header_data, 
                    actual_fields=actual_header_fields, 
                    header_aliases=header_aliases,
                    filename=f"SO_HEADER_{config['filename_base']}.csv",
                    forSO=True
                )
            )

            file_urls.append(
                _generate_csv_file(
                    data=item_data, 
                    actual_fields=actual_item_fields, 
                    header_aliases=item_aliases,
                    filename=f"SO_ITEM_{config['filename_base']}.csv",
                    forSO=False
                )
            )

    # 5. Return all file URLs
    return [url for url in file_urls if url]