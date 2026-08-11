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
        {"label": _("UPC"), "fieldname": "upc", "fieldtype": "Data", "width": 120},

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


# Promotional tags stored as Product Categories - these are merchandising flags,
# not real product categories, so they are hidden from the Category column.
PROMO_CATEGORY_TITLES = {"new in store", "back in store"}


def _drop_promo_categories(codes, titles_map):
    """Return only real product categories, dropping promo tags like 'BACK IN STORE'."""
    kept = []
    for code in codes:
        title = titles_map.get(code, code)
        if (title or "").strip().lower() in PROMO_CATEGORY_TITLES:
            continue
        kept.append(code)
    return kept


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


def _resolve_categories_table():
    """
    Item field: custom_product_categories (Table MultiSelect)
    Detect which link field inside child table points to Product Category/Subcategory,
    plus the Item UPC field to use for the printed barcode number.
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

    upc_field = "custom_upc" if item_meta.get_field("custom_upc") else None

    return child_dt, cat_field, subcat_child_field, subcat_item_field, upc_field


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
    upc_select = f"it.`{upc_field}` as upc," if upc_field else "NULL as upc,"

    rows = frappe.db.sql(
        f"""
        SELECT
            it.company as company,
            it.image as image_path,
            it.name as item_code,
            it.item_name as item_name,
            {upc_select}

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
        cat_codes = _drop_promo_categories(_split_codes(r.get("category_codes")), cat_titles)
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
    s = s.replace(" ", " ")
    if len(s) > 1 and (not s[0].isalnum()) and s[1] == " ":
        s = s[0] + s[2:]  # "$ 118.72" -> "$118.72"
    return s


