# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from cotton_valley.api.website_theme_setting import clear_website_theme_setting_cache


class UDCWebsiteThemeSettings(Document):
	def on_update(self):
		clear_website_theme_setting_cache()
