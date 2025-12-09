// Copyright (c) 2025, Saad and contributors
// For license information, please see license.txt

frappe.query_reports["Abandoned Carts Report"] = {
	"filters": [
		{
            "fieldname": "company",
            "label": "Company",
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 0  
        }
	]
};
