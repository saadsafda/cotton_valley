import json

import frappe


def execute():
	format_data = frappe.db.get_value("Print Format", "SO Print Format", "format_data")
	if not format_data:
		return

	try:
		json.loads(format_data)
		return
	except json.JSONDecodeError:
		# The quantity expression had unescaped double quotes inside the JSON string.
		fixed_format_data = format_data.replace('get_formatted("qty")', "get_formatted('qty')")

	# Validate before writing, and preserve any other site-specific template changes.
	json.loads(fixed_format_data)
	frappe.db.set_value("Print Format", "SO Print Format", "format_data", fixed_format_data)
	frappe.clear_cache(doctype="Print Format")
