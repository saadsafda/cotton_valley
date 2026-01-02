import frappe
from cotton_valley.api.website_theme_setting import get_file


@frappe.whitelist(allow_guest=True)
def get_category_list(category_id=None, company=None):
    company = "Cotton Valley" if not company or company == "null" else company
    # apply filter only if category_id is passed
    filters = {}

    if company:
        filters["company"] = company

    if category_id:
        filters["name"] = category_id

    # get categories - use SQL for complex sorting with null/0 handling
    filter_conditions = []
    filter_values = []
    
    if company:
        filter_conditions.append("company = %s")
        filter_values.append(company)
    
    if category_id:
        filter_conditions.append("name = %s")
        filter_values.append(category_id)
    
    where_clause = " AND ".join(filter_conditions) if filter_conditions else "1=1"
    
    categories = frappe.db.sql(f"""
        SELECT name, title, category_image, banner_image
        FROM `tabProduct Category`
        WHERE {where_clause}
        ORDER BY 
            CASE WHEN web_ranking IS NULL OR web_ranking = 0 THEN 1 ELSE 0 END,
            web_ranking ASC
    """, tuple(filter_values), as_dict=True)

    if not categories:
        return {"data": []}

    # get counts of items from child table
    item_counts = frappe.db.sql("""
        SELECT c.product_category as category, COUNT(DISTINCT i.name) as total
        FROM `tabItem` i
        INNER JOIN `tabProduct Categoris` c
            ON c.parent = i.name
        WHERE c.product_category IS NOT NULL
            AND i.company = %s
        GROUP BY c.product_category
    """, company, as_dict=True)
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
        WHERE sub.company = %s
        ORDER BY 
            CASE WHEN sub.web_ranking IS NULL OR sub.web_ranking = 0 THEN 1 ELSE 0 END,
            sub.web_ranking ASC
    """, company, as_dict=True)

    # group subcategories under their parent category
    sub_map = {}
    for sub in subcategories:
        sub_map.setdefault(sub["parent_category"], []).append({
            "name": sub["title"],
            "title": sub["title"],
            "id": sub["name"],
            "slug": sub["name"],
            "type": "product",
            "products_count": frappe.db.count("Item", filters=[["custom_sub_category", "in", [sub["name"]]]])
        })

    # attach count and subcategories
    for cat in categories:
        cat['id'] = cat["name"]
        cat['slug'] = cat["name"]
        cat['name'] = cat["title"]
        cat['category_image'] = get_file(cat["category_image"])
        cat["products_count"] = counts_map.get(cat["id"], 0)
        cat["subcategories"] = sub_map.get(cat["id"], [])
        cat["banner_image"] = get_file(cat["banner_image"])
        cat["type"] = "product"

    return {"data": categories}