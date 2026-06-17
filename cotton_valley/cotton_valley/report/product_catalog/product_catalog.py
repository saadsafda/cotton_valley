import os

import frappe
from frappe import _
from frappe.utils import get_url, formatdate, today, flt

SEP = "||"
PCS_CANDIDATES = frozenset({
    "PCS", "PC", "NOS", "EACH", "EA", "PIECE", "PIECES",
    "UNIT", "UNITS", "NUMBER", "NUMBERS",
})


def _normalize_uom(uom):
    """Strip dots, trailing 's', extra whitespace; uppercase."""
    return (uom or "").strip().upper().rstrip(".")


# -----------------------------
# ✅ SORT MAP (safe whitelist)
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
# ✅ QUERY REPORT REQUIRED API
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

    child_dt, cat_field, subcat_child_field, subcat_item_field = _resolve_table_multiselect()

    join_cat = ""
    cat_codes_select = "''"
    sub_codes_select = "''"

    if child_dt and cat_field:
        # Always LEFT JOIN for data retrieval
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

        # Independent category filter
        if filters.get("category"):
            conditions.append(f"""
                it.name IN (
                    SELECT cf.parent FROM `tab{child_dt}` cf
                    WHERE cf.parenttype = 'Item'
                      AND cf.parentfield = 'custom_product_categories'
                      AND cf.`{cat_field}` = %(category)s
                )
            """)

        # Independent subcategory filter
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
# ✅ MONEY FORMAT (remove "$ " space)
# -----------------------------
def _fmt_money_compact(value, currency=None):
    s = frappe.utils.fmt_money(value, currency=currency)
    if not s:
        return s
    # remove NBSP and normal spaces after currency symbol
    s = s.replace("\u00a0", " ")
    if len(s) > 1 and (not s[0].isalnum()) and s[1] == " ":
        s = s[0] + s[2:]  # "$ 118.72" -> "$118.72"
    return s


