import frappe
from frappe import _

def execute(filters=None):
    filters = filters or {}
    
    columns = []
    data = []

    # --- 1. Prepare Item Filters ---
    item_filters = {}
    if filters.get("item_code"):
        item_filters["name"] = filters.get("item_code")
    if filters.get("item_group"):
        item_filters["item_group"] = filters.get("item_group")
    if filters.get("enabled_status"):
        item_filters["disabled"] = 1 if filters.get("enabled_status") == "Disabled" else 0
    if filters.get("missing_main_image"):
        item_filters["image"] = ["in", [None, ""]]
    if filters.get("company"):
        item_filters["company"] = ["=", filters.get("company")]

    # --- 2. Fetch Items ---
    # Added 'brand' or any custom field if you have it to distinguish between Universal/Cotton Valley
    items = frappe.get_all("Item", 
        fields=["name", "image", "item_group", "disabled", "company"], 
        filters=item_filters, 
        order_by="name asc"
    )

    if not items:
        return [], []

    item_names = [item.name for item in items]

    # --- Stock Map Logic (Same as before) ---
    stock_map = {}
    if item_names:
        query = """
            SELECT bin.item_code, SUM(bin.actual_qty) as qty
            FROM `tabBin` bin
            JOIN `tabWarehouse` wh ON bin.warehouse = wh.name
            WHERE bin.item_code IN %(items)s
        """
        params = {"items": item_names}
        if filters.get("company"):
            query += " AND wh.company = %(company)s"
            params["company"] = filters.get("company")
        query += " GROUP BY bin.item_code"
        stock_data = frappe.db.sql(query, params, as_dict=1)
        for d in stock_data:
            stock_map[d.item_code] = d.qty or 0.0

    # --- Child Images (Same as before) ---
    all_child_images = frappe.get_all("Product Images", 
        filters={"parent": ["in", item_names]},
        fields=["parent", "image"], 
        order_by="idx asc"
    )
    image_map = {}
    for img in all_child_images:
        image_map.setdefault(img.parent, []).append(img.image)

    max_images = max(len(imgs) for imgs in image_map.values()) if image_map else 0

    # --- 6. Define Columns ---
    columns = [
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Data", "width": 120},
        {"label": _("Product ID"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
        {"label": _("Product Type"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 120},
        {"label": _("Available Stock"), "fieldname": "stock_qty", "fieldtype": "Float", "width": 130},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": _("Website Link"), "fieldname": "website_link", "fieldtype": "Data", "width": 400},
        {"label": _("Main Image"), "fieldname": "main_image_html", "fieldtype": "HTML", "width": 200}
    ]

    for i in range(1, max_images + 1):
        columns.append({"label": _(f"Image {i}"), "fieldname": f"image_{i}", "fieldtype": "HTML", "width": 100})

    # --- 7. Build Data Rows ---
    for item in items:
        row = {}
        row["item_code"] = item.name
        row["item_group"] = item.item_group
        row["status"] = "Disabled" if item.disabled else "Enabled"
        row["stock_qty"] = stock_map.get(item.name, 0.0)
        row["company"] = item.company

        # --- Dynamic Link Logic ---
        if item.company and "Cotton Valley" in item.company:
            # Cotton Valley ka exact product base URL
            base_url = "https://www.cottonvalley.net/product/" 
        else:
            # Universal product base URL
            base_url = "https://www.universaldc.com/product/"

        product_url = f"{base_url}{item.name}"
        
        row["website_link"] = f'<a href="{product_url}" target="_blank" style="color: #1675e0; font-weight: bold;">{product_url}</a>'

        # Images HTML (Same as before)
        if item.image:
             row["main_image_html"] = f'<img src="{item.image}" style="height: 300px; width: auto; object-fit: contain;">'
        
        current_item_images = image_map.get(item.name, [])
        for i in range(1, max_images + 1):
            col_name = f"image_{i}"
            if (i - 1) < len(current_item_images):
                img_url = current_item_images[i-1]
                if img_url and not img_url.startswith(("http", "/files/")):
                    img_url = f"/files/{img_url}"
                row[col_name] = f'<img src="{img_url}" style="height: 300px; width: auto; object-fit: contain;">' if img_url else ""
            else:
                row[col_name] = ""

        data.append(row)

    return columns, data