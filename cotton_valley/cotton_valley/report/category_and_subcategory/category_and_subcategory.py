# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe


def _resolve_item_category_mapping():
    """Resolve Item's category child table and linked category field.

    Item categories are stored in Item table-multiselect field `custom_product_categories`.
    This returns the child doctype and the field that links to Product Category.
    """
    item_meta = frappe.get_meta("Item")
    table_field = item_meta.get_field("custom_product_categories")

    child_dt = table_field.options if table_field and table_field.options else None
    if not child_dt:
        return None, None

    cat_field = None
    child_meta = frappe.get_meta(child_dt)
    for df in child_meta.fields:
        if df.fieldtype == "Link" and df.options == "Product Category":
            cat_field = df.fieldname
            break

    return child_dt, cat_field

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
            "width": 170
        },
        {
            "fieldname": "subcategory_id",
            "label": "Subcategory ID",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "subcategory_name",
            "label": "Subcategory Name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "item_count",
            "label": "Item Count",
            "fieldtype": "Int",
            "width": 90
        }
    ]

def get_data(filters):
    child_dt, cat_field = _resolve_item_category_mapping()

    # Fallback: if category mapping is not configured, preserve old behavior.
    if not child_dt or not cat_field:
        query = """
            SELECT
                p.company as company,
                p.name as category_id,
                p.title as category_title,
                c.product_subcategory as subcategory_id,
                c.subcategory_name as subcategory_name,
                COALESCE(
                    (SELECT COUNT(*)
                     FROM `tabItem`
                     WHERE custom_sub_category = c.product_subcategory
                     AND hide = 0),
                    0
                ) as item_count
            FROM
                `tabProduct Category` p
            JOIN
                `tabSubCategories` c ON c.parent = p.name
            WHERE
                1=1
        """

        conditions = ""
        query_values = {}

        if filters.get("company"):
            conditions += " AND p.company = %(company)s"
            query_values["company"] = filters.get("company")

        if filters.get("category"):
            conditions += " AND p.name = %(category)s"
            query_values["category"] = filters.get("category")

        if filters.get("subcategory"):
            conditions += " AND c.product_subcategory = %(subcategory)s"
            query_values["subcategory"] = filters.get("subcategory")

        final_query = query + conditions + " ORDER BY p.company ASC, p.name ASC, c.product_subcategory ASC"
        return frappe.db.sql(final_query, query_values, as_dict=True)

    # Base query with item count by category + subcategory.
    query = """
        SELECT
            p.company as company,
            p.name as category_id,
            p.title as category_title,
            c.product_subcategory as subcategory_id,
            c.subcategory_name as subcategory_name,
            COALESCE(
                (
                    SELECT COUNT(DISTINCT i.name)
                    FROM `tabItem` i
                    INNER JOIN `tab{child_dt}` ic
                        ON ic.parent = i.name
                        AND ic.parenttype = 'Item'
                        AND ic.parentfield = 'custom_product_categories'
                    WHERE i.custom_sub_category = c.product_subcategory
                                            AND i.hide = 0
                      AND ic.`{cat_field}` = p.name
                ),
                0
            ) as item_count
        FROM
            `tabProduct Category` p
        JOIN
            `tabSubCategories` c ON c.parent = p.name
        WHERE
            1=1
    """.format(child_dt=child_dt, cat_field=cat_field)

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
    final_query = query + conditions + " ORDER BY p.company ASC, p.name ASC, c.product_subcategory ASC"

    # Execute and return
    return frappe.db.sql(final_query, query_values, as_dict=True)