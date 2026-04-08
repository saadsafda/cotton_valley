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


@frappe.whitelist()
def upsert_item_from_client():
	"""Create or update an Item from client payload using item_code as the key."""
	try:
		data = frappe.request.get_data(as_text=True)
		if not data:
			frappe.local.response["http_status_code"] = 400
			return {"status": "error", "message": "No data provided"}

		payload = json.loads(data)

		item_code = payload.get("item_code") or payload.get("name")
		if not item_code:
			frappe.local.response["http_status_code"] = 400
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
			"disabled": "disabled",
			"pallet_hi": "custom_pallet_hi",
			"pallet_ti": "custom_pallet_ti",
			"carton_upc": "custom_carton_upc",
			"upc": "custom_upc",
			"cbm": "custom_cbm",
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

		item_doc.save(ignore_permissions=True)
		frappe.db.commit()

		return {
			"status": "success",
			"message": f"Item {item_code} successfully {'created' if is_new else 'updated'}",
			"item_code": item_code,
		}

	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "Upsert Item From Client API")
		frappe.local.response["http_status_code"] = 500
		return {"status": "error", "message": str(exc)}
