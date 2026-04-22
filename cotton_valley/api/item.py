import json

import frappe
from frappe.utils import flt, getdate


@frappe.whitelist()
def item_automation():
	pass


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

	if isinstance(value, list):
		return [v for v in (_safe_text(x) for x in value) if v]

	if isinstance(value, tuple):
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

	filters = {"erp_id": category_ref, "company": company} if company else {"erp_id": category_ref}
	category_ref_exists = frappe.db.exists("Product Category", filters)
	if category_ref_exists:
		return category_ref_exists
	


def _find_product_subcategory(subcategory_ref, company=None):
	subcategory_ref = _safe_text(subcategory_ref)
	if not subcategory_ref:
		return None
	subcategory_ref_exists = frappe.db.exists("Product Subcategory", {"erp_id": subcategory_ref, "company": company} if company else {"erp_id": subcategory_ref})
	if subcategory_ref_exists:
		return subcategory_ref_exists


def _set_item_category_row(item_doc, category_name):
	child_dt, cat_field = _resolve_item_category_mapping()
	if not child_dt or not cat_field:
		return
	item_doc.custom_product_categories = []
	rows = item_doc.get("custom_product_categories") or []
	for row in rows:
		if row.get(cat_field) == category_name:
			return

	item_doc.append("custom_product_categories", {cat_field: category_name})


@frappe.whitelist()
def upsert_item_from_client():
	"""Create or update an Item from client payload using item_code as the key."""
	try:
		data = frappe.request.get_data(as_text=True)
		if not data:
			frappe.local.response["http_status_code"] = 400
			return {"status": "error", "message": "No data provided"}

		payload = json.loads(data)
		if isinstance(payload, list):
			results = []
			if len(payload) > 20:
				job = frappe.enqueue(
					method="cotton_valley.api.item.process_item_upsert_batch",
					queue="long",
					timeout=10000,
					paraItems=payload,
				)
				return {
					"status": "success",
					"message": "Batch item upsert queued",
					"job_id": job.id if job else None,
					"item_count": len(payload),
				}
			
			results.append(process_item_upsert_batch(payload))
			return {
				"status": "success",
				"message": "Batch item upsert processed",
				"results": results,
			}
		if not isinstance(payload, dict):
			frappe.local.response["http_status_code"] = 400
			return {"status": "error", "message": "Invalid payload"}

		result = _process_item_upsert(payload)
		if result.get("status") != "success":
			frappe.local.response["http_status_code"] = 400
			return result

		return result

	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "Upsert Item From Client API")
		frappe.local.response["http_status_code"] = 500
		return {"status": "error", "message": str(exc)}


def _process_item_upsert(payload):
	if not isinstance(payload, dict):
		return {"status": "error", "message": "Invalid payload"}

	item_code = payload.get("item_code") or payload.get("name")
	if not item_code:
		return {"status": "error", "message": "Item code (item_code) is required"}

	is_new = False
	if frappe.db.exists("Item", item_code):
		item_doc = frappe.get_doc("Item", item_code)
	else:
		is_new = True
		item_doc = frappe.new_doc("Item")
		item_doc.item_code = item_code
		item_doc.item_name = payload.get("item_name") or item_code
		item_doc.item_group = payload.get("item_group") or "COD"
		item_doc.stock_uom = payload.get("stock_uom") or "Nos"

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

	for param_name, field_name in field_map.items():
		if param_name not in payload:
			continue
		value = payload.get(param_name)
		if value in (None, "", "null"):
			continue
		if field_name == "eta":
			item_doc.eta = _safe_getdate(value)
			continue
		if field_name in {
			"custom_pallet_hi",
			"custom_pallet_ti",
			"custom_cbm",
			"custom_package_length_inch",
			"custom_package_width_inch",
			"custom_package_height_inch",
			"custom_weight_lbs",
			"available_stock",
			"po_qty",
			"custom_avaerage_sale",
			"custom_lc",
			"custom_llc",
			"custom_eta_qty",
			"custom_total_stock",
		}:
			item_doc.set(field_name, flt(value))
			continue
		if field_name in {
			"custom_case_pack",
			"custom_case_per_pallet",
			"custom_case_pallet_warehouse",
			"custom_case_trucking",
		}:
			item_doc.set(field_name, int(flt(value)))
			continue
		item_doc.set(field_name, value)

	company = _safe_text(payload.get("company")) or item_doc.company

	category_refs = []
	category_refs.extend(_normalize_to_list(payload.get("category_ids")))

	# Remove duplicates while preserving order.
	category_refs = list(dict.fromkeys(category_refs))

	for category_ref in category_refs:
		category_name = _find_product_category(category_ref, company=company)
		if not category_name:
			return {
				"status": "error",
				"message": f"Category not found for value: {category_ref}",
			}
		_set_item_category_row(item_doc, category_name)

	subcategory_ref = _safe_text(payload.get("sub_category_id"))
	if subcategory_ref:
		subcategory_name = _find_product_subcategory(subcategory_ref, company=company)
		if not subcategory_name:
			return {
				"status": "error",
				"message": f"Subcategory not found for value: {subcategory_ref}",
			}
		item_doc.custom_sub_category = subcategory_name

	item_doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"status": "success",
		"message": f"Item {item_code} successfully {'created' if is_new else 'updated'}",
		"item_code": item_code,
	}


