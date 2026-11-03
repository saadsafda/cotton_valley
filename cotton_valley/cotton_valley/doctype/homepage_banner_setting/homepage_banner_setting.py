# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from frappe.utils import validate_url


class HomepageBannerSetting(Document):
	def validate(self):
		if self.catalog_url:
			validate_url(self.catalog_url, throw=True, valid_schemes=("http", "https"))
