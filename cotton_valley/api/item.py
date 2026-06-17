import json

import frappe
from frappe.utils import flt, getdate

# Maximum number of records handled in one go.
# Uploads up to this size are processed immediately in the request.
# Bigger uploads are split into chunks of this size and each chunk runs as a
# separate background job, so a large batch never blocks (freezes) the server.
CHUNK_SIZE = 50


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _bad_request(message):
	frappe.local.response["http_status_code"] = 400
	return {"status": "error", "message": message}


def _safe_getdate(value):
	if value in (None, "", "null"):
		return None
	try:
		return getdate(value)
	except Exception:
		return None


def _safe_text(value):
	if value in (None, "", "null"):
		return None
	return str(value).strip()


def _normalize_to_list(value):
	"""Normalize scalar/array input into a clean list of string values."""
	if value in (None, "", "null"):
		return []

	if isinstance(value, (list, tuple)):
		return [v for v in (_safe_text(x) for x in value) if v]

	if isinstance(value, str):
		text = value.strip()
		if not text or text.lower() == "null":
			return []

		# Accept JSON array payloads that come as strings.
		if text.startswith("[") and text.endswith("]"):
			try:
				parsed = json.loads(text)
				if isinstance(parsed, list):
					return [v for v in (_safe_text(x) for x in parsed) if v]
			except Exception:
				pass

		# Accept comma-separated values.
		if "," in text:
			return [v for v in (_safe_text(x) for x in text.split(",")) if v]

		single = _safe_text(text)
		return [single] if single else []

	single = _safe_text(value)
	return [single] if single else []


def _resolve_item_category_mapping():
	"""Resolve Item category child table and category link field dynamically."""
	item_meta = frappe.get_meta("Item")
	table_field = item_meta.get_field("custom_product_categories")
	child_dt = table_field.options if table_field and table_field.options else None
	if not child_dt:
		return None, None

	child_meta = frappe.get_meta(child_dt)
	for df in child_meta.fields:
		if df.fieldtype == "Link" and df.options == "Product Category":
			return child_dt, df.fieldname

	return child_dt, None


def _find_product_category(category_ref, company=None):
	category_ref = _safe_text(category_ref)
	if not category_ref:
		return None
	filters = {"erp_id": category_ref}
	if company:
		filters["company"] = company
	return frappe.db.exists("Product Category", filters)


def _find_product_subcategory(subcategory_ref, company=None):
	subcategory_ref = _safe_text(subcategory_ref)
	if not subcategory_ref:
		return None
	filters = {"erp_id": subcategory_ref}
	if company:
		filters["company"] = company
	return frappe.db.exists("Product Subcategory", filters)


@frappe.whitelist()
def item_automation():
	pass


# ---------------------------------------------------------------------------
# Item upsert
# ---------------------------------------------------------------------------
@frappe.whitelist()
def upsert_item_from_client():
	"""Create or update Items from a client payload (a single object or a list)."""
	try:
		data = frappe.request.get_data(as_text=True)
		if not data:
			return _bad_request("No data provided")

		payload = json.loads(data)

		# Single item: process now and return its result.
		if isinstance(payload, dict):
			result = _process_item_upsert(payload)
			if result.get("status") != "success":
				frappe.local.response["http_status_code"] = 400
			return result

		if not isinstance(payload, list):
			return _bad_request("Invalid payload")

		# Small list: process now.
		if len(payload) <= CHUNK_SIZE:
			return {
				"status": "success",
				"message": "Items processed",
				"results": process_item_upsert_batch(payload),
			}

		# Large list: split into small chunks and run each in the background.
		# The request returns immediately and no single job blocks the server.
		_enqueue_in_chunks("cotton_valley.api.item.process_item_upsert_batch", payload)
		return {
			"status": "success",
			"message": "Large batch queued in background",
			"item_count": len(payload),
		}

	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "Upsert Item From Client API")
		frappe.local.response["http_status_code"] = 500
		return {"status": "error", "message": str(exc)}


