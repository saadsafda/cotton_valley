// Copyright (c) 2026, Saad and contributors
// For license information, please see license.txt

frappe.query_reports["Website Search Analytics"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            reqd: 0,
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 0,
        },
        {
            fieldname: "user_type",
            label: __("User Type"),
            fieldtype: "Select",
            options: "\nAll\nGuest\nLogged In",
            default: "",
        },
        {
            fieldname: "user",
            label: __("User"),
            fieldtype: "Data",
        },
        {
            fieldname: "search_query",
            label: __("Search Query"),
            fieldtype: "Data",
        },
        {
            fieldname: "min_search_count",
            label: __("Minimum Search Count"),
            fieldtype: "Int",
            default: 0,
        },
        {
            fieldname: "page_url",
            label: __("Page URL"),
            fieldtype: "Data",
        },
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
        },
    ],
};
