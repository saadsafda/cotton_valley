# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data

def get_columns():
    return [
        {
            "fieldname": "company",
            "label": "Company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 150
        },
        {
            "fieldname": "category_id",
            "label": "Category ID",
            "fieldtype": "Link",
            "options": "Product Category",
            "width": 120
        },
        {
            "fieldname": "category_title",
            "label": "Category",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "subcategory_id",
            "label": "Subcategory ID",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "subcategory_name",
            "label": "Subcategory Name",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "item_count",
            "label": "Item Count",
            "fieldtype": "Int",
            "width": 120
        }
    ]

def get_data(filters):
    # Base query with item count
    query = """
        SELECT
            p.company as company,
            p.name as category_id,
            p.title as category_title,
            c.product_subcategory as subcategory_id,
            c.subcategory_name as subcategory_name,
            COALESCE(
                (SELECT COUNT(*) FROM `tabItem` WHERE custom_sub_category = c.product_subcategory AND disabled = 0),
                0
            ) as item_count
        FROM
            `tabProduct Category` p
        JOIN
            `tabSubCategories` c ON c.parent = p.name
        WHERE
            1=1
    """

    # Dynamic conditions based on filters
    conditions = ""
    query_values = {}

    # 1. Filter by Company
    if filters.get("company"):
        conditions += " AND p.company = %(company)s"
        query_values["company"] = filters.get("company")

    # 2. Filter by Category
    if filters.get("category"):
        conditions += " AND p.name = %(category)s"
        query_values["category"] = filters.get("category")

    # 3. Filter by Subcategory
    # Matches the 'subcategory' filter from JS to the child table column
    if filters.get("subcategory"):
        conditions += " AND c.product_subcategory = %(subcategory)s"
        query_values["subcategory"] = filters.get("subcategory")

    # Combine query and conditions
    final_query = query + conditions

    # Execute and return
    return frappe.db.sql(final_query, query_values, as_dict=True)