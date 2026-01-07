// Copyright (c) 2026, Saad and contributors
// For license information, please see license.txt

frappe.query_reports["Inventory Level Check"] = {
	"filters": [
		{
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 0
        },
        {
            "fieldname": "item_code",
            "label": __("Item Code"),
            "fieldtype": "Link",
            "options": "Item",
            "reqd": 0
        },
        {
            "fieldname": "item_name",
            "label": __("Item Name"),
            "fieldtype": "Data",
            "reqd": 0
        },
        {
            "fieldname": "item_group",
            "label": __("Product Type"),
            "fieldtype": "Link",
            "options": "Item Group",
            "reqd": 0
        }

	]
};
