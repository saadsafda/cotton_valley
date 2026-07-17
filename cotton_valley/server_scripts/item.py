import random
import frappe
from frappe.utils import get_datetime

RECOMMENDED_PRODUCTS_LIMIT = 5


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


def _auto_populate_recommended_products(doc):
	"""
	If the "Recommended Products" grid (custom_recommended) is empty, fill it
	with up to RECOMMENDED_PRODUCTS_LIMIT other active items that share the
	same Subcategory (custom_sub_category) as this item. Subcategory is used
	instead of the broader Category so recommendations are actually similar
	items (e.g. a bottle recommends other bottles, not everything tagged
	under a wide category). If this item has no subcategory, or no other
	item shares it, nothing is added.
	"""
	if not doc.meta.get_field("custom_recommended"):
		return

	if doc.get("custom_recommended"):
		return

	if not doc.name:
		return

	sub_category = doc.get("custom_sub_category")
	if not sub_category:
		return

	conditions = ["i.custom_sub_category = %s", "i.name != %s", "i.hide = 0"]
	values = [sub_category, doc.name]

	if doc.company:
		conditions.append("i.company = %s")
		values.append(doc.company)

	rows = frappe.db.sql(
		f"""
		SELECT DISTINCT i.name
		FROM `tabItem` i
		WHERE {" AND ".join(conditions)}
		""",
		tuple(values),
		as_dict=True,
	)

	if not rows:
		return

	candidates = [r.name for r in rows]
	random.shuffle(candidates)

	for item_name in candidates[:RECOMMENDED_PRODUCTS_LIMIT]:
		doc.append("custom_recommended", {"product_name": item_name})


# def _prevent_duplicate_item_price(doc, method=None):
# 	if doc.doctype != "Item Price":
# 		return

# 	if not doc.item_code or not doc.price_list:
# 		return

# 	exists = frappe.db.exists(
# 		"Item Price",
# 		{
# 			"item_code": doc.item_code,
# 			"price_list": doc.price_list,
# 			"name": ["!=", doc.name],
# 		},
# 	)
# 	if exists:
# 		frappe.throw("Duplicate Item Price: This item already has a price for this Price List.")


def validate(doc, method):
	"""
	Handle Data Import and form saves.
	"""
	_sanitize_submit_datetime(doc)
	_clear_product_tags_if_requested(doc)
	_auto_populate_recommended_products(doc)
	# _prevent_duplicate_item_price(doc)


def before_save(doc, method):
	"""
	Handle regular saves from form/API.
	"""
	_sanitize_submit_datetime(doc)
	_clear_product_tags_if_requested(doc)
	# _prevent_duplicate_item_price(doc)
