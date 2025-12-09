import frappe
from frappe import _

def execute(filters=None):
    filters = filters or {}
    
    columns = []
    data = []

    # --- 1. Prepare Item Filters ---
    item_filters = {}
    
    # [NEW] Filter by specific Item ID if selected
    if filters.get("item_code"):
        item_filters["name"] = filters.get("item_code")

    # Filter by Company (Your working logic)
    if filters.get("company"):
        items_in_company = frappe.get_all("Item Default", 
            filters={"company": filters.get("company")}, 
            pluck="parent"
        )
        
        if not items_in_company:
            return [], [] 
            
        if "name" in item_filters:
            # If user selected BOTH Item Code and Company, ensure Item is valid for that Company
            if item_filters["name"] not in items_in_company:
                return [], []
        else:
            item_filters["name"] = ["in", items_in_company]

    # --- 2. Fetch Items (Applies the filters defined above) ---
    items = frappe.get_all("Item", 
        fields=["name", "image"], 
        filters=item_filters, 
        order_by="name asc"
    )

    if not items:
        return [], []

    # Create list of names for child table fetching
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
            "width": 150
        },
        {
            "label": _("Product ID"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
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

        comps = sorted(list(company_map.get(item.name, [])))
        row["company"] = ", ".join(comps)

        # Main Image
        if item.image:
             row["main_image_html"] = f'<img src="{item.image}" style="max-height: 200px; max-width: 200px; object-fit: contain; border: 1px solid #ddd;">'
        else:
             row["main_image_html"] = ""

        # Dynamic Images
        current_item_images = image_map.get(item.name, [])
        for i in range(1, max_images + 1):
            col_name = f"image_{i}"
            if (i - 1) < len(current_item_images):
                img_url = current_item_images[i-1]
                if img_url:
                    row[col_name] = f'<img src="{img_url}" style="height: 200px; width: 200px; object-fit: contain;">'
                else:
                    row[col_name] = ""
            else:
                row[col_name] = ""

        data.append(row)

    return columns, data