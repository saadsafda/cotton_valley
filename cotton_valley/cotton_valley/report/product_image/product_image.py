import frappe
from frappe import _

def execute(filters=None):
    filters = filters or {}
    
    columns = []
    data = []

    # --- 1. Prepare Item Filters ---
    item_filters = {}
    
    # Filter by Item Code
    if filters.get("item_code"):
        item_filters["name"] = filters.get("item_code")

    # [NEW] Filter by Product Type (Item Group)
    if filters.get("item_group"):
        item_filters["item_group"] = filters.get("item_group")

    # [NEW] Filter by Status (Enabled/Disabled)
    if filters.get("enabled_status"):
        if filters.get("enabled_status") == "Enabled":
            item_filters["disabled"] = 0
        elif filters.get("enabled_status") == "Disabled":
            item_filters["disabled"] = 1

    # If the checkbox is checked (returns 1), filter for empty images
    if filters.get("missing_main_image"):
        item_filters["image"] = ["in", [None, ""]]

    # Filter by Company
    if filters.get("company"):
        items_in_company = frappe.get_all("Item Default", 
            filters={"company": filters.get("company")}, 
            pluck="parent"
        )
        
        if not items_in_company:
            return [], [] 
            
        if "name" in item_filters:
            if item_filters["name"] not in items_in_company:
                return [], []
        else:
            item_filters["name"] = ["in", items_in_company]

    # --- 2. Fetch Items ---
    # [UPDATED] Added 'item_group' and 'disabled' to fields
    items = frappe.get_all("Item", 
        fields=["name", "image", "item_group", "disabled"], 
        filters=item_filters, 
        order_by="name asc"
    )

    if not items:
        return [], []

    item_names = [item.name for item in items]

    # --- 3. Fetch Child Images ---
    all_child_images = frappe.get_all("Product Images", 
        filters={"parent": ["in", item_names]},
        fields=["parent", "image"], 
        order_by="idx asc"
    )
    
    image_map = {}
    for img in all_child_images:
        image_map.setdefault(img.parent, []).append(img.image)

    # --- 4. Fetch Company Map ---
    all_defaults = frappe.get_all("Item Default",
        filters={"parent": ["in", item_names]},
        fields=["parent", "company"]
    )

    company_map = {}
    for d in all_defaults:
        if d.company:
            company_map.setdefault(d.parent, set()).add(d.company)

    # --- 5. Determine Dynamic Columns ---
    max_images = 0
    if image_map:
        max_images = max(len(imgs) for imgs in image_map.values())

    # --- 6. Define Columns ---
    columns = [
        {
            "label": _("Company"),
            "fieldname": "company",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Product ID"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 120
        },
        # [NEW] Product Type Column
        {
            "label": _("Product Type"),
            "fieldname": "item_group",
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 120
        },
        # [NEW] Status Column
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Main Image"),
            "fieldname": "main_image_html",
            "fieldtype": "HTML",
            "width": 200
        }
    ]

    for i in range(1, max_images + 1):
        columns.append({
            "label": _(f"Image {i}"),
            "fieldname": f"image_{i}",
            "fieldtype": "HTML",
            "width": 100,
        })

    # --- 7. Build Data Rows ---
    for item in items:
        row = {}
        row["item_code"] = item.name
        
        # [NEW] Map Product Type
        row["item_group"] = item.item_group
        
        # [NEW] Map Status (0=Enabled, 1=Disabled)
        row["status"] = "Disabled" if item.disabled else "Enabled"

        comps = sorted(list(company_map.get(item.name, [])))
        row["company"] = ", ".join(comps)

        # Main Image (Height set to 300px)
        if item.image:
             row["main_image_html"] = f'<img src="{item.image}" style="height: 300px; width: auto; object-fit: contain;">'
        else:
             row["main_image_html"] = ""

        # Dynamic Images (Height set to 300px)
        current_item_images = image_map.get(item.name, [])
        for i in range(1, max_images + 1):
            col_name = f"image_{i}"
            if (i - 1) < len(current_item_images):
                img_url = current_item_images[i-1]
                
                # Fix path if missing /files/
                if img_url and not img_url.startswith("http") and not img_url.startswith("/files/"):
                     img_url = f"/files/{img_url}"

                if img_url:
                    row[col_name] = f'<img src="{img_url}" style="height: 300px; width: auto; object-fit: contain;">'
                else:
                    row[col_name] = ""
            else:
                row[col_name] = ""

        data.append(row)

    return columns, data