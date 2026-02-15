import os
import tempfile
from urllib.request import pathname2url

import frappe
import pdfkit
from frappe import _
from frappe.utils import get_url, formatdate, today
from frappe.utils.file_manager import save_file

SEP = "||"
PCS_CANDIDATES = frozenset({
    "PCS", "PC", "NOS", "EACH", "EA", "PIECE", "PIECES",
    "UNIT", "UNITS", "NUMBER", "NUMBERS",
})


def _normalize_uom(uom):
    """Strip dots, trailing 's', extra whitespace; uppercase."""
    return (uom or "").strip().upper().rstrip(".")


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

        if filters.get("category"):
            conditions.append(f"cat.`{cat_field}` = %(category)s")

        if filters.get("subcategory"):
            if subcat_child_field:
                sub_codes_select = f"""
                    IFNULL(GROUP_CONCAT(DISTINCT cat.`{subcat_child_field}` ORDER BY cat.`{subcat_child_field}` SEPARATOR '{SEP}'), '')
                """
                conditions.append(f"cat.`{subcat_child_field}` = %(subcategory)s")
            elif subcat_item_field:
                sub_codes_select = f"IFNULL(it.`{subcat_item_field}`, '')"
                conditions.append(f"it.`{subcat_item_field}` = %(subcategory)s")
            else:
                sub_codes_select = "''"
        else:
            if subcat_child_field:
                sub_codes_select = f"""
                    IFNULL(GROUP_CONCAT(DISTINCT cat.`{subcat_child_field}` ORDER BY cat.`{subcat_child_field}` SEPARATOR '{SEP}'), '')
                """
            elif subcat_item_field:
                sub_codes_select = f"IFNULL(it.`{subcat_item_field}`, '')"
            else:
                sub_codes_select = "''"
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
        ORDER BY it.item_name
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


# -----------------------------
# ✅ PDF TEMPLATE (bold removed, colors like screenshot, price correct)
# -----------------------------
PDF_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
@page { size: Letter; margin: 10mm 10mm 14mm 10mm; }

* { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }

