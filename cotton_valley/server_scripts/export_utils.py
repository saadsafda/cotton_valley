import frappe
import csv
import json
from io import StringIO
from frappe import _
from typing import List

# --- START OF HELPER FUNCTION ---
def _generate_csv_file(data, header_map, filename, forSO=True):
    """
    Helper function to create a frappe.File document from data.
    It builds the CSV row directly from the header_map.
    """
    try:
        csv_buffer = StringIO()
        writer = csv.writer(csv_buffer)

        if forSO:
            # remove company and order type columns from header_map
            header_map = [item for item in header_map if item[0] not in ("company", "product_type")]

        # 1. Get header aliases from the map
        header_aliases = [item[1] for item in header_map]
        writer.writerow(header_aliases)

        # 2. Write data rows
        for row in data:
            # Build the full output row, including blanks
            output_row = []
            
            # Iterate through the map, which defines the correct order
            for field_name, alias in header_map:
                if field_name is None:
                    # This is a defined blank column
                    output_row.append(None) 
                else:
                    # This is a data column, get the value
                    output_row.append(row.get(field_name))
            
            writer.writerow(output_row)

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
            selected_so_names = []

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

    # 2. Define the fields to be exported (FIXED: Using unified header map)
    
    # 2a. UNIFIED HEADER MAP: (DocType Field Name, CSV Column Header)
    # Use None for fields that should be blank columns
    header_map = [
        ("name", "Order ID"),
        ("transaction_date", "Date"),
        ("submit_datetime", "Numeric Time"),
        ("customer_account_number", "Account"),
        ("shipping_address_details", "Shipping Address 1"),
        (None, "Shipping Address 2"), # Blank Column
        ("shipping_city", "Ship City"),
        ("shipping_state", "Ship State"),
        ("shipping_country", "Ship Country"),
        ("shipping_zip_code", "Ship Zip"),
        (None, "Shipping Phone"),     # Blank Column
        ("customer_name", "Bill Name"),
        ("billing_address_details", "Billing Address 1"),
        (None, "Billing Address 2"),  # Blank Column
        ("billing_city", "Bill City"),
        ("state", "Bill State"), # Verify this field name
        ("country", "Bill Country"), # Verify this field name
        ("zip_code", "Bill Zip"), # Verify this field name
        (None, "Billing Phone"),      # Blank Column
        ("custom_customer_email", "Email"),
        (None, "Referring Page"),     # Blank Column
        (None, "Entry Point"),        # Blank Column
        (None, "Shipping"),           # Blank Column
        ("custom_mode_of_payment", "Payment Method"),
        (None, "Card Number"),        # Blank Column
        (None, "Card Expiry"),        # Blank Column
        (None, "Comments"),           # Blank Column
        ("grand_total", "Total"),
        (None, "Link From"),          # Blank Column
        (None, "Warning"),            # Blank Column
        (None, "Auth Code"),          # Blank Column
        (None, "AVS Code"),           # Blank Column
        (None, "Gift Message"),       # Blank Column
        ("custom_notes", "Notes"),
        ("company", "Company"),
        ("product_type", "Order Type")
    ]
    
    # Generate the list of actual fields to fetch
    actual_header_fields = [item[0] for item in header_map if item[0] is not None]

    # 2b. Item Fields (Unchanged)
    actual_item_fields = ["parent", "idx", "item_code", "qty", "rate"]
    item_header_map = [
        ("parent", "Order ID"), 
        ("idx", "Line ID"), 
        ("item_code", "Product ID"), 
        (None, "Product Code"), 
        ("qty", "Quantity"), 
        ("rate", "Unit Price")
    ]

    
    # 3. Fetch all Sales Order Headers and Items 
    all_sales_orders = frappe.get_all(
        "Sales Order",
        filters=so_filters,
        fields=actual_header_fields, # Use the list with only actual fields
    )

    # check if there are any sales order who already exported
    already_exported_sos = [so for so in all_sales_orders if so.get("exported") == 1]
    if already_exported_sos:
        already_exported_names = [so.get("name") for so in already_exported_sos]
        frappe.log_error(
            title="Some Sales Orders Already Exported", 
            message=f"The following Sales Orders have already been exported and will be skipped: {', '.join(already_exported_names)}"
        )
        # Filter them out from the main list
        all_sales_orders = [so for so in all_sales_orders if so.get("exported") != 1]
    
    if not all_sales_orders:
        return []

    all_items = frappe.get_all(
        "Sales Order Item",
        filters={"parent": ["in", [so.name for so in all_sales_orders]]},
        fields=actual_item_fields,
        order_by="parent, idx"
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
                    is_type_match = so.get("product_type") == order_type_filter 
                
                if is_company_match and is_type_match:
                    header_data.append(so)
                    target_so_names.append(so.name)

            if not header_data:
                frappe.log_error(title=f"No SOs for {company_name}", message=f"No filtered Sales Orders found for {company_name} ({config['type']}).")
                continue

            # 4b. Filter Sales Order Items
            item_data = [
                item for item in all_items if item.get("parent") in target_so_names
            ]

            # --- FILE GENERATION (Passing the maps) ---
            file_urls.append(
                _generate_csv_file(
                    data=header_data, 
                    header_map=header_map, # Pass the full header map
                    filename=f"SO_HEADER_{config['filename_base']}.csv",
                    forSO=True 
                )
            )

            file_urls.append(
                _generate_csv_file(
                    data=item_data, 
                    header_map=item_header_map, # Pass the item map
                    filename=f"SO_ITEM_{config['filename_base']}.csv",
                    forSO=False 
                )
            )
            
            # Mark all exported sales orders as exported
            for so_name in target_so_names:
                try:
                    frappe.db.set_value("Sales Order", so_name, "exported", 1)
                except Exception as e:
                    frappe.log_error(title=f"Failed to mark SO as exported: {so_name}", message=str(e))
            
            # Commit the changes
            frappe.db.commit()

    # 5. Return all file URLs
    return [url for url in file_urls if url]