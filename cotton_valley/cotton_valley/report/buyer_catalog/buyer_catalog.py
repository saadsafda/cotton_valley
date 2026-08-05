# Copyright (c) 2026, Saad and contributors
# For license information, please see license.txt

import base64
import mimetypes
import os

import frappe
from frappe import _
from frappe.utils import cint, flt, formatdate, get_url, today

SEP = "||"

SORT_MAP = {
	"Ascending Order": "it.name ASC",
	"Descending Order": "it.name DESC",
	"Low-High Price": "MAX(ip.price_list_rate) ASC",
	"High-Low Price": "MAX(ip.price_list_rate) DESC",
	"A-Z Order": "it.item_name ASC",
	"Z-A Order": "it.item_name DESC",
}

DEFAULT_ORDER = "CASE WHEN it.website_ranking IS NULL OR it.website_ranking = 0 THEN 1 ELSE 0 END ASC, it.website_ranking ASC"

PDF_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {
	size: Letter;
	margin: 24mm 7mm 14mm 7mm;

	@top-center {
		content: element(page-header);
		width: 100%;
	}
	@bottom-center {
		content: element(page-footer);
		width: 100%;
	}
}

* {
	box-sizing: border-box;
	-webkit-print-color-adjust: exact;
	print-color-adjust: exact;
}

body {
	margin: 0;
	padding: 0;
	font-family: Arial, sans-serif;
	color: #202020;
	font-size: 9px;
	height: 100%;
}

html {
	height: 100%;
}

.page-header {
	position: running(page-header);
	width: 100%;
	background: #fff;
	padding: 4px 6px;
}
.page-header table { width: 100%; border-collapse: collapse; }
.page-header td { vertical-align: middle; padding: 0; }
.hdr-left { flex: 1; text-align: left; }
.hdr-right { width: 100px; text-align: right; }
.hdr-right img { height: 44px; max-width: 100%; object-fit: contain; display: block; }
.header-title {
	font-size: 28px;
	line-height: 1.05;
	font-weight: 900;
	letter-spacing: 0;
	text-transform: uppercase;
	color: #101010;
	margin: 0;
}

.brand { display: none; }
.brand img { display: none; }

.brand-fallback {
	font-size: 10px;
	font-weight: 700;
	letter-spacing: 0.2px;
	text-align: center;
	line-height: 1.1;
	text-transform: uppercase;
	color: #111;
}

.section-ribbon {
	background: #6f8331;
	color: #fff;
	font-size: 11px;
	font-weight: 800;
	text-transform: uppercase;
	display: inline-block;
	padding: 2px 9px 3px 7px;
	position: relative;
	margin-bottom: 6px;
}

.section-ribbon::after {
	content: "";
	position: absolute;
	right: -10px;
	top: 0;
	width: 0;
	height: 0;
	border-top: 8px solid #6f8331;
	border-bottom: 8px solid transparent;
	border-right: 10px solid transparent;
}

.page-wrap {
	border: 1px solid #4b4b4b;
	padding: 7px 6px 3px 6px;
	-webkit-box-decoration-break: clone;
	box-decoration-break: clone;
	height: calc(100% - 6px);
	min-height: calc(100% - 6px);
	margin-bottom: 6px;
}

.page-break-after {
	page-break-after: always;
	break-after: page;
}

.grid-table {
	width: 100%;
	border-collapse: collapse;
	border-spacing: 0;
	table-layout: fixed;
	/* full page-wrap height minus the section ribbon (incl. its margin) */
	height: calc(100% - 26px);
}

.grid-table tbody {
	height: 100%;
}

.grid-table tr {
	vertical-align: top;
	height: 33.333%;
}

.card-cell {
	width: 33.3333%;
	padding: 10px 10px 12px 10px;
	vertical-align: top;
}

.card-cell.empty {
	padding: 10px 10px 12px 10px;
}

.card {
	display: block;
	page-break-inside: avoid;
	break-inside: avoid;
	overflow: visible;
	height: 100%;
	padding: 8px 4px;
}

.imgbox {
	width: 88%;
	height: 126px;
	text-align: center;
	margin: 0 auto 10px auto;
	display: block;
	overflow: visible;
}

.imgbox img {
	width: auto;
	height: auto;
	max-width: 100%;
	max-height: 126px;
	object-fit: contain;
	object-position: center center;
	display: inline-block;
	margin: 0 auto;
}

