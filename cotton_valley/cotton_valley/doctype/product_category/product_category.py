# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ProductCategory(Document):
	def validate(self):
		self.validate_duplicate_subcategories()

	def validate_duplicate_subcategories(self):
		seen = {}
		for row in self.subcategories:
			if not row.product_subcategory:
				continue
			if row.product_subcategory in seen:
				frappe.throw(
					_("Row #{0}: Subcategory {1} is already added in row #{2}").format(
						row.idx, frappe.bold(row.product_subcategory), seen[row.product_subcategory]
					),
					title=_("Duplicate Subcategory"),
				)
			seen[row.product_subcategory] = row.idx