# -----------------------------------------------------------------------
# ✅ PDF TEMPLATE – WeasyPrint with CSS running elements for header/footer
# -----------------------------------------------------------------------
PDF_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {
    size: Letter;
    margin: 34mm 8mm 20mm 8mm;

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
}
.footer-note { font-size: 10px; font-weight: 600; color: #555; margin-top: 2px; text-align: center; }

/* GRID */
.grid {
    margin-top: 6px;
    margin-left: -5px;
    margin-right: -5px;
}
.grid::after {
    content: '';
    display: table;
    clear: both;
}
.card {
    float: left;
    width: 25%;
    padding: 0 5px 10px 5px;
    page-break-inside: avoid;
    break-inside: avoid;
}

.card-box {
    border: 1.5px solid #c8c8c8;
    border-radius: 10px;
    background: #ffffff;
    padding: 8px;
    overflow: hidden;
    height: 245px;
    display: flex;
    flex-direction: column;
}

/* IMAGE */
.imgbox {
    text-align: center;
    margin-bottom: 6px;
    height: 100px;
    overflow: hidden;
}
.imgbox img {
    max-width: 100%;
    max-height: 96px;
    object-fit: contain;
}

/* LABELS */
.lbl-gray {
    color: #7f7f7f;
    font-weight: 400;
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

/* DESC */
.desc-line {
    font-size: 8.5px;
    color: #333;
    margin-bottom: 0;
    line-height: 1.35;
    height: 34px;
    overflow: hidden;
}

/* Reserve consistent vertical space for description + category text */
.text-block {
    min-height: 58px;
    margin-bottom: 3px;
}

/* CATEGORY */
.cat-line {
    font-size: 8.5px;
    margin-top: 3px;
    min-height: 22px;
    max-height: 22px;
    line-height: 1.25;
    overflow: hidden;
    white-space: normal;
    word-break: break-word;
}
.cat-line .lbl-gray { color: #888; }
.cat-line .cat-val {
    color: #222;
    font-weight: 400;
}

/* UPC / CASE PACK / STOCK rows */
.info-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 3px;
    table-layout: fixed;
}
.info-table td {
    padding: 1px 0;
    font-size: 8.5px;
    color: #333;
    vertical-align: middle;
    white-space: nowrap;
    overflow: hidden;
}
.info-table .col-left  { width: 50%; }
.info-table .col-right { width: 50%; text-align: right; overflow: visible; white-space: normal; }
.info-table .lbl-gray  { color: #888; }

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
    background: #fbeaea;
    color: #c0392b;
    border: 1px solid #f1aeb5;
}
.badge.in {
    background: #e2f5e9;
    color: #1e7e34;
    border: 1px solid #a3cfbb;
}

/* PRICE BAR */
.price-bar {
    background: #b8d4e8;
    border-radius: 4px;
    padding: 4px 8px 4px 6px;
    margin-top: auto;
}
.price-bar table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
}
.price-bar td {
    padding: 0;
    width: 50%;
    max-width: 50%;
    font-size: 8px;
    font-weight: 700;
    color: #1a2a3a;
    white-space: nowrap;
    overflow: hidden;
    vertical-align: middle;
}
.price-bar td:first-child {
    padding-right: 3px;
}
.price-bar .lbl {
    font-size: 7px;
    font-weight: 600;
    color: #2c4a6a;
}
.price-bar .right {
    padding-left: 3px;
    padding-right: 2px;
    text-align: right;
}
.price-bar.single td {
    width: 100%;
    max-width: 100%;
    padding-right: 0;
}
</style>
</head>

<body>
    <!-- Running header – WeasyPrint places this on every page via @top-left -->
    <div class="page-header">
        <table>
            <tr>
                <td class="hdr-left">{% if company_logo %}<img src="{{ company_logo }}">{% endif %}</td>
                <td class="hdr-center">
                    <div class="header-title">{{ header_title }}</div>
                    {% if header_sub %}<div class="header-sub">{{ header_sub }}</div>{% endif %}
                    {% if header_note %}<div style="margin-top:4px;font-size:11px;color:#333;font-weight:600;">{{ header_note }}</div>{% endif %}
                </td>
                <td class="hdr-right">{{ print_date }}</td>
            </tr>
        </table>
    </div>

    <!-- Running footer – WeasyPrint places this on every page via @bottom-left -->
    <div class="page-footer">
        Total Products: {{ total_products }}
        {% if footer_note %}<div class="footer-note">{{ footer_note }}</div>{% endif %}
    </div>

    <div class="grid">
        {% for p in products %}
            <div class="card">
                <div class="card-box">
                    <div class="imgbox">
                        {% if p.image_url %}<img src="{{ p.image_url }}">{% endif %}
                    </div>
                    <div class="item-line"><span class="lbl-gray">Item: </span><b>{{ p.item_code }}</b></div>
                    <div class="text-block">
                        <div class="desc-line"><span class="lbl-gray">Desc: </span>{{ p.desc }}</div>
                        <div class="cat-line"><span class="lbl-gray">Category: </span><span class="cat-val">{{ p.category_name or '' }}</span></div>
                    </div>
                    <table class="info-table">
                        <tr>
                            <td class="col-left"><span class="lbl-gray">UPC: </span>{{ p.upc or "" }}</td>
                            <td class="col-right"><span class="lbl-gray">Case Pack : </span>{{ p.case_pack or "" }}</td>
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
                    <div class="price-bar{% if not p.show_unit_price %} single{% endif %}">
                        <table>
                            <tr>
                                <td><span class="lbl">CA.P.:</span>{{ p.case_price }}</td>
                                {% if p.show_unit_price %}<td class="right"><span class="lbl">EA.P.:</span>{{ p.unit_price }}</td>{% endif %}
                            </tr>
                        </table>
                    </div>
                    {% endif %}
                </div>
            </div>
        {% endfor %}
    </div>

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


def _get_case_pack_map(item_codes):
    if not item_codes:
        return {}, {}

    rows = frappe.db.sql("""
        SELECT parent as item_code, uom, conversion_factor
        FROM `tabUOM Conversion Detail`
        WHERE parenttype='Item'
          AND parent IN %(items)s
    """, {"items": tuple(item_codes)}, as_dict=1)

    best = {}
    best_uom = {}
    fallback = {}
    fallback_uom = {}

    for r in rows:
        uom = (r.uom or "").strip()
        uom_norm = _normalize_uom(uom)
        cf = float(r.conversion_factor or 0)

        if cf <= 0:
            continue

        # ✅ match piece-type UOMs (case-insensitive, dots stripped)
        if uom_norm in PCS_CANDIDATES:
            if (r.item_code not in best) or (cf > float(best.get(r.item_code) or 0)):
                best[r.item_code] = cf
                best_uom[r.item_code] = uom
        elif cf > 1:
            # ✅ fallback: any UOM with cf > 1 (likely pieces-per-case)
            if (r.item_code not in fallback) or (cf > float(fallback.get(r.item_code) or 0)):
                fallback[r.item_code] = cf
                fallback_uom[r.item_code] = uom

    # merge fallback for items not found via PCS candidates
    for ic in fallback:
        if ic not in best:
            best[ic] = fallback[ic]
            best_uom[ic] = fallback_uom[ic]

    return best, best_uom



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

    child_dt, cat_field, subcat_child_field, subcat_item_field, upc_field = _resolve_categories_table()

    join_cat = ""
    cat_codes_select = "''"
    sub_codes_select = "''"
    if child_dt and cat_field:
        # Always LEFT JOIN for data retrieval
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

        # Independent category filter
        if filters.get("category"):
            conditions.append(f"""
                it.name IN (
                    SELECT cf.parent FROM `tab{child_dt}` cf
                    WHERE cf.parenttype = 'Item'
                      AND cf.parentfield = 'custom_product_categories'
                      AND cf.`{cat_field}` = %(category)s
                )
            """)

        # Independent subcategory filter
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

    # Resolve category / subcategory titles
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

        # Case pack from custom_case_pack field on Item
        case_pack = r.get("case_pack") or 0
        try:
            cp_num = float(case_pack) if case_pack else 0.0
        except (ValueError, TypeError):
            cp_num = 0.0

        unit_price_val = (price / cp_num) if cp_num > 0 else None

        # Show unit price when CA >= 1
        show_unit_price = (cp_num >= 1 and unit_price_val is not None)

        stock_qty = flt(r.get("available_stock"))
        in_stock = stock_qty > 0

        # Resolve category / subcategory names
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
            "piece_uom": "PCS",

            # remove "$ " space
            "case_price": _fmt_money_compact(price, currency=currency),

            # unit price string only if needed
            "unit_price": _fmt_money_compact(unit_price_val, currency=currency) if unit_price_val is not None else "",
            "show_unit_price": show_unit_price,

            "stock_qty": int(stock_qty) if float(stock_qty).is_integer() else stock_qty,
            "in_stock": in_stock,

            "category_name": category_name,
            "subcategory_name": subcategory_name,
        })

    return products


@frappe.whitelist()
def download_product_catalog_pdf(filters=None):
    if isinstance(filters, str):
        filters = frappe.parse_json(filters)
    filters = filters or {}

    products = _get_products_for_pdf(filters)

    hide_price = filters.get("hide_price", 0)
    header_note = (filters.get("header_note") or "").strip()

    context = {
        "products": products,
        "total_products": len(products),
        "print_date": formatdate(today()),
        "company_logo": _get_company_logo(filters.get("company")),
        "hide_price": int(hide_price),
        "header_note": header_note,
        # editable header fields (can be passed in `filters`)
        "header_title": (filters.get("header_title") or "PRODUCT CATALOG"),
        "header_sub": (filters.get("header_sub") or ""),
        "footer_note": (filters.get("footer_note") or ""),
    }

    html = frappe.render_template(PDF_TEMPLATE, context)

    # Use WeasyPrint – supports CSS running elements for header/footer on every page
    from weasyprint import HTML as WeasyHTML
    pdf = WeasyHTML(string=html, base_url=frappe.get_site_path()).write_pdf()

    # Stream PDF directly as download (avoids 10MB save_file limit)
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