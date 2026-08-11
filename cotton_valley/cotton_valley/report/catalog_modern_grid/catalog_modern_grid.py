# Copyright (c) 2026, Saad and contributors
# For license information, please see license.txt

import os

import frappe
from frappe import _
from frappe.utils import get_url, get_fullname, now_datetime, flt, cint

SEP = "||"

# -----------------------------
# SORT MAP (safe whitelist)
# -----------------------------
SORT_MAP = {
    "Ascending Order":  "it.name ASC",
    "Descending Order": "it.name DESC",
    "Low-High Price":   "MAX(ip.price_list_rate) ASC",
    "High-Low Price":   "MAX(ip.price_list_rate) DESC",
    "A-Z Order":        "it.item_name ASC",
    "Z-A Order":        "it.item_name DESC",
}

DEFAULT_ORDER = "CASE WHEN it.website_ranking IS NULL OR it.website_ranking = 0 THEN 1 ELSE 0 END ASC, it.website_ranking ASC"


def _get_order_clause(filters):
    """Return a safe, whitelisted ORDER BY expression from the sort filter."""
    sort = (filters.get("sort") or "").strip()
    return SORT_MAP.get(sort, DEFAULT_ORDER)


# -----------------------------
# QUERY REPORT REQUIRED API
# -----------------------------
def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 120},
        {"label": _("Image"), "fieldname": "image", "fieldtype": "HTML", "width": 90},
        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 260},

        {"label": _("Category Code"), "fieldname": "category_code", "fieldtype": "Data", "width": 180},
        {"label": _("Category Name"), "fieldname": "category_name", "fieldtype": "Data", "width": 220},
        {"label": _("Sub-Category Code"), "fieldname": "subcategory_code", "fieldtype": "Data", "width": 200},
        {"label": _("Sub-Category Name"), "fieldname": "subcategory_name", "fieldtype": "Data", "width": 220},

        {"label": _("Price List Rate"), "fieldname": "price_list_rate", "fieldtype": "Currency", "options": "currency", "width": 130},
        {"label": _("UOM"), "fieldname": "stock_uom", "fieldtype": "Data", "width": 80},
    ]


def _split_codes(val):
    if not val:
        return []
    return [x.strip() for x in val.split(SEP) if x and x.strip()]


def _get_titles_map(doctype, names):
    if not names:
        return {}

    meta = frappe.get_meta(doctype)
    title_field = meta.title_field or "name"

    rows = frappe.get_all(
        doctype,
        filters={"name": ["in", list(names)]},
        fields=["name", title_field],
        limit_page_length=10000,
    )

    out = {}
    for r in rows:
        out[r["name"]] = (r.get(title_field) or r["name"])
    return out


def _resolve_table_multiselect():
    """
    Item field: custom_product_categories (Table MultiSelect)
    Detect which link field inside child table points to Product Category/Subcategory.
    """
    item_meta = frappe.get_meta("Item")
    f = item_meta.get_field("custom_product_categories")

    child_dt = f.options if f and f.options else None
    cat_field = None
    subcat_child_field = None

    if child_dt:
        child_meta = frappe.get_meta(child_dt)
        for df in child_meta.fields:
            if df.fieldtype == "Link" and df.options == "Product Category":
                cat_field = df.fieldname
            if df.fieldtype == "Link" and df.options == "Product Subcategory":
                subcat_child_field = df.fieldname

    subcat_item_field = None
    for df in item_meta.fields:
        if df.fieldtype == "Link" and df.options == "Product Subcategory":
            subcat_item_field = df.fieldname
            break

    return child_dt, cat_field, subcat_child_field, subcat_item_field


