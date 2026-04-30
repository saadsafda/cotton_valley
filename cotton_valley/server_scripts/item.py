import frappe
from frappe.utils import get_datetime


def _clear_product_tags_if_requested(doc):
	clear_requested = doc.get("clear_product_tags") or doc.get("custom_clear_product_tags")
	if not clear_requested:
		return

	# Clear all Item table fields that point to Product Tags.
	for df in doc.meta.get_table_fields():
		if df.options == "Product Tags":
			doc.set(df.fieldname, [])

	# Also clear already-persisted rows to avoid stale child inserts.
	if doc.name:
		frappe.db.delete("Product Tags", {
			"parenttype": "Item",
			"parent": doc.name,
		})

	if doc.meta.get_field("clear_product_tags"):
		doc.set("clear_product_tags", 0)
	if doc.meta.get_field("custom_clear_product_tags"):
		doc.set("custom_clear_product_tags", 0)


def _sanitize_submit_datetime(doc):
	"""
	Protect Item saves/imports from non-datetime strings in submit_datetime.
	"""
	if not doc.meta.get_field("submit_datetime"):
		return

	value = doc.get("submit_datetime")
	if not value:
		return

	try:
		parsed = get_datetime(value)
		doc.set("submit_datetime", parsed)
	except Exception:
		doc.set("submit_datetime", None)


def _prevent_duplicate_item_price(doc, method=None):
	if doc.doctype != "Item Price":
		return

	if not doc.item_code or not doc.price_list:
		return

	exists = frappe.db.exists(
		"Item Price",
		{
			"item_code": doc.item_code,
			"price_list": doc.price_list,
			"name": ["!=", doc.name],
		},
	)
	if exists:
		frappe.throw("Duplicate Item Price: This item already has a price for this Price List.")


def validate(doc, method):
	"""
	Handle Data Import and form saves.
	"""
	_sanitize_submit_datetime(doc)
	_clear_product_tags_if_requested(doc)
	_prevent_duplicate_item_price(doc)


def before_save(doc, method):
	"""
	Handle regular saves from form/API.
	"""
	_sanitize_submit_datetime(doc)
	_clear_product_tags_if_requested(doc)
	_prevent_duplicate_item_price(doc)