# -----------------------------------------------------------------------
# PDF TEMPLATE - "Old Bridge" style: black header banner with logo + company
# address, a "Prepared by / Date & Time / Prepared for" strip, a 3-up product
# grid (name, code, category/dimension/stock-price mini tables + image, and a
# decorative barcode across the bottom). Uses WeasyPrint running elements for
# header/footer and page counters.
# -----------------------------------------------------------------------
PDF_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {
    size: Letter;
    margin: 35mm 8mm 12mm 8mm;

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

body { font-family: Arial, sans-serif; font-size: 9px; color: #333; margin: 0; padding: 0; }

/* RUNNING HEADER */
.page-header {
    position: running(page-header);
    width: 100%;
    font-family: Arial, sans-serif;
}
.hdr-bar {
    background: #000;
    padding: 14px 18px;
    width: 100%;
    margin-bottom: 6px;
}
.hdr-bar table { width: 100%; border-collapse: collapse; }
.hdr-bar td { vertical-align: middle; padding: 0; }
.hdr-left { width: 190px; }
.hdr-logo {
    display: inline-block;
    color: #fff;
    font-weight: 800;
    font-size: 15px;
    letter-spacing: 0.5px;
}
.hdr-right { text-align: right; font-size: 10px; color: #fff; font-weight: 600; letter-spacing: 0.2px; }
.page-num::before { content: "Page " counter(page) " of " counter(pages); }

.meta-strip {
    background: #f1f1f1;
    border: 1px solid #ddd;
    padding: 6px 16px;
    width: 100%;
}
.meta-strip table { width: 100%; border-collapse: collapse; }
.meta-strip td { vertical-align: top; padding: 0; font-size: 8px; }
.meta-strip .m-left { text-align: left; }
.meta-strip .m-center { text-align: center; }
.meta-strip .m-right { text-align: right; }
.meta-strip .lbl { color: #8a8a8a; }
.meta-strip .val { display: block; margin-top: 2px; font-size: 12px; font-weight: 700; color: #1a1a1a; }

/* RUNNING FOOTER */
.page-footer {
    position: running(page-footer);
    width: 100%;
    border-top: 1px solid #ccc;
    padding: 5px 16px;
    font-family: Arial, sans-serif;
    font-size: 8.5px;
    font-weight: 500;
    color: #666;
    text-align: center;
}

/* GRID - 3 cards per row.
   Built as a real table rather than floats: WeasyPrint does not reliably honour
   break-inside:avoid on floated boxes, which let a card's barcode get orphaned
   onto the next page. Table rows paginate atomically, so a card always stays
   whole, and fixed columns mean a tall card can never leave a hole in the row. */
.grid {
    width: 100%;
    margin-top: 8px;
    border-collapse: collapse;
    table-layout: fixed;
}
.grid-row {
    page-break-inside: avoid;
    break-inside: avoid;
}
.card {
    width: 33.333%;
    vertical-align: top;
    padding: 0 5px 5px 5px;
    page-break-inside: avoid;
    break-inside: avoid;
}

.card-box {
    overflow: hidden;
    page-break-inside: avoid;
    break-inside: avoid;
}

.name-line {
    font-size: 7.5px;
    font-weight: 400;
    color: #1a1a1a;
    line-height: 1.2;
    max-height: 18px;
    overflow: hidden;
    margin-bottom: 1px;
}
.code-line {
    font-size: 11px;
    font-weight: 800;
    color: #111;
    margin-bottom: 2px;
}

/* BODY ROW: mini tables (left) + image (right) */
.body-row {
    display: table;
    width: 100%;
    table-layout: fixed;
    page-break-inside: avoid;
    break-inside: avoid;
}
.body-cell {
    display: table-cell;
    vertical-align: top;
}
.tables-cell { width: 60%; padding-right: 5px; }
.image-cell { width: 40%; text-align: center; vertical-align: top; }
/* Height matches the rendered height of .detail-box (measured 82.4px) so the
   photo lines up exactly with the details+barcode box beside it. */
.image-cell img {
    width: 100%;
    height: 82px;
    object-fit: contain;
}

/* One unified border wrapping the attribute tables AND the barcode. The inner
   tables are borderless apart from the row separators, so the box reads as a
   single framed block. */
.detail-box {
    border: 1px solid #ccc;
    overflow: hidden;
}
.mini-table {
    width: 100%;
    border-collapse: collapse;
    border: none;
    margin: 0;
}
.mini-table th, .mini-table td {
    border: none;
    border-bottom: 1px solid #ccc;
    padding: 1px 2px;
    font-size: 6.5px;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
}
.mini-table th {
    background: #eeeeee;
    color: #555;
    font-weight: 700;
}
.mini-table td { color: #222; font-weight: 600; }
.mini-table td.oos { color: #d32f2f; }

/* DECORATIVE BARCODE - last band inside .detail-box; the preceding table's
   bottom border separates it, and the box's own border closes it off. */
.barcode-wrap {
    width: 100%;
    padding: 2px 4px;
    overflow: hidden;
}
.barcode-bars {
    display: block;
    height: 15px;
    width: 100%;
    background-image: repeating-linear-gradient(
        90deg,
        #1a1a1a 0px, #1a1a1a 1.4px,
        transparent 1.4px, transparent 2.4px,
        #1a1a1a 2.4px, #1a1a1a 3.1px,
        transparent 3.1px, transparent 4.6px,
        #1a1a1a 4.6px, #1a1a1a 5.1px,
        transparent 5.1px, transparent 6.8px,
        #1a1a1a 6.8px, #1a1a1a 8.0px,
        transparent 8.0px, transparent 9.0px
    );
    background-size: 100% 100%;
}
</style>
</head>

<body>
    <!-- Running header - WeasyPrint places this on every page via @top-center -->
    <div class="page-header">
        <div class="hdr-bar">
            <table>
                <tr>
                    <td class="hdr-left">
                        {% if company_logo %}
                            <img src="{{ company_logo }}" style="height:52px;">
                        {% else %}
                            <span class="hdr-logo">{{ company_name or "" }}</span>
                        {% endif %}
                    </td>
                    <td class="hdr-right">
                        <div>{{ header_address }}</div>
                    </td>
                </tr>
            </table>
        </div>
        <div class="meta-strip">
            <table>
                <tr>
                    <td class="m-left">
                        <span class="lbl">Prepared by:</span>
                        <span class="val">{{ prepared_by or "" }}</span>
                    </td>
                    <td class="m-center">
                        <span class="lbl">Date &amp; Time:</span>
                        <span class="val">{{ print_date }}</span>
                    </td>
                    <td class="m-right">
                        <span class="lbl">Prepared for:</span>
                        <span class="val">{{ prepared_for or "" }}</span>
                    </td>
                </tr>
            </table>
        </div>
    </div>

    <!-- Running footer -->
    <div class="page-footer">
        {% if footer_note %}{{ footer_note }}{% else %}<span class="page-num"></span>{% endif %}
    </div>

    <table class="grid">
        {% for row in products|batch(3) %}
        <tr class="grid-row">
        {% for p in row %}
            <td class="card">
                <div class="card-box">
                    <div class="code-line">{{ p.item_code }}</div>
                    <div class="name-line">{{ p.item_name }}</div>
                    <div class="body-row">
                        <div class="body-cell tables-cell">
                            <div class="detail-box">
                                <table class="mini-table">
                                    <tr><th>Category</th><th>SubCategory</th></tr>
                                    <tr><td>{{ p.category_name or "" }}</td><td>{{ p.subcategory_name or "" }}</td></tr>
                                </table>
                                <table class="mini-table">
                                    <tr><th>Length</th><th>Width</th><th>Height</th><th>Weight</th></tr>
                                    <tr><td>{{ p.length }}</td><td>{{ p.width }}</td><td>{{ p.height }}</td><td>{{ p.weight }}</td></tr>
                                </table>
                                <table class="mini-table">
                                    <tr><th>Stock</th><th>Cases</th><th>CA Price</th><th>PCS Price</th></tr>
                                    <tr>
                                        <td class="{% if not p.in_stock %}oos{% endif %}">{{ p.stock_qty }}</td>
                                        <td>{{ p.case_pack }}</td>
                                        <td>{% if not hide_price %}{{ p.case_price }}{% endif %}</td>
                                        <td>{% if not hide_price and p.show_unit_price %}{{ p.unit_price }}{% endif %}</td>
                                    </tr>
                                </table>
                                <div class="barcode-wrap">
                                    <div class="barcode-bars"></div>
                                </div>
                            </div>
                        </div>
                        <div class="body-cell image-cell">
                            {% if p.image_url %}<img src="{{ p.image_url }}">{% endif %}
                        </div>
                    </div>
                </div>
            </td>
        {% endfor %}
        {# keep the last row's columns the same width as full rows #}
        {% for _ in range(3 - row|length) %}<td class="card"></td>{% endfor %}
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


HEADER_ADDRESS = "Cotton Valley LLC 326 APPLEGARTH ROAD MONROE, NJ 08831"


def _fmt_dim(value):
    """Round dimensions/weight to at most 2 decimals, keeping one decimal minimum
    (3.740016 -> '3.74', 10.5 -> '10.5', 0 -> '0.0')."""
    s = f"{flt(value):.2f}".rstrip("0")
    return f"{s}0" if s.endswith(".") else s


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
            IFNULL(it.available_stock, 0) as available_stock,
            it.custom_item_length_inch as item_length,
            it.custom_item_width_inch as item_width,
            it.custom_item_height_inch as item_height,
            it.custom_item_weight_lbs as item_weight,
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

        unit_price_val = (price / cp_num) if cp_num > 0 else None
        show_unit_price = (cp_num >= 1 and unit_price_val is not None)

        stock_qty = flt(r.get("available_stock"))
        in_stock = stock_qty > 0

        cat_codes = _drop_promo_categories(_split_codes(r.get("category_codes")), cat_titles)
        sub_codes = _split_codes(r.get("subcategory_codes"))
        category_name = ", ".join([cat_titles.get(x, x) for x in cat_codes])
        subcategory_name = ", ".join([sub_titles.get(x, x) for x in sub_codes])

        products.append({
            "item_code": r.item_code,
            "item_name": r.item_name or "",
            "image_url": _abs_url(r.image_path),
            "upc": r.upc,
            "case_pack": int(cp_num) if cp_num and float(cp_num).is_integer() else (cp_num if cp_num else ""),

            "case_price": _fmt_money_compact(price, currency=currency),
            "unit_price": _fmt_money_compact(unit_price_val, currency=currency) if unit_price_val is not None else "",
            "show_unit_price": show_unit_price,

            "stock_qty": int(stock_qty) if float(stock_qty).is_integer() else stock_qty,
            "in_stock": in_stock,

            "category_name": category_name,
            "subcategory_name": subcategory_name,

            "length": _fmt_dim(r.get("item_length")),
            "width": _fmt_dim(r.get("item_width")),
            "height": _fmt_dim(r.get("item_height")),
            "weight": _fmt_dim(r.get("item_weight")),
        })

    return products


@frappe.whitelist()
def download_catalog_old_bridge_pdf(filters=None):
    if isinstance(filters, str):
        filters = frappe.parse_json(filters)
    filters = filters or {}

    products = _get_products_for_pdf(filters)
    total_products = len(products)

    hide_price = filters.get("hide_price", 0)

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
        "company_name": filters.get("company") or "",
        "header_address": HEADER_ADDRESS,
        "hide_price": int(hide_price),
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