def get_data(filters):
    if not filters.get("company") or not filters.get("price_list"):
        return []

    conditions = [
        "it.disabled = 0",
        "(it.image IS NOT NULL AND it.image != '')",
        "it.company = %(company)s",
        "ip.price_list = %(price_list)s",
        "(pl.buying = 0 OR pl.selling = 1)",
    ]

    if filters.get("item_group"):
        conditions.append("it.item_group = %(item_group)s")

    if cint(filters.get("in_stock_only")):
        conditions.append("IFNULL(it.available_stock, 0) > 0")

    child_dt, cat_field, subcat_child_field, subcat_item_field = _resolve_table_multiselect()

    join_cat = ""
    cat_codes_select = "''"
    sub_codes_select = "''"

    if child_dt and cat_field:
        join_cat = f"""
            LEFT JOIN `tab{child_dt}` cat
              ON cat.parent = it.name
             AND cat.parenttype = 'Item'
             AND cat.parentfield = 'custom_product_categories'
        """

        cat_codes_select = f"""
            IFNULL(GROUP_CONCAT(DISTINCT cat.`{cat_field}` ORDER BY cat.`{cat_field}` SEPARATOR '{SEP}'), '')
        """

        if subcat_child_field:
            sub_codes_select = f"""
                IFNULL(GROUP_CONCAT(DISTINCT cat.`{subcat_child_field}` ORDER BY cat.`{subcat_child_field}` SEPARATOR '{SEP}'), '')
            """
        elif subcat_item_field:
            sub_codes_select = f"IFNULL(it.`{subcat_item_field}`, '')"
        else:
            sub_codes_select = "''"

        if filters.get("category"):
            conditions.append(f"""
                it.name IN (
                    SELECT cf.parent FROM `tab{child_dt}` cf
                    WHERE cf.parenttype = 'Item'
                      AND cf.parentfield = 'custom_product_categories'
                      AND cf.`{cat_field}` = %(category)s
                )
            """)

        if filters.get("subcategory"):
            if subcat_child_field:
                conditions.append(f"""
                    it.name IN (
                        SELECT sf.parent FROM `tab{child_dt}` sf
                        WHERE sf.parenttype = 'Item'
                          AND sf.parentfield = 'custom_product_categories'
                          AND sf.`{subcat_child_field}` = %(subcategory)s
                    )
                """)
            elif subcat_item_field:
                conditions.append(f"it.`{subcat_item_field}` = %(subcategory)s")
    else:
        join_cat = ""
        cat_codes_select = "''"
        sub_codes_select = f"IFNULL(it.`{subcat_item_field}`, '')" if subcat_item_field else "''"

    where_clause = " WHERE " + " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            it.company as company,
            it.image as image_path,
            it.name as item_code,
            it.item_name as item_name,

            {cat_codes_select} as category_codes,
            {sub_codes_select} as subcategory_codes,

            MAX(ip.price_list_rate) as price_list_rate,
            it.stock_uom as stock_uom,
            MAX(ip.currency) as currency
        FROM `tabItem` it
        INNER JOIN `tabItem Price` ip
            ON ip.item_code = it.name
           AND ip.price_list = %(price_list)s
        LEFT JOIN `tabPrice List` pl
            ON pl.name = ip.price_list
        {join_cat}
        {where_clause}
        GROUP BY it.name
        ORDER BY {_get_order_clause(filters)}
        """,
        filters,
        as_dict=1,
    )

    all_cat = set()
    all_sub = set()
    for r in rows:
        for c in _split_codes(r.get("category_codes")):
            all_cat.add(c)
        for s in _split_codes(r.get("subcategory_codes")):
            all_sub.add(s)

    cat_titles = _get_titles_map("Product Category", all_cat)
    sub_titles = _get_titles_map("Product Subcategory", all_sub)

    out = []
    for r in rows:
        cat_codes = _split_codes(r.get("category_codes"))
        sub_codes = _split_codes(r.get("subcategory_codes"))

        r["category_code"] = ", ".join(cat_codes)
        r["category_name"] = ", ".join([cat_titles.get(x, x) for x in cat_codes])

        r["subcategory_code"] = ", ".join(sub_codes)
        r["subcategory_name"] = ", ".join([sub_titles.get(x, x) for x in sub_codes])

        r["image"] = (
            f'<img src="{r["image_path"]}" style="width:60px;height:60px;object-fit:contain;border-radius:4px;border:1px solid #ddd;">'
            if r.get("image_path")
            else ""
        )

        r.pop("category_codes", None)
        r.pop("subcategory_codes", None)
        r.pop("image_path", None)

        out.append(r)

    return out


# -----------------------------
# MONEY FORMAT (remove "$ " space)
# -----------------------------
def _fmt_money_compact(value, currency=None):
    s = frappe.utils.fmt_money(value, currency=currency)
    if not s:
        return s
    s = s.replace(" ", " ")
    if len(s) > 1 and (not s[0].isalnum()) and s[1] == " ":
        s = s[0] + s[2:]  # "$ 118.72" -> "$118.72"
    return s


# -----------------------------------------------------------------------
# PDF TEMPLATE - WeasyPrint with CSS running elements for header/footer
# and CSS page counters (Page X of Y) rendered inside the running header
# -----------------------------------------------------------------------
PDF_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {
    size: Letter;
    margin: 38mm 8mm 20mm 8mm;

    @top-center {
        content: element(page-header);
        width: 100%;
    }
    @bottom-center {
        content: element(page-footer);
        width: 100%;
    }
}

* { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }

body { font-family: Arial, sans-serif; font-size: 9px; color: #4a4a4a; margin: 0; padding: 0; }

/* RUNNING HEADER */
.page-header {
    position: running(page-header);
    width: 100%;
    background: #fff;
    border: 2px solid #444;
    border-radius: 4px;
    padding: 6px 14px;
    font-family: Arial, sans-serif;
}
.page-header table { width: 100%; border-collapse: collapse; }
.page-header td { vertical-align: middle; padding: 0; }
.hdr-left { width: 155px; }
.hdr-left img { height: 44px; }
.hdr-center { text-align: center; line-height: 1.15; }
.header-title { font-size: 20px; font-weight: 800; letter-spacing: 0.6px; color: #111; }
.header-sub { margin-top: 4px; font-size: 11px; color: #6b6b6b; }
.hdr-right { width: 155px; text-align: right; font-size: 11px; color: #6b6b6b; line-height: 1.4; }
.page-num::before { content: "Page " counter(page) " of " counter(pages); }

.prepared-row td { padding-top: 4px; font-size: 9.5px; color: #444; border-top: 1px solid #e2e2e2; }
.prepared-row .lbl { color: #888; }
.prepared-row .val { font-weight: 700; color: #222; }
.prepared-row .prep-right { text-align: right; }

/* RUNNING FOOTER */
.page-footer {
    position: running(page-footer);
    width: 100%;
    border-top: 1px solid #ccc;
    padding: 6px 16px;
    font-family: Arial, sans-serif;
    font-size: 8.5px;
    font-weight: 500;
    color: #222;
    letter-spacing: 0.2px;
    text-align: center;
}
.footer-note { font-size: 10px; font-weight: 600; color: #555; text-align: center; }

/* GRID (table-based: WeasyPrint paginates multi-row tables far more
   reliably than CSS Grid, which drifts/overflows once content spans
   many pages) */
.grid {
    width: 100%;
    table-layout: fixed;
    border-collapse: collapse;
    margin-top: 4px;
}
.grid col {
    width: 25%;
}
.card {
    width: 25%;
    vertical-align: top;
    padding: 3px;
    page-break-inside: avoid;
    break-inside: avoid;
}

.card-box {
    border: 1.5px solid #c8c8c8;
    border-radius: 8px;
    background: #ffffff;
    padding: 5px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    height: 198px;
}

/* IMAGE - absorbs the card's leftover height so the text block below
   always sits flush with the bottom edge (WeasyPrint honours flex-grow
   but ignores `margin-top: auto` in flex containers) */
.imgbox {
    text-align: center;
    margin-bottom: 5px;
    flex: 1 1 auto;
    min-height: 0;
    overflow: hidden;
}
.imgbox img {
    max-width: 100%;
    max-height: 80px;
    object-fit: contain;
}

/* LABELS */
.lbl-gray {
    color: #5a5a5a;
    font-weight: 600;
}

/* ITEM CODE */
.item-line {
    font-size: 9px;
    font-weight: 400;
    color: #333;
    margin-bottom: 2px;
    line-height: 1.3;
}
.item-line b {
    font-weight: 700;
    color: #111;
}
.item-line .lbl-gray {
    font-weight: 700;
    color: #111;
}
.item-line .il-code {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* PRICE ROW - pinned to the bottom of the card, spread edge to edge */
.price-line {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-top: 4px;
}
.price-line .pl-case,
.price-line .pl-unit {
    font-weight: 700;
    color: #f71c1c;
    white-space: nowrap;
    font-size: 9px;
}
.price-line .unit {
    color: #333;
    font-weight: 600;
    font-size: 7px;
    margin-left: 1px;
}

/* DESC */
.desc-line {
    font-size: 8.5px;
    color: #333333;
    font-weight: 500;
    margin-bottom: 1px;
    line-height: 1.3;
    max-height: 46px;
    overflow: hidden;
}

/* ITEM UPC / CASE PACK / CASES PER PALLET / STOCK rows */
.info-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 0;
    table-layout: fixed;
}
.info-table td {
    padding: 0.5px 0;
    font-size: 8.5px;
    color: #333333;
    font-weight: 500;
    vertical-align: middle;
    white-space: nowrap;
    overflow: hidden;
}
.info-table .col-left  { text-align: left; }
.info-table .col-right { text-align: right; overflow: visible; }
.info-table .col-full  { text-align: left; }
.info-table .lbl-gray  { color: #5a5a5a; font-weight: 600; }

/* BADGE */
.badge {
    display: inline-block;
    padding: 1px 8px;
    border-radius: 10px;
    font-size: 8px;
    font-weight: 700;
    line-height: 1.4;
    white-space: nowrap;
}
.badge.out {
    background: #ffcdd2;
    color: #f71c1c;
    border: 1px solid #ffcdd2;
}
.badge.in {
    background: #2e7d32;
    color: #ffffff;
    border: 1px solid #2e7d32;
}
</style>
</head>

<body>
    <!-- Running header - WeasyPrint places this on every page via @top-center -->
    <div class="page-header">
        <table>
            <tr>
                <td class="hdr-left">{% if company_logo %}<img src="{{ company_logo }}">{% endif %}</td>
                <td class="hdr-center">
                    <div class="header-title">{{ header_title }}</div>
                    <div class="header-sub">{{ header_sub }}</div>
                </td>
                <td class="hdr-right">
                    <div>{{ print_date }}</div>
                    <div class="page-num"></div>
                </td>
            </tr>
            {% if prepared_by or prepared_for %}
            <tr class="prepared-row">
                <td colspan="2"><span class="lbl">Prepared by: </span><span class="val">{{ prepared_by or "" }}</span></td>
                <td class="prep-right"><span class="lbl">Prepared for: </span><span class="val">{{ prepared_for or "" }}</span></td>
            </tr>
            {% endif %}
        </table>
    </div>

    <!-- Running footer - WeasyPrint places this on every page via @bottom-center -->
    <div class="page-footer">
        {% if footer_note %}<div class="footer-note">{{ footer_note }}</div>{% endif %}
    </div>

    <table class="grid">
        <colgroup>
            <col><col><col><col>
        </colgroup>
        {% for row in products|batch(4) %}
            <tr>
                {% for p in row %}
                    <td class="card">
                        <div class="card-box">
                            <div class="imgbox">
                                {% if p.image_url %}<img src="{{ p.image_url }}">{% endif %}
                            </div>
                            <div class="item-line">
                                <span class="il-code"><span class="lbl-gray">Item: </span><b>{{ p.item_code }}</b></span>
                            </div>
                            <div class="desc-line"><span class="lbl-gray">Desc: </span>{{ p.desc }}</div>
                            <table class="info-table">
                                <colgroup>
                                    <col style="width:42%;">
                                    <col style="width:58%;">
                                </colgroup>
                                <tr>
                                    <td class="col-full" colspan="2"><span class="lbl-gray">Item UPC: </span>{{ p.upc or "" }}</td>
                                </tr>
                                <tr>
                                    <td class="col-left"><span class="lbl-gray">Case Pack: </span>{{ p.case_pack or "" }}</td>
                                    <td class="col-right"><span class="lbl-gray">Cases Per Pallet: </span>{{ p.cases_per_pallet or "" }}</td>
                                </tr>
                                <tr>
                                    <td class="col-left"><span class="lbl-gray">Stock: </span></td>
                                    <td class="col-right">
                                        {% if p.in_stock %}
                                            <span class="badge in">{{ p.stock_qty }}</span>
                                        {% else %}
                                            <span class="badge out">Out of Stock</span>
                                        {% endif %}
                                    </td>
                                </tr>
                            </table>
                            {% if not hide_price %}
                            <div class="price-line">
                                <span class="pl-case">{{ p.case_price }}<span class="unit">CA</span></span>
                                {% if p.show_unit_price %}<span class="pl-unit">{{ p.unit_price }}<span class="unit">pcs</span></span>{% endif %}
                            </div>
                            {% endif %}
                        </div>
                    </td>
                {% endfor %}
            </tr>
        {% endfor %}
    </table>

</body>
</html>
"""


