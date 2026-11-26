import json
import unittest
from pathlib import Path
from unittest.mock import patch

from jinja2 import Environment

from cotton_valley.patches import fix_so_print_format


class TestSOPrintFormat(unittest.TestCase):
	def setUp(self):
		path = (
			Path(__file__).resolve().parents[1]
			/ "cotton_valley/print_format/so_print_format/so_print_format.json"
		)
		self.format_data = json.loads(path.read_text())["format_data"]

	def test_shipped_format_has_valid_json_and_jinja(self):
		for row in json.loads(self.format_data):
			if row.get("options"):
				Environment().parse(row["options"])

	@patch.object(fix_so_print_format, "frappe")
	def test_repairs_reported_error_and_preserves_customizations(self, frappe):
		broken = self.format_data.replace("get_formatted('qty')", 'get_formatted("qty")')
		with self.assertRaises(json.JSONDecodeError) as error:
			json.loads(broken)
		self.assertEqual(error.exception.pos, 12014)
		customized = self.format_data.replace("Product Name", "Custom Product Name")
		frappe.db.get_value.return_value = broken.replace("Product Name", "Custom Product Name")

		fix_so_print_format.execute()

		frappe.db.set_value.assert_called_once_with(
			"Print Format", "SO Print Format", "format_data", customized
		)
		frappe.clear_cache.assert_called_once_with(doctype="Print Format")
		# A second migration run must leave the repaired format untouched.
		frappe.db.get_value.return_value = customized
		fix_so_print_format.execute()
		self.assertEqual(frappe.db.set_value.call_count, 1)

	@patch.object(fix_so_print_format, "frappe")
	def test_valid_format_is_unchanged(self, frappe):
		frappe.db.get_value.return_value = self.format_data
		fix_so_print_format.execute()
		frappe.db.set_value.assert_not_called()
		frappe.clear_cache.assert_not_called()

	@patch.object(fix_so_print_format, "frappe")
	def test_missing_or_empty_format_is_unchanged(self, frappe):
		for value in (None, ""):
			frappe.db.get_value.return_value = value
			fix_so_print_format.execute()
		frappe.db.set_value.assert_not_called()

	@patch.object(fix_so_print_format, "frappe")
	def test_other_invalid_json_is_not_written(self, frappe):
		frappe.db.get_value.return_value = '[{"options": "truncated'
		with self.assertRaises(json.JSONDecodeError):
			fix_so_print_format.execute()
		frappe.db.set_value.assert_not_called()
		frappe.clear_cache.assert_not_called()
