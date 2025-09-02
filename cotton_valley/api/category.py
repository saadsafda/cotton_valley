import frappe
from cotton_valley.api.website_theme_setting import get_file


@frappe.whitelist(allow_guest=True)
def get_categories():
    categories = frappe.get_all("Category", fields=["name", "category_name"])
    return categories

@frappe.whitelist(allow_guest=True)
def get_category_list(category_id=None):
    # apply filter only if category_id is passed
    filters = {}
    if category_id:
        filters["name"] = category_id

    # get categories
    categories = frappe.get_all(
        "Product Category",
        filters=filters,
        fields=["name", "title", "category_image"]
    )

    if not categories:
        return {"data": []}

    # get counts of items from child table
    item_counts = frappe.db.sql("""
        SELECT c.product_category as category, COUNT(DISTINCT i.name) as total
        FROM `tabItem` i
        INNER JOIN `tabProduct Categoris` c
            ON c.parent = i.name
        WHERE c.product_category IS NOT NULL
        GROUP BY c.product_category
    """, as_dict=True)
    counts_map = {row["category"]: row["total"] for row in item_counts}

    # fetch child subcategories linked inside Product Category
    subcategories = frappe.db.sql("""
        SELECT sc.parent as parent_category,
               sc.product_subcategory as subcategory,
               sub.title,
               sub.name
        FROM `tabSubCategories` sc
        INNER JOIN `tabProduct Subcategory` sub
            ON sub.name = sc.product_subcategory
    """, as_dict=True)

    # group subcategories under their parent category
    sub_map = {}
    for sub in subcategories:
        sub_map.setdefault(sub["parent_category"], []).append({
            "name": sub["title"],
            "title": sub["title"],
            "id": sub["name"],
            "slug": sub["name"],
            "type": "product"
        })

    # attach count and subcategories
    for cat in categories:
        cat['id'] = cat["name"]
        cat['slug'] = cat["name"]
        cat['name'] = cat["title"]
        cat['category_image'] = get_file(cat["category_image"])
        cat["products_count"] = counts_map.get(cat["id"], 0)
        cat["subcategories"] = sub_map.get(cat["id"], [])
        cat["type"] = "product"

    return {"data": categories}