def _process_item_upsert(payload):
	"""Update one Item from a payload. Commits only on success."""
	if not isinstance(payload, dict):
		return {"status": "error", "message": "Invalid item payload"}

	item_code = payload.get("item_code") or payload.get("name")
	if not item_code:
		return {"status": "error", "message": "Item code (item_code) is required"}

	if not frappe.db.exists("Item", item_code):
		return {"status": "error", "message": f"Item {item_code} not found"}

	item_doc = frappe.get_doc("Item", item_code)

	# Incoming field -> Item field.
	field_map = {
		"item_name": "item_name",
		"disabled": "hide",
		"pallet_hi": "custom_pallet_hi",
		"pallet_ti": "custom_pallet_ti",
		"carton_upc": "custom_carton_upc",
		"upc": "custom_upc",
		"cbm": "custom_cbm",
		"company": "company",
		"case_pack": "custom_case_pack",
		"case_per_pallet": "custom_case_per_pallet",
		"case_pallet_warehouse": "custom_case_pallet_warehouse",
		"case_trucking": "custom_case_trucking",
		"short_description": "custom_short_description",
		"package_length_inch": "custom_package_length_inch",
		"package_width_inch": "custom_package_width_inch",
		"package_height_inch": "custom_package_height_inch",
		"weight_lbs": "custom_weight_lbs",
		"available_stock": "available_stock",
		"po_qty": "po_qty",
		"avaerage_sale": "custom_avaerage_sale",
		"lc": "custom_lc",
		"llc": "custom_llc",
		"pcs_container": "custom_pcs_container",
		"eta_qty": "custom_eta_qty",
		"eta": "eta",
		"vendor_code": "custom_vendor_code",
		"grade": "custom_grade",
		"total_stock": "custom_total_stock",
	}

	# Fields that must be cast before saving.
	float_fields = {
		"custom_pallet_hi", "custom_pallet_ti", "custom_cbm",
		"custom_package_length_inch", "custom_package_width_inch",
		"custom_package_height_inch", "custom_weight_lbs", "available_stock",
		"po_qty", "custom_avaerage_sale", "custom_lc", "custom_llc",
		"custom_eta_qty", "custom_total_stock",
	}
	int_fields = {
		"custom_case_pack", "custom_case_per_pallet",
		"custom_case_pallet_warehouse", "custom_case_trucking",
	}

	for param_name, field_name in field_map.items():
		if param_name not in payload:
			continue
		value = payload.get(param_name)
		if value in (None, "", "null"):
			continue
		if field_name == "eta":
			value = _safe_getdate(value)
		elif field_name in float_fields:
			value = flt(value)
		elif field_name in int_fields:
			value = int(flt(value))
		item_doc.set(field_name, value)

	company = _safe_text(payload.get("company")) or item_doc.company

	# Replace the product categories with the ones given in the payload.
	category_refs = list(dict.fromkeys(_normalize_to_list(payload.get("category_ids"))))
	if category_refs:
		child_dt, cat_field = _resolve_item_category_mapping()
		if child_dt and cat_field:
			rows = []
			for category_ref in category_refs:
				category_name = _find_product_category(category_ref, company=company)
				if not category_name:
					return {"status": "error", "message": f"Category not found for value: {category_ref}"}
				rows.append({cat_field: category_name})
			item_doc.set("custom_product_categories", rows)

	subcategory_ref = _safe_text(payload.get("sub_category_id"))
	if subcategory_ref:
		subcategory_name = _find_product_subcategory(subcategory_ref, company=company)
		if not subcategory_name:
			return {"status": "error", "message": f"Subcategory not found for value: {subcategory_ref}"}
		item_doc.custom_sub_category = subcategory_name

	item_doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"status": "success",
		"message": f"Item {item_code} successfully updated",
		"item_code": item_code,
	}


def process_item_upsert_batch(paraItems):
	"""Process a list of item payloads one by one (used inline and as a job)."""
	results = []
	for entry in paraItems:
		try:
			result = _process_item_upsert(entry)
		except Exception as exc:
			# Undo this item's partial changes; already-saved items are safe.
			frappe.db.rollback()
			frappe.log_error(frappe.get_traceback(), "Item Upsert Batch")
			result = {"status": "error", "message": str(exc)}
		results.append(result)
	return results