def _abs_url(path):
    if not path:
        return ""
    return get_url(path) if path.startswith("/") else path


def _resolve_categories_table():
    item_meta = frappe.get_meta("Item")
    f = item_meta.get_field("custom_product_categories")

    child_dt = f.options if f and f.options else None
    cat_field = None
    subcat_child_field = None

    if child_dt:
        child_meta = frappe.get_meta(child_dt)
        for df in child_meta.fields:
            if df.fieldtype == "Link" and df.options == "Product Category":
                cat_field = df.fieldname
            if df.fieldtype == "Link" and df.options == "Product Subcategory":
                subcat_child_field = df.fieldname

    subcat_item_field = None
    for df in item_meta.fields:
        if df.fieldtype == "Link" and df.options == "Product Subcategory":
            subcat_item_field = df.fieldname
            break

    upc_field = None
    for df in item_meta.fields:
        if (df.label or "").strip().lower() == "item upc":
            upc_field = df.fieldname
            break
    if not upc_field:
        for fn in ("item_upc", "custom_item_upc"):
            if item_meta.get_field(fn):
                upc_field = fn
                break

    return child_dt, cat_field, subcat_child_field, subcat_item_field, upc_field


def _get_company_logo(company):
    if not company:
        return ""
    logo = frappe.get_value("Company", company, "company_logo")
    if not logo:
        return ""

    import base64, mimetypes
    site_path = frappe.get_site_path()

    if logo.startswith("/files/"):
        file_path = os.path.join(site_path, "public", logo.lstrip("/"))
    elif logo.startswith("/private/"):
        file_path = os.path.join(site_path, logo.lstrip("/"))
    else:
        return _abs_url(logo)

    if not os.path.exists(file_path):
        return _abs_url(logo)

    mime = mimetypes.guess_type(file_path)[0] or "image/png"
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{b64}"


