# Copyright (c) 2026, Saad and contributors
# For license information, please see license.txt

"""Sales Person Target Hierarchy report.

Renders a Sales Person's `Target Detail` rows as a drill-down tree:

    Category
      └─ Subcategory
            └─ Item

Targets are entered per-row in the Sales Person `targets` table. Each row may
target a Category only, a Category + Subcategory, or a Category + Subcategory
+ Item (cotton_valley custom fields). The report rolls up children into their
parents:
  - Category total      = sum of its Subcategory totals (or its own row when
                          there are no Subcategory / Item rows under it).
  - Subcategory total   = sum of its Item rows (or its own row when there are
                          no Item rows under it).
  - Item total          = the row's own target amount / qty.
"""

import frappe
from frappe import _


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def execute(filters=None):
    filters = filters or {}

    if not filters.get("sales_person"):
        frappe.throw(_("Please select a Sales Person."))
    if not filters.get("fiscal_year"):
        frappe.throw(_("Please select a Fiscal Year."))

    columns = _get_columns()
    data = _get_data(filters)
    return columns, data


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------

def _get_columns():
    return [
        {
            "fieldname": "label",
            "label": _("Category / Subcategory / Item"),
            "fieldtype": "Data",
            "width": 360,
        },
        {
            "fieldname": "row_type",
            "label": _("Level"),
            "fieldtype": "Data",
            "width": 110,
        },
        {
            "fieldname": "reference",
            "label": _("Reference"),
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "fieldname": "target_amount",
            "label": _("Target Amount"),
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "fieldname": "target_qty",
            "label": _("Target Qty"),
            "fieldtype": "Float",
            "width": 120,
        },
    ]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def _get_data(filters):
    sales_person = filters["sales_person"]
    fiscal_year = filters["fiscal_year"]
    company = filters.get("company")
    category_filter = filters.get("category")

    target_rows = frappe.get_all(
        "Target Detail",
        filters={
            "parenttype": "Sales Person",
            "parent": sales_person,
            "fiscal_year": fiscal_year,
        },
        fields=[
            "name",
            "product_category",
            "category_name",
            "product_subcategory",
            "subcategory_name",
            "item_code",
            "item_name",
            "target_amount",
            "target_qty",
        ],
        order_by="idx asc",
    )

    if company:
        # Filter by Product Category's company. Categories without a matching
        # company are excluded.
        allowed = set(
            frappe.get_all(
                "Product Category",
                filters={"company": company},
                pluck="name",
            )
        )
        target_rows = [r for r in target_rows if not r.product_category or r.product_category in allowed]

    if category_filter:
        target_rows = [r for r in target_rows if r.product_category == category_filter]

    if not target_rows:
        return []

    # ------------------------------------------------------------------
    # Build hierarchy:
    #   tree[category] = {
    #       "self": <row dict or None>,
    #       "subcategories": {
    #           subcategory: {
    #               "self": <row dict or None>,
    #               "items": [<row dict>, ...],
    #           }
    #       }
    #   }
    # ------------------------------------------------------------------
    tree = {}

    for r in target_rows:
        category = r.product_category
        subcategory = r.product_subcategory
        item_code = r.item_code

        if not category:
            # A target row without a category cannot be placed in the tree;
            # skip it. (UI allows item_group only rows; out of scope here.)
            continue

        node = tree.setdefault(
            category,
            {"self": None, "subcategories": {}, "title": r.category_name or category},
        )
        if r.category_name and not node.get("title"):
            node["title"] = r.category_name

        if not subcategory and not item_code:
            # Category-level target row.
            node["self"] = r
            continue

        if subcategory:
            sub_node = node["subcategories"].setdefault(
                subcategory,
                {
                    "self": None,
                    "items": [],
                    "title": r.subcategory_name or subcategory,
                },
            )
            if r.subcategory_name and not sub_node.get("title"):
                sub_node["title"] = r.subcategory_name

            if item_code:
                sub_node["items"].append(r)
            else:
                # Subcategory-level target row.
                sub_node["self"] = r
        elif item_code:
            # Item under category but no subcategory recorded: place it under
            # a synthetic "(No Subcategory)" bucket so it is still visible.
            sub_key = "__NO_SUBCATEGORY__"
            sub_node = node["subcategories"].setdefault(
                sub_key,
                {
                    "self": None,
                    "items": [],
                    "title": _("(No Subcategory)"),
                },
            )
            sub_node["items"].append(r)

    # ------------------------------------------------------------------
    # Flatten tree into rows with parent_id / id for tree rendering.
    # ------------------------------------------------------------------
    rows = []

    for category_id in sorted(tree.keys()):
        node = tree[category_id]
        cat_row_id = "cat::" + category_id

        # Compute subcategory totals first so we can roll up to category.
        subcategory_rows = []
        category_amount = 0.0
        category_qty = 0.0
        had_children = False

        for subcategory_key in sorted(node["subcategories"].keys()):
            sub_node = node["subcategories"][subcategory_key]
            sub_row_id = "{0}::sub::{1}".format(cat_row_id, subcategory_key)

            # Item rows under subcategory.
            item_rows = []
            sub_amount = 0.0
            sub_qty = 0.0
            sub_had_children = False

            for item_row in sub_node["items"]:
                amt = float(item_row.target_amount or 0)
                qty = float(item_row.target_qty or 0)
                sub_amount += amt
                sub_qty += qty
                sub_had_children = True

                item_label = item_row.item_name or item_row.item_code
                item_rows.append(
                    {
                        "id": "{0}::item::{1}".format(sub_row_id, item_row.name),
                        "parent_id": sub_row_id,
                        "label": item_label,
                        "row_type": "Item",
                        "reference": item_row.item_code,
                        "target_amount": amt,
                        "target_qty": qty,
                        "indent": 2,
                    }
                )

            # If subcategory has no item rows, fall back to its own row's
            # values (if any).
            if not sub_had_children and sub_node["self"]:
                sub_amount = float(sub_node["self"].target_amount or 0)
                sub_qty = float(sub_node["self"].target_qty or 0)

            subcategory_reference = (
                subcategory_key if subcategory_key != "__NO_SUBCATEGORY__" else ""
            )
            subcategory_rows.append(
                {
                    "id": sub_row_id,
                    "parent_id": cat_row_id,
                    "label": sub_node.get("title") or subcategory_key,
                    "row_type": "Subcategory",
                    "reference": subcategory_reference,
                    "target_amount": sub_amount,
                    "target_qty": sub_qty,
                    "indent": 1,
                    "_children": item_rows,
                }
            )

            category_amount += sub_amount
            category_qty += sub_qty
            had_children = True

        # If category has no subcategory/item rows, fall back to its own row.
        if not had_children and node["self"]:
            category_amount = float(node["self"].target_amount or 0)
            category_qty = float(node["self"].target_qty or 0)

        rows.append(
            {
                "id": cat_row_id,
                "parent_id": "",
                "label": node.get("title") or category_id,
                "row_type": "Category",
                "reference": category_id,
                "target_amount": category_amount,
                "target_qty": category_qty,
                "indent": 0,
            }
        )

        for sub_row in subcategory_rows:
            children = sub_row.pop("_children", [])
            rows.append(sub_row)
            rows.extend(children)

    return rows
