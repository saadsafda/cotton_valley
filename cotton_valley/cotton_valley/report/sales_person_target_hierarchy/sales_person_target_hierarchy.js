// Copyright (c) 2026, Saad and contributors
// For license information, please see license.txt

frappe.query_reports["Sales Person Target Hierarchy"] = {
	"filters": [
		{
			"fieldname": "sales_person",
			"label": __("Sales Person"),
			"fieldtype": "Link",
			"options": "Sales Person",
			"reqd": 1
		},
		{
			"fieldname": "fiscal_year",
			"label": __("Fiscal Year"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
			"reqd": 1,
			"default": frappe.defaults.get_user_default("fiscal_year") || frappe.sys_defaults.fiscal_year
		},
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company")
		},
		{
			"fieldname": "category",
			"label": __("Product Category"),
			"fieldtype": "Link",
			"options": "Product Category"
		}
	],

	"tree": true,
	"name_field": "id",
	"parent_field": "parent_id",
	"initial_depth": 1,

	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && column.fieldname === "label") {
			if (data.row_type === "Category") {
				value = `<b>${value}</b>`;
			} else if (data.row_type === "Subcategory") {
				value = `<span style="color:#1F75FE">${value}</span>`;
			}
		}
		return value;
	}
};