def process_item_upsert_batch(paraItems):
	results = []
	for entry in paraItems:
		if not isinstance(entry, dict):
			results.append({"status": "error", "message": "Invalid item payload"})
			continue
		result = _process_item_upsert(entry)
		results.append(result)
	return results

@frappe.whitelist()
def update_item_price_from_client():
	"""Update Item Price using price_id, item_code, and item_rate."""
	try:
		data = frappe.request.get_data(as_text=True)
		if not data:
			frappe.local.response["http_status_code"] = 400
			return {"status": "error", "message": "No data provided"}

		payload = json.loads(data)

		price_id = payload.get("price_id")
		udc_price_id = payload.get("udc_price_id")
		item_code = payload.get("item_code")
		item_rate = payload.get("item_rate")

		if not price_id and not udc_price_id:
			frappe.local.response["http_status_code"] = 400
			return {"status": "error", "message": "price_id or udc_price_id is required"}
		if not item_code:
			frappe.local.response["http_status_code"] = 400
			return {"status": "error", "message": "item_code is required"}
		if item_rate in (None, "", "null"):
			frappe.local.response["http_status_code"] = 400
			return {"status": "error", "message": "item_rate is required"}

		if not frappe.db.exists("Item", item_code):
			frappe.local.response["http_status_code"] = 404
			return {"status": "error", "message": f"Item {item_code} not found"}

		price_list_filters = {"price_id": price_id} if price_id else {"udc_price_id": udc_price_id}
		price_list = frappe.db.get_value("Price List", price_list_filters, "name")
		if not price_list:
			frappe.local.response["http_status_code"] = 404
			missing_key = "price_id" if price_id else "udc_price_id"
			missing_value = price_id or udc_price_id
			return {
				"status": "error",
				"message": f"Price List not found for {missing_key} {missing_value}",
			}

		existing = frappe.db.exists(
			"Item Price",
			{"item_code": item_code, "price_list": price_list},
		)
		if not existing:
			frappe.local.response["http_status_code"] = 404
			return {
				"status": "error",
				"message": f"Item Price not found for item {item_code} and price list {price_list}",
			}

		price_doc = frappe.get_doc("Item Price", existing)
		price_doc.item_code = item_code
		price_doc.price_list = price_list
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

	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "Update Item Price From Client API")
		frappe.local.response["http_status_code"] = 500
		return {"status": "error", "message": str(exc)}


@frappe.whitelist()
def update_item_price_from_client_batch():
	"""Update multiple Item Price records using an array payload."""
	try:
		data = frappe.request.get_data(as_text=True)
		if not data:
			frappe.local.response["http_status_code"] = 400
			return {"status": "error", "message": "No data provided"}

		payload = json.loads(data)
		items = payload.get("items") if isinstance(payload, dict) else payload
		if not isinstance(items, list) or not items:
			frappe.local.response["http_status_code"] = 400
			return {"status": "error", "message": "items must be a non-empty array"}

		if len(items) > 20:
			job = frappe.enqueue(
				method="cotton_valley.api.item.process_item_price_batch",
				queue="long",
				timeout=10000,
				paraItems=items,
			)
			return {
				"status": "success",
				"message": "Batch item price update queued",
				"job_id": job.id if job else None,
				"item_count": len(items),
			}

		results = process_item_price_batch(items)
		return {
			"status": "success",
			"message": "Batch item price update processed",
			"results": results,
		}

	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "Batch Update Item Price From Client API")
		frappe.local.response["http_status_code"] = 500
		return {"status": "error", "message": str(exc)}


def process_item_price_batch(paraItems):
	results = []
	for entry in paraItems:
		if not isinstance(entry, dict):
			results.append({"status": "error", "message": "Invalid item payload"})
			continue

		price_id = entry.get("price_id")
		udc_price_id = entry.get("udc_price_id")
		item_code = entry.get("item_code")
		item_rate = entry.get("item_rate")

		if not price_id and not udc_price_id:
			results.append({"status": "error", "message": "price_id or udc_price_id is required"})
			continue
		if not item_code:
			results.append({"status": "error", "message": "item_code is required"})
			continue
		if item_rate in (None, "", "null"):
			results.append({"status": "error", "message": "item_rate is required"})
			continue

		if not frappe.db.exists("Item", item_code):
			results.append({"status": "error", "message": f"Item {item_code} not found"})
			continue

		price_list_filters = {"price_id": price_id} if price_id else {"udc_price_id": udc_price_id}
		price_list = frappe.db.get_value("Price List", price_list_filters, "name")
		if not price_list:
			missing_key = "price_id" if price_id else "udc_price_id"
			missing_value = price_id or udc_price_id
			results.append({
				"status": "error",
				"message": f"Price List not found for {missing_key} {missing_value}",
			})
			continue

		existing = frappe.db.exists(
			"Item Price",
			{"item_code": item_code, "price_list": price_list},
		)
		if not existing:
			results.append({
				"status": "error",
				"message": f"Item Price not found for item {item_code} and price list {price_list}",
			})
			continue

		price_doc = frappe.get_doc("Item Price", existing)
		price_doc.item_code = item_code
		price_doc.price_list = price_list
		price_doc.price_list_rate = flt(item_rate)
		price_doc.save(ignore_permissions=True)

		results.append({
			"status": "success",
			"price_id": price_id,
			"udc_price_id": udc_price_id,
			"price_list": price_list,
			"item_code": item_code,
			"item_rate": price_doc.price_list_rate,
		})

	frappe.db.commit()
	return results