def _get_products_for_pdf(filters):
    conditions = [
        "it.disabled = 0",
        "(it.image IS NOT NULL AND it.image != '')",
        "ip.price_list = %(price_list)s",
    ]
    if filters.get("company"):
        conditions.append("it.company = %(company)s")
    if filters.get("item_group"):
        conditions.append("it.item_group = %(item_group)s")
    if cint(filters.get("in_stock_only")):
        conditions.append("IFNULL(it.available_stock, 0) > 0")

    child_dt, cat_field, subcat_child_field, subcat_item_field, upc_field = _resolve_categories_table()

    join_cat = ""
    cat_codes_select = "''"
    sub_codes_select = "''"
    if child_dt and cat_field:
        join_cat = f"""
            LEFT JOIN `tab{child_dt}` cat
              ON cat.parent = it.name
             AND cat.parenttype = 'Item'
             AND cat.parentfield = 'custom_product_categories'
        """

        cat_codes_select = f"""
            IFNULL(GROUP_CONCAT(DISTINCT cat.`{cat_field}` ORDER BY cat.`{cat_field}` SEPARATOR '{SEP}'), '')
        """

        if subcat_child_field:
            sub_codes_select = f"""
                IFNULL(GROUP_CONCAT(DISTINCT cat.`{subcat_child_field}` ORDER BY cat.`{subcat_child_field}` SEPARATOR '{SEP}'), '')
            """
        elif subcat_item_field:
            sub_codes_select = f"IFNULL(it.`{subcat_item_field}`, '')"

        if filters.get("category"):
            conditions.append(f"""
                it.name IN (
                    SELECT cf.parent FROM `tab{child_dt}` cf
                    WHERE cf.parenttype = 'Item'
                      AND cf.parentfield = 'custom_product_categories'
                      AND cf.`{cat_field}` = %(category)s
                )
            """)

        if filters.get("subcategory"):
            if subcat_child_field:
                conditions.append(f"""
                    it.name IN (
                        SELECT sf.parent FROM `tab{child_dt}` sf
                        WHERE sf.parenttype = 'Item'
                          AND sf.parentfield = 'custom_product_categories'
                          AND sf.`{subcat_child_field}` = %(subcategory)s
                    )
                """)
            elif subcat_item_field:
                conditions.append(f"it.`{subcat_item_field}` = %(subcategory)s")

    where_clause = " WHERE " + " AND ".join(conditions)
    upc_select = f"it.`{upc_field}` as upc," if upc_field else "NULL as upc,"

    rows = frappe.db.sql(f"""
        SELECT
            it.name as item_code,
            it.item_name as item_name,
            it.image as image_path,
            {upc_select}
            ip.price_list_rate,
            ip.currency,
            IFNULL(it.custom_case_pack, 0) as case_pack,
            IFNULL(it.custom_case_per_pallet, 0) as cases_per_pallet,
            IFNULL(it.available_stock, 0) as available_stock,
            {cat_codes_select} as category_codes,
            {sub_codes_select} as subcategory_codes
        FROM `tabItem` it
        INNER JOIN `tabItem Price` ip
            ON ip.item_code = it.name
           AND ip.price_list = %(price_list)s
        {join_cat}
        {where_clause}
        GROUP BY it.name
        ORDER BY {_get_order_clause(filters)}
    """, filters, as_dict=1)

    all_cat = set()
    all_sub = set()
    for r in rows:
        for c in _split_codes(r.get("category_codes")):
            all_cat.add(c)
        for s in _split_codes(r.get("subcategory_codes")):
            all_sub.add(s)
    cat_titles = _get_titles_map("Product Category", all_cat)
    sub_titles = _get_titles_map("Product Subcategory", all_sub)

    products = []
    for r in rows:
        price = r.price_list_rate or 0
        currency = r.currency or None

        case_pack = r.get("case_pack") or 0
        try:
            cp_num = float(case_pack) if case_pack else 0.0
        except (ValueError, TypeError):
            cp_num = 0.0

        cases_per_pallet = r.get("cases_per_pallet") or 0
        try:
            cpp_num = float(cases_per_pallet) if cases_per_pallet else 0.0
        except (ValueError, TypeError):
            cpp_num = 0.0

        unit_price_val = (price / cp_num) if cp_num > 0 else None
        show_unit_price = (cp_num >= 1 and unit_price_val is not None)

        stock_qty = flt(r.get("available_stock"))
        in_stock = stock_qty > 0

        cat_codes = _split_codes(r.get("category_codes"))
        sub_codes = _split_codes(r.get("subcategory_codes"))
        category_name = ", ".join([cat_titles.get(x, x) for x in cat_codes])
        subcategory_name = ", ".join([sub_titles.get(x, x) for x in sub_codes])

        products.append({
            "item_code": r.item_code,
            "desc": r.item_name or "",
            "image_url": _abs_url(r.image_path),
            "upc": r.upc,
            "case_pack": int(cp_num) if cp_num and float(cp_num).is_integer() else (cp_num if cp_num else ""),
            "cases_per_pallet": int(cpp_num) if cpp_num and float(cpp_num).is_integer() else (cpp_num if cpp_num else ""),
            "piece_uom": "PCS",

            "case_price": _fmt_money_compact(price, currency=currency),
            "unit_price": _fmt_money_compact(unit_price_val, currency=currency) if unit_price_val is not None else "",
            "show_unit_price": show_unit_price,

            "stock_qty": int(stock_qty) if float(stock_qty).is_integer() else stock_qty,
            "in_stock": in_stock,

            "category_name": category_name,
            "subcategory_name": subcategory_name,
        })

    return products


