// Copyright (c) 2025, Saad and contributors
// For license information, please see license.txt

frappe.query_reports["Items With Price level"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 0
        },
        {
            "fieldname": "price_list", 
            "label": __("Price List"),
            "fieldtype": "Link",
            "options": "Price List"
        },
        {
            "fieldname": "item_group", 
            "label": __("Product Type"),
            "fieldtype": "Link",
            "options": "Item Group"
        },
        {
            "fieldname": "item_code",
            "label": __("Item Code"),
            "fieldtype": "Link",
            "options": "Item"
        }
    ]
};