# ---------------------------------------------------------------------------
# Item price update
# ---------------------------------------------------------------------------
@frappe.whitelist()
def update_item_price_from_client():
	"""Update a single Item Price using price_id/udc_price_id, item_code and item_rate."""
	try:
		data = frappe.request.get_data(as_text=True)
		if not data:
			return _bad_request("No data provided")

		payload = json.loads(data)
		if not isinstance(payload, dict):
			return _bad_request("Invalid payload")

		result = _process_item_price(payload)
		if result.get("status") != "success":
			frappe.local.response["http_status_code"] = 400
		return result

	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "Update Item Price From Client API")
		frappe.local.response["http_status_code"] = 500
		return {"status": "error", "message": str(exc)}


@frappe.whitelist()
def update_item_price_from_client_batch():
	"""Update multiple Item Prices from an array payload."""
	try:
		data = frappe.request.get_data(as_text=True)
		if not data:
			return _bad_request("No data provided")

		payload = json.loads(data)
		items = payload.get("items") if isinstance(payload, dict) else payload
		if not isinstance(items, list) or not items:
			return _bad_request("items must be a non-empty array")

		# Small list: process now.
		if len(items) <= CHUNK_SIZE:
			return {
				"status": "success",
				"message": "Item prices processed",
				"results": process_item_price_batch(items),
			}

		# Large list: split into small chunks and run each in the background.
		_enqueue_in_chunks("cotton_valley.api.item.process_item_price_batch", items)
		return {
			"status": "success",
			"message": "Large batch queued in background",
			"item_count": len(items),
		}

	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "Batch Update Item Price From Client API")
		frappe.local.response["http_status_code"] = 500
		return {"status": "error", "message": str(exc)}


def _process_item_price(payload):
	"""Update one Item Price from a payload. Commits only on success."""
	if not isinstance(payload, dict):
		return {"status": "error", "message": "Invalid item payload"}

	price_id = payload.get("price_id")
	udc_price_id = payload.get("udc_price_id")
	item_code = payload.get("item_code")
	item_rate = payload.get("item_rate")

	if not price_id and not udc_price_id:
		return {"status": "error", "message": "price_id or udc_price_id is required"}
	if not item_code:
		return {"status": "error", "message": "item_code is required"}
	if item_rate in (None, "", "null"):
		return {"status": "error", "message": "item_rate is required"}
	if not frappe.db.exists("Item", item_code):
		return {"status": "error", "message": f"Item {item_code} not found"}

	price_list_filters = {"price_id": price_id} if price_id else {"udc_price_id": udc_price_id}
	price_list = frappe.db.get_value("Price List", price_list_filters, "name")
	if not price_list:
		missing_key = "price_id" if price_id else "udc_price_id"
		missing_value = price_id or udc_price_id
		return {"status": "error", "message": f"Price List not found for {missing_key} {missing_value}"}

	existing = frappe.db.exists("Item Price", {"item_code": item_code, "price_list": price_list})
	if not existing:
		return {"status": "error", "message": f"Item Price not found for item {item_code} and price list {price_list}"}

	price_doc = frappe.get_doc("Item Price", existing)
	price_doc.price_list_rate = flt(item_rate)
	price_doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"status": "success",
		"message": f"Item price for {item_code} updated successfully",
		"price_id": price_id,
		"udc_price_id": udc_price_id,
		"price_list": price_list,
		"item_code": item_code,
		"item_rate": price_doc.price_list_rate,
	}


def process_item_price_batch(paraItems):
	"""Update a list of Item Prices one by one (used inline and as a job)."""
	results = []
	for entry in paraItems:
		try:
			result = _process_item_price(entry)
		except Exception as exc:
			# Undo this item's partial changes; already-saved items are safe.
			frappe.db.rollback()
			frappe.log_error(frappe.get_traceback(), "Item Price Batch")
			result = {"status": "error", "message": str(exc)}
		results.append(result)
	return results


# ---------------------------------------------------------------------------
# Shared background helper
# ---------------------------------------------------------------------------
def _enqueue_in_chunks(method, items):
	"""Split items into CHUNK_SIZE pieces and queue each piece as its own job."""
	for start in range(0, len(items), CHUNK_SIZE):
		frappe.enqueue(
			method,
			queue="long",
			timeout=1500,
			paraItems=items[start:start + CHUNK_SIZE],
		)