@frappe.whitelist()
def download_catalog_modern_grid_pdf(filters=None):
    if isinstance(filters, str):
        filters = frappe.parse_json(filters)
    filters = filters or {}

    products = _get_products_for_pdf(filters)
    total_products = len(products)

    hide_price = filters.get("hide_price", 0)
    header_sub = (filters.get("header_sub") or "").strip() or f"Total Products: {total_products}"

    prepared_by = (filters.get("prepared_by") or "").strip() or get_fullname(frappe.session.user)

    prepared_for_customer = (filters.get("prepared_for") or "").strip()
    prepared_for = prepared_for_customer
    if prepared_for_customer:
        customer_name = frappe.db.get_value("Customer", prepared_for_customer, "customer_name")
        if customer_name:
            prepared_for = customer_name

    context = {
        "products": products,
        "total_products": total_products,
        "print_date": now_datetime().strftime("%-m/%-d/%Y %I:%M %p"),
        "company_logo": _get_company_logo(filters.get("company")),
        "hide_price": int(hide_price),
        "header_title": (filters.get("header_title") or "PRODUCT CATALOG"),
        "header_sub": header_sub,
        "footer_note": (filters.get("footer_note") or ""),
        "prepared_by": prepared_by,
        "prepared_for": prepared_for,
    }

    html = frappe.render_template(PDF_TEMPLATE, context)

    from weasyprint import HTML as WeasyHTML
    pdf = WeasyHTML(string=html, base_url=frappe.get_site_path()).write_pdf()

    filename = f"Product Catalog - {filters.get('company') or ''}.pdf".replace("/", "-")
    frappe.local.response["filename"] = filename
    frappe.local.response["filecontent"] = pdf
    frappe.local.response["type"] = "download"