.sku-line {
	font-size: 9.5px;
	line-height: 1.15;
	font-weight: 900;
	text-align: center;
	margin-bottom: 2px;
	word-break: break-word;
}

.sku-line .orange { color: #ff4f00; }
.sku-line .blue { color: #3b57c8; }
.sku-line .teal { color: #00a7c8; }

.name-line {
	font-size: 8.5px;
	line-height: 1.2;
	font-weight: 700;
	display: block;
	text-align: center;
	text-transform: uppercase;
	width: 88%;
	max-width: 100%;
	margin-left: auto;
	margin-right: auto;
	margin-bottom: 0;
	min-height: 0;
	white-space: normal;
	word-break: break-word;
	word-wrap: break-word;
	overflow-wrap: break-word;
}

.price-line {
	font-size: 9px;
	line-height: 1.15;
	font-weight: 900;
	text-align: center;
	color: #e11717;
	margin-bottom: 2px;
}

.avg-line {
	font-size: 8.5px;
	line-height: 1.15;
	font-weight: 800;
	text-align: center;
	margin-bottom: 3px;
	color: #e11717;
}

.avg-line .black { color: #111; }

.metrics,
.dims {
	font-size: 7.5px;
	line-height: 1.2;
	font-weight: 700;
	text-align: center;
	margin-bottom: 1px;
}

.dims { font-size: 7px; }

.footer {
	padding-top: 5px;
	border-top: 1px solid #b5b5b5;
	text-align: center;
	font-size: 11px;
	font-weight: 700;
}

.page-footer {
	position: running(page-footer);
	width: 100%;
	padding: 0 4px;
	background: #fff;
}
</style>
</head>
<body>
	<div class="page-header">
		<table>
			<tr>
				<td class="hdr-left"><div class="header-title">{{ header_title }}</div></td>
				<td class="hdr-right">{% if company_logo %}<img src="{{ company_logo }}">{% endif %}</td>
			</tr>
		</table>
	</div>

	<div class="page-footer">
		<div class="footer">{{ footer_text }}</div>
	</div>

	{% set items_per_page = 9 %}
	{% for page_start in range(0, products|length, items_per_page) %}
	<div class="page-wrap{% if not loop.last %} page-break-after{% endif %}">
		<div class="section-ribbon">{{ section_title }}</div>

		<table class="grid-table">
			<tbody>
				{% for idx in range(page_start, page_start + items_per_page) %}
				{% set page_idx = idx - page_start %}
				{% if page_idx % 3 == 0 %}
				<tr>
				{% endif %}
					{% if idx < products|length %}
					{% set p = products[idx] %}
					<td class="card-cell">
						<div class="card">
							<div class="imgbox">
								{% if p.image_url %}<img src="{{ p.image_url }}">{% endif %}
							</div>
							<div class="sku-line">
								<span class="orange">#{{ p.item_code }}</span>
								<span class="blue">|{{ p.upc_token }}</span>
								<span class="orange">|{{ p.new_tag }}</span>
								<span class="teal">|CP:{{ p.case_pack_display }}</span>
							</div>
							<div class="name-line">{{ p.title_line }}</div>
							{% if not hide_price %}
							<div class="price-line">RS.P.: {{ p.case_price }} | EA.P:{{ p.ea_price }}</div>
							<div class="avg-line">AVG.S.:{{ p.avg_sales }} <span class="black">| LC.EA.:{{ p.last_cost_ea }} | LLC.EA.:{{ p.last_cost_case }}</span></div>
							{% else %}
							<div class="avg-line">AVG.S.:{{ p.avg_sales }}</div>
							{% endif %}
							<div class="metrics">Total: {{ p.total_qty }} | Avai.Q: {{ p.available_qty }} | PO: {{ p.po_qty }}</div>
							<div class="metrics">CBM: {{ p.cbm }} | PCS-Cont: {{ p.pcs_cont }}</div>
							<div class="dims">Case L/W/H : {{ p.case_lwh }} | ETA : {{ p.eta_display }}</div>
							<div class="dims">Case Weight:{{ p.case_weight }} | Case WH: {{ p.case_wh }}</div>
						</div>
					</td>
					{% else %}
					<td class="card-cell empty"></td>
					{% endif %}
				{% if page_idx % 3 == 2 %}
				</tr>
				{% endif %}
				{% endfor %}
			</tbody>
		</table>
	</div>
	{% endfor %}

</body>
</html>
"""


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": _("Image"), "fieldname": "image", "fieldtype": "HTML", "width": 90},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 260},
		{"label": _("Category Code"), "fieldname": "category_code", "fieldtype": "Data", "width": 180},
		{"label": _("Category Name"), "fieldname": "category_name", "fieldtype": "Data", "width": 220},
		{"label": _("Sub-Category Code"), "fieldname": "subcategory_code", "fieldtype": "Data", "width": 180},
		{"label": _("Sub-Category Name"), "fieldname": "subcategory_name", "fieldtype": "Data", "width": 220},
		{"label": _("Case Price"), "fieldname": "case_price", "fieldtype": "Currency", "options": "currency", "width": 120},
		{"label": _("EA Price"), "fieldname": "ea_price", "fieldtype": "Currency", "options": "currency", "width": 120},
		{"label": _("Available Qty"), "fieldname": "available_qty", "fieldtype": "Float", "width": 120},
		{"label": _("CBM"), "fieldname": "cbm", "fieldtype": "Float", "width": 100},
	]


def _get_order_clause(filters):
	sort = (filters.get("sort") or "").strip()
	return SORT_MAP.get(sort, DEFAULT_ORDER)


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
	for row in rows:
		out[row["name"]] = (row.get(title_field) or row["name"])
	return out


def _fmt_num(value, precision=2):
	if value is None or value == "":
		return "-"
	v = flt(value)
	if v == 0:
		return "-"
	fmt = f"{{0:.{precision}f}}"
	s = fmt.format(v)
	if precision > 0:
		s = s.rstrip("0").rstrip(".")
	return s


def _fmt_num_fixed(value, precision=2):
	"""Format number with fixed decimal places (no stripping trailing zeros) and '-' for blank values."""
	if value is None or value == "":
		return "-"
	v = flt(value)
	if v == 0:
		return "-"
	fmt = f"{{0:.{precision}f}}"
	return fmt.format(v)


def _fmt_date(date_val):
	"""Format date as DD MMM YYYY (e.g., 04 APR 2026)."""
	if not date_val:
		return "-"
	try:
		from datetime import datetime
		if isinstance(date_val, str):
			date_obj = datetime.strptime(date_val[:10], "%Y-%m-%d")
		else:
			date_obj = date_val
		return date_obj.strftime("%d %b %Y").upper()
	except Exception:
		return "-"


def _fmt_money(value):
	return f"${flt(value):.2f}"


def _money_number(value):
	return f"{flt(value):.2f}"


def _abs_url(path):
	if not path:
		return ""
	path = str(path).strip()
	if not path:
		return ""
	if path.startswith(("http://", "https://", "data:")):
		return path
	if path.startswith("/"):
		return get_url(path)
	return get_url("/" + path)


def _to_logo_src(logo_path):
	"""Return a reliable image src for PDF rendering (prefer embedded data-uri for local files)."""
	if not logo_path:
		return ""

	logo_path = str(logo_path).strip()
	if not logo_path:
		return ""

	site_path = frappe.get_site_path()
	file_path = None

	if logo_path.startswith("/files/"):
		file_path = os.path.join(site_path, "public", logo_path.lstrip("/"))
	elif logo_path.startswith("/private/"):
		file_path = os.path.join(site_path, logo_path.lstrip("/"))
	elif logo_path.startswith("/assets/"):
		# In many Frappe sites, /assets is served from sites/assets.
		file_path = os.path.join(site_path, logo_path.lstrip("/"))

	if not file_path:
		return _abs_url(logo_path)

	if not os.path.exists(file_path):
		return _abs_url(logo_path)

	mime = mimetypes.guess_type(file_path)[0] or "image/png"
	if mime == "image/svg+xml":
		return _abs_url(logo_path)

	with open(file_path, "rb") as f:
		b64 = base64.b64encode(f.read()).decode()
	return f"data:{mime};base64,{b64}"


def _get_company_letterhead_logo(company):
	"""Return letterhead image path for the given company, if available."""
	if not company:
		return ""

	try:
		letter_head = frappe.db.get_value("Company", company, "default_letter_head")
		if not letter_head:
			return ""

		for fieldname in ("image", "letter_head", "image_path"):
			img = frappe.db.get_value("Letter Head", letter_head, fieldname)
			if img:
				return img
	except Exception:
		pass

	return ""


def _is_image_file(path):
	if not path:
		return False
	if str(path).strip().startswith("data:image/"):
		return True
	mime = mimetypes.guess_type(str(path))[0] or ""
	return mime.startswith("image/")


def _get_company_attachment_logo(company):
	"""Return best image attachment from Company doc (sidebar image/attachments)."""
	if not company:
		return ""

	try:
		rows = frappe.get_all(
			"File",
			filters={
				"attached_to_doctype": "Company",
				"attached_to_name": company,
				"is_folder": 0,
			},
			fields=["file_url", "attached_to_field", "creation"],
			order_by="creation desc",
			limit_page_length=50,
		)
	except Exception:
		return ""

	if not rows:
		return ""

	# Prefer images explicitly linked to likely logo fields.
	for r in rows:
		if (r.get("attached_to_field") or "") in ("company_logo", "image") and _is_image_file(r.get("file_url")):
			return r.get("file_url") or ""

	# Fallback: any image attachment on Company.
	for r in rows:
		if _is_image_file(r.get("file_url")):
			return r.get("file_url") or ""

	return ""


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

	return child_dt, cat_field, subcat_child_field, subcat_item_field


def _get_item_grade_fieldname():
	"""Resolve the Item field that stores grade text shown in catalog (label: Grade)."""
	item_meta = frappe.get_meta("Item")

	for df in item_meta.fields:
		if (df.label or "").strip().lower() == "grade":
			return df.fieldname

	for candidate in ("custom_grade", "grade", "custom_new_arrivals"):
		if item_meta.get_field(candidate):
			return candidate

	return None


def _get_pending_po_map(item_codes):
	if not item_codes:
		return {}

	rows = frappe.db.sql(
		"""
		SELECT poi.item_code, SUM(GREATEST(poi.qty - poi.received_qty, 0)) AS pending_qty
		FROM `tabPurchase Order Item` poi
		INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
		WHERE po.docstatus = 1
		  AND po.status NOT IN ('Closed', 'Completed', 'Cancelled')
		  AND poi.item_code IN %(items)s
		GROUP BY poi.item_code
		""",
		{"items": tuple(item_codes)},
		as_dict=1,
	)
	return {r.item_code: flt(r.pending_qty) for r in rows}


def _get_avg_sales_map(item_codes, company=None):
	if not item_codes:
		return {}

	params = {
		"items": tuple(item_codes),
		"from_date": frappe.utils.add_days(today(), -90),
	}

	company_sql = ""
	if company:
		company_sql = " AND si.company = %(company)s"
		params["company"] = company

	rows = frappe.db.sql(
		f"""
		SELECT sii.item_code, SUM(sii.qty) AS sold_qty
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE si.docstatus = 1
		  AND si.posting_date >= %(from_date)s
		  AND sii.item_code IN %(items)s
		  {company_sql}
		GROUP BY sii.item_code
		""",
		params,
		as_dict=1,
	)

	return {r.item_code: flt(r.sold_qty) / 3.0 for r in rows}


def _get_company_logo(company):
	company = (company or "").strip()
	company_key = company.lower()
	candidates = []

	if company:
		# 1) Company doctype logo (highest priority)
		candidates.append(frappe.db.get_value("Company", company, "company_logo"))

		# 2) Company image field (if present in this site)
		try:
			company_meta = frappe.get_meta("Company")
			if company_meta.get_field("image"):
				candidates.append(frappe.db.get_value("Company", company, "image"))
		except Exception:
			pass

		# 3) Company doc attachments (sidebar image / attachment list)
		candidates.append(_get_company_attachment_logo(company))

		# 4) Company's default letter head image
		candidates.append(_get_company_letterhead_logo(company))

	# 5) Company-specific website theme settings logos
	if company_key == "udc":
		theme_doctypes = ["UDC Website Theme Settings"]
	else:
		theme_doctypes = ["Website Theme Settings"]

	for dt in theme_doctypes:
		try:
			candidates.append(frappe.db.get_single_value(dt, "header_logo"))
			candidates.append(frappe.db.get_single_value(dt, "footer_logo"))
		except Exception:
			pass

	# 6) Global app logo fallback
	try:
		candidates.append(frappe.db.get_single_value("Website Settings", "app_logo"))
	except Exception:
		pass

	# 7) Last-resort static files by company
	if company_key == "udc":
		candidates.extend([
			"/files/CottonValley_UDC_logo.jpg",
			"/files/UDC_logo.jpg",
		])
	else:
		candidates.extend([
			"/files/CottonValley_logo.jpg",
			"/assets/cotton_valley/logo.png",
			"/files/CottonValley_UDC_logo.jpg",
		])

	seen = set()
	for cand in candidates:
		if not cand:
			continue
		if cand in seen:
			continue
		seen.add(cand)
		src = _to_logo_src(cand)
		if src:
			return src

	return ""


def _build_product_rows(filters):
	if not filters.get("company") or not filters.get("price_list"):
		return []

	conditions = [
		"it.disabled = 0",
		"(it.image IS NOT NULL AND it.image != '')",
		"it.company = %(company)s",
		"ip.price_list = %(price_list)s",
	]

	if filters.get("item_group"):
		conditions.append("it.item_group = %(item_group)s")

	if cint(filters.get("in_stock_only")):
		conditions.append("IFNULL(it.available_stock, 0) > 0")

	child_dt, cat_field, subcat_child_field, subcat_item_field = _resolve_categories_table()
	grade_field = _get_item_grade_fieldname()
	grade_select = f"it.`{grade_field}` AS grade_value," if grade_field else "NULL AS grade_value,"

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

		cat_codes_select = (
			f"IFNULL(GROUP_CONCAT(DISTINCT cat.`{cat_field}` ORDER BY cat.`{cat_field}` SEPARATOR '{SEP}'), '')"
		)

		if subcat_child_field:
			sub_codes_select = (
				f"IFNULL(GROUP_CONCAT(DISTINCT cat.`{subcat_child_field}` ORDER BY cat.`{subcat_child_field}` SEPARATOR '{SEP}'), '')"
			)
		elif subcat_item_field:
			sub_codes_select = f"IFNULL(it.`{subcat_item_field}`, '')"

		if filters.get("category"):
			conditions.append(
				f"""
				it.name IN (
					SELECT cf.parent FROM `tab{child_dt}` cf
					WHERE cf.parenttype = 'Item'
					  AND cf.parentfield = 'custom_product_categories'
					  AND cf.`{cat_field}` = %(category)s
				)
				"""
			)

		if filters.get("subcategory"):
			if subcat_child_field:
				conditions.append(
					f"""
					it.name IN (
						SELECT sf.parent FROM `tab{child_dt}` sf
						WHERE sf.parenttype = 'Item'
						  AND sf.parentfield = 'custom_product_categories'
						  AND sf.`{subcat_child_field}` = %(subcategory)s
					)
					"""
				)
			elif subcat_item_field:
				conditions.append(f"it.`{subcat_item_field}` = %(subcategory)s")

	where_clause = " WHERE " + " AND ".join(conditions)

	rows = frappe.db.sql(
		f"""
		SELECT
			it.name AS item_code,
			it.item_name,
			it.image AS image_path,
			it.custom_case_pack,
			it.custom_upc,
			it.custom_vendor_code,
			{grade_select}
			it.custom_new_arrivals,
			it.custom_cbm,
			it.custom_case_per_pallet,
			it.custom_pcs_container,
			it.custom_avaerage_sale,
			it.custom_lc,
			it.custom_llc,
			it.custom_case_pallet_warehouse,
			it.custom_package_length_inch,
			it.custom_package_width_inch,
			it.custom_package_height_inch,
			it.custom_weight_lbs,
			it.po_qty,
			it.eta,
			it.available_stock,
			it.custom_total_stock,
			it.last_purchase_rate,
			MAX(ip.price_list_rate) AS price_list_rate,
			MAX(ip.currency) AS currency,
			{cat_codes_select} AS category_codes,
			{sub_codes_select} AS subcategory_codes
		FROM `tabItem` it
		INNER JOIN `tabItem Price` ip
			ON ip.item_code = it.name
		   AND ip.price_list = %(price_list)s
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
		for code in _split_codes(r.get("category_codes")):
			all_cat.add(code)
		for code in _split_codes(r.get("subcategory_codes")):
			all_sub.add(code)

	cat_titles = _get_titles_map("Product Category", all_cat)
	sub_titles = _get_titles_map("Product Subcategory", all_sub)

	item_codes = [r.item_code for r in rows]
	po_map = _get_pending_po_map(item_codes)
	avg_sales_map = _get_avg_sales_map(item_codes, filters.get("company"))

	products = []
	for r in rows:
		cat_codes = _split_codes(r.get("category_codes"))
		sub_codes = _split_codes(r.get("subcategory_codes"))
		category_code = ", ".join(cat_codes)
		subcategory_code = ", ".join(sub_codes)
		category_name = ", ".join([cat_titles.get(x, x) for x in cat_codes])
		subcategory_name = ", ".join([sub_titles.get(x, x) for x in sub_codes])

		case_pack = flt(r.custom_case_pack) or 1.0
		case_price = flt(r.price_list_rate)
		ea_price = case_price / case_pack if case_pack > 0 else 0
		last_cost_ea = flt(r.custom_lc if r.custom_lc not in (None, "") else r.last_purchase_rate)
		last_cost_case = flt(r.custom_llc) if r.custom_llc not in (None, "") else (last_cost_ea * case_pack if case_pack > 0 else 0)

		available_qty = flt(r.available_stock)
		po_qty = flt(r.po_qty) if r.po_qty not in (None, "") else flt(po_map.get(r.item_code, 0))
		total_qty = flt(r.custom_total_stock)

		upc_token = (r.custom_vendor_code or "-")

		grade_raw = r.get("grade_value")
		if isinstance(grade_raw, str):
			grade_tag = grade_raw.strip()
		elif grade_raw is None:
			grade_tag = ""
		elif flt(grade_raw) == 0:
			grade_tag = ""
		elif flt(grade_raw) == 1 and grade_field == "custom_new_arrivals":
			grade_tag = "NEW"
		else:
			grade_tag = str(grade_raw)

		# Final fallback: preserve previous behavior if grade field is not configured.
		if not grade_tag and flt(r.custom_new_arrivals):
			grade_tag = "NEW"

		avg_sales_val = r.custom_avaerage_sale if r.custom_avaerage_sale not in (None, "") else avg_sales_map.get(r.item_code, 0)
		case_wh_val = (
			r.custom_case_pallet_warehouse
			if r.custom_case_pallet_warehouse not in (None, "")
			else r.custom_case_per_pallet
		)

		pcs_cont = flt(r.custom_pcs_container or 0)
		eta_display = _fmt_date(r.eta)
		case_lwh = (
			f"{_fmt_num(r.custom_package_length_inch)}"
			f"/{_fmt_num(r.custom_package_width_inch)}"
			f"/{_fmt_num(r.custom_package_height_inch)}"
		)

		products.append(
			{
				"item_code": r.item_code,
				"item_name": r.item_name or "",
				"category_code": category_code,
				"category_name": category_name,
				"subcategory_code": subcategory_code,
				"subcategory_name": subcategory_name,
				"image_url": _abs_url(r.image_path),
				"image_path": r.image_path,
				"title_line": (r.item_name or "").upper(),
				"upc_token": upc_token,
				"new_tag": grade_tag or "-",
				"case_pack": case_pack,
				"case_pack_display": _fmt_num_fixed(case_pack, 0),
				"case_price": _money_number(case_price),
				"ea_price": _money_number(ea_price),
				"avg_sales": _fmt_num_fixed(avg_sales_val, 2),
				"last_cost_ea": _fmt_num_fixed(last_cost_ea, 2),
				"last_cost_case": _fmt_num_fixed(last_cost_case, 2),
				"total_qty": _fmt_num(total_qty, 0) if total_qty > 0 else "-",
				"available_qty": _fmt_num(available_qty, 0) if available_qty > 0 else "-",
				"po_qty": _fmt_num(po_qty, 0) if po_qty > 0 else "-",
				"cbm": _fmt_num_fixed(r.custom_cbm, 4),
				"pcs_cont": _fmt_num_fixed(pcs_cont, 0) if pcs_cont > 0 else "-",
				"case_lwh": case_lwh if case_lwh and case_lwh != "-/-/-" else "-",
				"case_weight": _fmt_num_fixed(r.custom_weight_lbs, 4),
				"case_wh": _fmt_num_fixed(case_wh_val, 2),
				"eta_display": eta_display,
				"currency": r.currency,
			}
		)

	return products


def get_data(filters):
	products = _build_product_rows(filters)
	rows = []
	for p in products:
		image_html = ""
		if p.get("image_url"):
			image_html = (
				f'<img src="{p.get("image_url")}" '
				'style="width:58px;height:58px;object-fit:contain;border:1px solid #ddd;border-radius:4px;background:#fff;">'
			)

		rows.append(
			{
				"image": image_html,
				"item_code": p["item_code"],
				"item_name": p["item_name"],
				"category_code": p.get("category_code", ""),
				"category_name": p.get("category_name", ""),
				"subcategory_code": p.get("subcategory_code", ""),
				"subcategory_name": p.get("subcategory_name", ""),
				"case_price": flt(p["case_price"]),
				"ea_price": flt(p["ea_price"]),
				"available_qty": flt(p["available_qty"]),
				"cbm": flt(p["cbm"]),
			}
		)
	return rows


@frappe.whitelist()
def download_buyer_catalog_pdf(filters=None):
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	filters = filters or {}

	products = _build_product_rows(filters)

	# Embed images directly so the PDF does not depend on the server being
	# able to fetch its own public URLs (fails on some live setups).
	for p in products:
		embedded = _to_logo_src(p.get("image_path"))
		if embedded:
			p["image_url"] = embedded

	context = {
		"products": products,
		"header_title": (filters.get("header_title") or "HARDWARE & ELECTRONICS"),
		"section_title": (filters.get("section_title") or "HARDWARE & ELECTRONICS"),
		"footer_text": (filters.get("footer_text") or ""),
		"hide_price": int(filters.get("hide_price") or 0),
		"company_logo": _get_company_logo(filters.get("company")),
		"company_name": (filters.get("company") or "Cotton Valley"),
		"show_logo": int(filters.get("show_logo") if filters.get("show_logo") is not None else 1),
		"print_date": formatdate(today()),
	}

	html = frappe.render_template(PDF_TEMPLATE, context)

	from weasyprint import HTML as WeasyHTML

	pdf = WeasyHTML(string=html, base_url=frappe.get_site_path()).write_pdf()

	filename = f"Buyer Catalog - {filters.get('company') or 'Catalog'} - {today()}.pdf".replace("/", "-")
	frappe.local.response["filename"] = filename
	frappe.local.response["filecontent"] = pdf
	frappe.local.response["type"] = "download"


@frappe.whitelist()
def get_product_types(doctype, txt, searchfield, start, page_len, filters):
	filters = filters or {}

	conds = [
		"ig.name LIKE %(txt)s",
		"it.disabled = 0",
		"(it.image IS NOT NULL AND it.image != '')",
	]
	params = {"txt": f"%{txt}%", "start": int(start), "page_len": int(page_len)}

	if filters.get("company"):
		conds.append("it.company = %(company)s")
		params["company"] = filters["company"]

	if filters.get("price_list"):
		conds.append(
			"""
			EXISTS (
				SELECT 1
				FROM `tabItem Price` ip
				WHERE ip.item_code = it.name
				  AND ip.price_list = %(price_list)s
			)
			"""
		)
		params["price_list"] = filters["price_list"]

	where = " AND ".join(conds)

	return frappe.db.sql(
		f"""
		SELECT DISTINCT ig.name, ig.name
		FROM `tabItem Group` ig
		INNER JOIN `tabItem` it ON it.item_group = ig.name
		WHERE {where}
		ORDER BY ig.name
		LIMIT %(start)s, %(page_len)s
		""",
		params,
	)


@frappe.whitelist()
def get_subcategories(doctype, txt, searchfield, start, page_len, filters):
	conds = ["sc.name LIKE %(txt)s"]
	params = {"txt": f"%{txt}%", "start": int(start), "page_len": int(page_len)}

	if filters.get("company"):
		conds.append("sc.company = %(company)s")
		params["company"] = filters["company"]

	if filters.get("category"):
		conds.append(
			"""
			sc.name IN (
				SELECT sub.product_subcategory
				FROM `tabSubCategories` sub
				WHERE sub.parenttype = 'Product Category'
				  AND sub.parent = %(category)s
			)
			"""
		)
		params["category"] = filters["category"]

	where = " AND ".join(conds)

	return frappe.db.sql(
		f"""
		SELECT sc.name, sc.title
		FROM `tabProduct Subcategory` sc
		WHERE {where}
		ORDER BY sc.title
		LIMIT %(start)s, %(page_len)s
		""",
		params,
	)
