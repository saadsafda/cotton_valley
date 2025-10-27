# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MonthlySales(Document):
	@frappe.whitelist()
	def get_months(self):
		"""
		Initialize sales target months for a Sales Person document.
		"""
		month_list = [
			"January",
			"February",
			"March",
			"April",
			"May",
			"June",
			"July",
			"August",
			"September",
			"October",
			"November",
			"December",
		]
		idx = 1
		for m in month_list:
			mnth = self.append("sales_target")
			mnth.month = m
			mnth.target_amount = 10000.0 / 12
			mnth.idx = idx
			idx += 1