@frappe.whitelist()
def get_product_types(doctype, txt, searchfield, start, page_len, filters):
    """Return Product Type (Item Group) values associated with report-eligible Item records."""
    filters = filters or {}

    conds = [
        "ig.name LIKE %(txt)s",
        "it.disabled = 0",
        "(it.image IS NOT NULL AND it.image != '')",
    ]
    params = {
        "txt": f"%{txt}%",
        "start": int(start),
        "page_len": int(page_len),
    }

    if filters.get("company"):
        conds.append("it.company = %(company)s")
        params["company"] = filters["company"]

    if filters.get("price_list"):
        conds.append("""
            EXISTS (
                SELECT 1
                FROM `tabItem Price` ip
                LEFT JOIN `tabPrice List` pl ON pl.name = ip.price_list
                WHERE ip.item_code = it.name
                  AND ip.price_list = %(price_list)s
                  AND (pl.buying = 0 OR pl.selling = 1)
            )
        """)
        params["price_list"] = filters["price_list"]

    where = " AND ".join(conds)
    return frappe.db.sql(
        f"""SELECT DISTINCT ig.name, ig.name
            FROM `tabItem Group` ig
            INNER JOIN `tabItem` it ON it.item_group = ig.name
            WHERE {where}
            ORDER BY ig.name
            LIMIT %(start)s, %(page_len)s""",
        params,
    )


@frappe.whitelist()
def get_subcategories(doctype, txt, searchfield, start, page_len, filters):
    """Return Product Subcategory names, optionally filtered by company and category."""
    conds = ["sc.name LIKE %(txt)s"]
    params = {"txt": f"%{txt}%", "start": int(start), "page_len": int(page_len)}

    if filters.get("company"):
        conds.append("sc.company = %(company)s")
        params["company"] = filters["company"]

    if filters.get("category"):
        conds.append("""
            sc.name IN (
                SELECT sub.product_subcategory
                FROM `tabSubCategories` sub
                WHERE sub.parenttype = 'Product Category'
                  AND sub.parent = %(category)s
            )
        """)
        params["category"] = filters["category"]

    where = " AND ".join(conds)
    return frappe.db.sql(
        f"""SELECT sc.name, sc.title
           FROM `tabProduct Subcategory` sc
           WHERE {where}
           ORDER BY sc.title
           LIMIT %(start)s, %(page_len)s""",
        params,
    )
