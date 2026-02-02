import frappe

def execute(filters=None):
    # Agar filters None ho to empty dict bana lein taake error na aye
    if not filters: filters = {}

    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "fieldname": "item_code",
            "label": "Item Code",
            "fieldtype": "Data",
            "options": "Item",
            "align": "left",
            "width": 120
        },
        {
            "fieldname": "item_name",
            "label": "Item Name",
            "fieldtype": "Data",
            "width": 450
        },
        {
            "fieldname": "company",
            "label": "Company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 120
        },
        {
            "fieldname": "item_group",
            "label": "Product Type",
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 120
        },
        {
            "fieldname": "available_stock",
            "label": "Available Stock",
            "fieldtype": "Float",
            "width": 110
        },
        {
            "fieldname": "threshold_stock",
            "label": "Threshold Stock",
            "fieldtype": "Float",
            "width": 110
        }
    ]

def get_data(filters):
    
    # 1. Base Condition (Jo hamesha rahegi: Stock Mismatch)
    conditions = ["CAST(IFNULL(available_stock, 0) AS DECIMAL(10,3)) != CAST(IFNULL(threshold_stock, 0) AS DECIMAL(10,3))"]

    # 2. Filters Logic (Agar user ne filter diya hai to condition add karo)
    
    # Item Code Filter
    if filters.get("item_code"):
        conditions.append("name = %(item_code)s")

    # Item Name Filter (Partial Match ke liye LIKE use kiya)
    if filters.get("item_name"):
        filters["item_name"] = f"%{filters['item_name']}%" # Wildcards add kiye
        conditions.append("item_name LIKE %(item_name)s")

    # Company Filter
    if filters.get("company"):
        conditions.append("company = %(company)s")

    # Product Type (Item Group) Filter
    if filters.get("item_group"):
        conditions.append("item_group = %(item_group)s")

    # 3. Conditions ko SQL ke liye join karna
    where_clause = " AND ".join(conditions)

    sql_query = f"""
        SELECT
            name as item_code,
            item_name,
            company,
            item_group,
            CAST(available_stock AS DECIMAL(10,3)) as available_stock,
            CAST(threshold_stock AS DECIMAL(10,3)) as threshold_stock
        FROM
            `tabItem`
        WHERE
            {where_clause}
    """
    
    # 4. Query Execute (Filters pass kiye taake values replace ho sakein)
    data = frappe.db.sql(sql_query, filters, as_dict=True)
    return data