body { font-family: Arial, sans-serif; font-size: 9px; color: #4a4a4a; margin: 0; padding: 0; }

/* HEADER */
.header-wrap { border: 1px solid #444; padding: 10px 14px; }
.header-wrap table { width: 100%; border-collapse: collapse; }
.header-wrap td { vertical-align: middle; padding: 0; }
.hdr-left { width: 155px; }
.hdr-left img { height: 44px; }
.hdr-center { text-align: center; line-height: 1.15; }
.header-title { font-size: 20px; font-weight: 800; letter-spacing: 0.6px; color: #111; }
.header-sub { margin-top: 4px; font-size: 11px; color: #6b6b6b; }
.hdr-right { width: 155px; text-align: right; font-size: 11px; color: #6b6b6b; line-height: 1.2; }

/* GRID */
.grid { margin-top: 14px; margin-left: -5px; margin-right: -5px; }
.grid::after { content: ''; display: table; clear: both; }
.card { float: left; width: 25%; padding: 0 5px 10px 5px; page-break-inside: avoid; }

.card-box{
  border: 2px solid #bdbdbd;
  border-radius: 10px;
  padding: 10px 10px 32px 10px;
  min-height: 300px;
  position: relative;
  overflow: hidden;
  background: #fff;
}

/* IMAGE */
.imgbox { height: 170px; border-radius: 8px; text-align: center; margin-bottom: 6px; background: #fff; overflow: hidden; }
.imgbox img { max-width: 100%; max-height: 170px; }

/* LABELS (not bold) */
.label { color: #6b6b6b; font-weight: 400; }

/* ITEM + PRICE */
.item-price-row { width: 100%; border-collapse: collapse; margin-bottom: 6px; }
.item-price-row td { padding: 0; vertical-align: baseline; }

.item-td { font-size: 14px; font-weight: 400; white-space: nowrap; color: #4a4a4a; }
.item-code { font-weight: 400; color: #000; font-size: 14px; }

.price-td { text-align: right; white-space: nowrap; }
.case-price { color: #e53935; font-weight: 700; font-size: 14px; }

/* exact like screenshot: $16.25 ca$0.65 pcs (no text spaces) */
.sep-ca { color: #e53935; font-weight: 700; font-size: 11px; margin-left: 6px; }
.unit-price { color: #e53935; font-weight: 700; font-size: 14px; }
.uom { color: #e53935; font-weight: 400; font-size: 11px; margin-left: 3px; }

/* DESC */
.desc { color: #4a4a4a; font-size: 11px; font-weight: 400; height: 30px; overflow: hidden; margin: 3px 0 10px 0; line-height: 1.4; }

/* UPC/CA */
.detail-row { width: 100%; border-collapse: collapse; }
.detail-row td { padding: 3px 0; vertical-align: top; font-size: 11px; font-weight: 400; color: #4a4a4a; }
.muted { color: #6b6b6b; }

/* STOCK */
.stock-row { position: absolute; left: 10px; right: 10px; bottom: 8px; }
.stock-row table { width: 100%; border-collapse: collapse; }
.stock-row td { padding: 0; vertical-align: middle; font-size: 11px; }
.stock-label { color: #6b6b6b; font-weight: 400; }
.stock-badge { text-align: right; }

.badge {
  display: inline-block;
  padding: 3px 12px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}
.badge.out { background: #f8d7da; color: #b42323; border: 1px solid #f1aeb5; }
.badge.in  { background: #d1e7dd; color: #0f5132; border: 1px solid #a3cfbb; }
</style>
</head>

<body>
  <div class="header-wrap">
    <table>
      <tr>
        <td class="hdr-left">{% if company_logo %}<img src="{{ company_logo }}">{% endif %}</td>
        <td class="hdr-center">
          <div class="header-title">PRODUCT CATALOG</div>
          <div class="header-sub">Total Products: {{ total_products }}</div>
        </td>
        <td class="hdr-right">{{ print_date }}</td>
      </tr>
    </table>
  </div>

  <div class="grid">
    {% for p in products %}
      <div class="card">
        <div class="card-box">

          <div class="imgbox">
            {% if p.image_url %}<img src="{{ p.image_url }}">{% endif %}
          </div>

          <table class="item-price-row">
            <tr>
              <td class="item-td"><span class="label">Item:</span> <span class="item-code">{{ p.item_code }}</span></td>
              <td class="price-td">
                <span class="case-price">{{ p.case_price }}</span>{% if p.show_unit_price %}<span class="sep-ca">ca</span><span class="unit-price">{{ p.unit_price }}</span><span class="uom">{{ p.piece_uom | lower }}</span>{% endif %}
              </td>
            </tr>
          </table>

          <div class="desc"><span class="label">Desc:</span> {{ p.desc }}</div>

          <table class="detail-row">
            <tr>
              <td><span class="label">UPC:</span> {{ p.upc or "" }}</td>
              <td style="text-align:right;" class="muted"><span class="label">CA:</span> {{ p.case_pack or "" }}</td>
            </tr>
          </table>

          <div class="stock-row">
            <table>
              <tr>
                <td class="stock-label"><span class="label">Stock:</span></td>
                <td class="stock-badge">
                  {% if p.in_stock %}
                    <span class="badge in">{{ p.stock_qty }}</span>
                  {% else %}
                    <span class="badge out">Out of Stock</span>
                  {% endif %}
                </td>
              </tr>
            </table>
          </div>

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



def _get_stock_map(item_codes, company=None):
    if not item_codes:
        return {}

    if company:
        rows = frappe.db.sql("""
            SELECT b.item_code, SUM(b.actual_qty) as qty
            FROM `tabBin` b
            INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
            WHERE b.item_code IN %(items)s
              AND w.company = %(company)s
            GROUP BY b.item_code
        """, {"items": tuple(item_codes), "company": company}, as_dict=1)
    else:
        rows = frappe.db.sql("""
            SELECT item_code, SUM(actual_qty) as qty
            FROM `tabBin`
            WHERE item_code IN %(items)s
            GROUP BY item_code
        """, {"items": tuple(item_codes)}, as_dict=1)

    return {r.item_code: (r.qty or 0) for r in rows}


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

    child_dt, cat_field, subcat_child_field, subcat_item_field, upc_field = _resolve_categories_table()

    join_cat = ""
    if child_dt and cat_field:
        join_cat = f"""
            LEFT JOIN `tab{child_dt}` cat
              ON cat.parent = it.name
             AND cat.parenttype = 'Item'
             AND cat.parentfield = 'custom_product_categories'
        """
        if filters.get("category"):
            conditions.append(f"cat.`{cat_field}` = %(category)s")

        if filters.get("subcategory"):
            if subcat_child_field:
                conditions.append(f"cat.`{subcat_child_field}` = %(subcategory)s")
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
            ip.currency
        FROM `tabItem` it
        INNER JOIN `tabItem Price` ip
            ON ip.item_code = it.name
           AND ip.price_list = %(price_list)s
        {join_cat}
        {where_clause}
        GROUP BY it.name
        ORDER BY it.item_name
    """, filters, as_dict=1)

    item_codes = [r.item_code for r in rows]
    case_pack_map, piece_uom_map = _get_case_pack_map(item_codes)
    stock_map = _get_stock_map(item_codes, filters.get("company"))

    products = []
    for r in rows:
        price = r.price_list_rate or 0
        currency = r.currency or None

        case_pack = case_pack_map.get(r.item_code) 
        piece_uom = piece_uom_map.get(r.item_code) or "PCS"

        cp_num = float(case_pack) if case_pack not in (None, "", 0) else 0.0
        unit_price_val = (price / cp_num) if cp_num > 0 else None

        # ✅ ONLY show unit price when CA > 1
        show_unit_price = (cp_num > 1 and unit_price_val is not None)

        stock_qty = stock_map.get(r.item_code, 0) or 0
        in_stock = stock_qty > 0

        products.append({
            "item_code": r.item_code,
            "desc": r.item_name or "",
            "image_url": _abs_url(r.image_path),
            "upc": r.upc,
            "case_pack": int(case_pack) if case_pack and float(case_pack).is_integer() else case_pack,
            "piece_uom": piece_uom,

            # ✅ remove "$ " space
            "case_price": _fmt_money_compact(price, currency=currency),

            # unit price string only if needed
            "unit_price": _fmt_money_compact(unit_price_val, currency=currency) if unit_price_val is not None else "",
            "show_unit_price": show_unit_price,

            "stock_qty": int(stock_qty) if float(stock_qty).is_integer() else stock_qty,
            "in_stock": in_stock,
        })

    return products


@frappe.whitelist()
def download_product_catalog_pdf(filters=None):
    if isinstance(filters, str):
        filters = frappe.parse_json(filters)
    filters = filters or {}

    products = _get_products_for_pdf(filters)

    context = {
        "products": products,
        "total_products": len(products),
        "print_date": formatdate(today()),
        "company_logo": _get_company_logo(filters.get("company")),
    }

    html = frappe.render_template(PDF_TEMPLATE, context)

    pdf_options = {
        "page-size": "Letter",
        "margin-top": "14mm",
        "margin-bottom": "12mm",
        "margin-left": "8mm",
        "margin-right": "8mm",
        "encoding": "UTF-8",
        "quiet": "",
        "print-media-type": "",
        "enable-local-file-access": "",

        "footer-left": "Generated by Cotton Valley",
        "footer-right": "Page [page] of [toPage]",
        "footer-font-size": "8",
    }

    pdf = pdfkit.from_string(html, False, options=pdf_options)

    filename = f"Product Catalog - {filters.get('company') or ''}.pdf".replace("/", "-")
    file_doc = save_file(filename, pdf, dt=None, dn=None, is_private=0)
    return {"file_url": file_doc.file_url}
