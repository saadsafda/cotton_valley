import frappe
import csv
from io import StringIO
from frappe import _
from typing import List

@frappe.whitelist()
def export_dual_company_sales_orders(selected_so_names=None):

    # convert selected_so_names to list if it's a string (from JSON)
    if isinstance(selected_so_names, str):
        import json
        selected_so_names = json.loads(selected_so_names)

    # --- 0. Define Dynamic Filters ---
    so_filters = {"docstatus": 1} 

    if selected_so_names and len(selected_so_names) > 0:
        so_filters["name"] = ["in", selected_so_names]

    # 1. Define the Companies and File Names (UPDATED CONFIG)
    export_configs = {
        "Cotton Valley": [
            # Removed 'order_type_filter' here
            {"type": "All", "filename_base": "cotton_valley_all"} 
        ],
        "UDC": [
            {"type": "COD", "filename_base": "udc_cod", "order_type_filter": "COD"},
            {"type": "Regular", "filename_base": "udc_regular", "order_type_filter": "Regular"},
        ],
    }

    # 2. Define the fields to be exported (Unchanged)
    header_fields = ["name", "customer_name", "company", "product_type", 
                     "transaction_date", "grand_total", "status"]
    item_fields = ["parent", "idx", "item_code", "item_name", "qty", "rate", "amount"]
    
    print("Selected SO Names:", so_filters)
    # 3. Fetch all Sales Order Headers and Items (Unchanged)
    all_sales_orders = frappe.get_all(
        "Sales Order",
        filters=so_filters,
        fields=header_fields,
    )
    
    if not all_sales_orders:
        return []

    all_items = frappe.get_all(
        "Sales Order Item",
        filters={"parent": ["in", [so.name for so in all_sales_orders]]},
        fields=item_fields,
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
                
                # Check if an order_type_filter is defined for this config
                order_type_filter = config.get("order_type_filter")
                
                # If filter is defined, check match; otherwise, assume match (for Cotton Valley)
                is_type_match = True
                if order_type_filter:
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

            # --- FILE GENERATION (Unchanged) ---
            file_urls.append(
                _generate_csv_file(
                    data=header_data, 
                    fields=header_fields, 
                    filename=f"SO_HEADER_{config['filename_base']}.csv"
                )
            )

            file_urls.append(
                _generate_csv_file(
                    data=item_data, 
                    fields=item_fields, 
                    filename=f"SO_ITEM_{config['filename_base']}.csv"
                )
            )

    # 5. Return all file URLs
    return [url for url in file_urls if url] 

# Helper function (Unchanged)
def _generate_csv_file(data, fields, filename):
    """Helper function to create a frappe.File document from data and fields."""
    try:
        csv_buffer = StringIO()
        writer = csv.writer(csv_buffer)

        # Write header row
        writer.writerow([f.replace("_", " ").title() for f in fields])

        # Write data rows
        for row in data:
            writer.writerow([row.get(f) for f in fields])

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