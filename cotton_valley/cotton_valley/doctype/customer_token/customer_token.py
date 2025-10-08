# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CustomerToken(Document):
	def validate(self):
		if not self.customer:
			frappe.throw("Customer is required")

		# Count other tokens safely
		token_count = frappe.db.count(
			"Customer Token", 
			filters={"customer": self.customer}
		)

		# Lock customer row to prevent race conditions
		frappe.db.sql("SELECT name FROM `tabCustomer` WHERE name=%s FOR UPDATE", self.customer)

		# Update the no_of_login field
		frappe.db.set_value("Customer", self.customer, "no_of_login", token_count)
		frappe.db.set_value("Customer", self.customer, "last_login_date", frappe.utils.now())
