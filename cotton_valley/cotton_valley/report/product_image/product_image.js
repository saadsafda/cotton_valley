// Copyright (c) 2025, Saad and contributors
// For license information, please see license.txt

frappe.query_reports["Product image"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": 0
        },
        {
            "fieldname": "item_code",
            "label": __("Product ID"),
            "fieldtype": "Link",
            "options": "Item",
            "default": 0
        },
        {
            "fieldname": "item_group",
            "label": __("Product Type"),
            "fieldtype": "Link",
            "options": "Item Group",
            "default": 0
        },
        {
            "fieldname": "enabled_status",
            "label": __("Status"),
            "fieldtype": "Select",
            "options": ["", "Enabled", "Disabled"],
            "default": ""
        },
        {
            "fieldname": "missing_main_image",
            "label": __("Main Image Not Found"),
            "fieldtype": "Check",
            "default": 0
        }
    ],

    // 1. Set Row Height to 300
    "get_datatable_options": function(options) {
        return Object.assign(options, {
            rowHeight: 300, 
        });
    },

    // 2. CSS to force height and alignment
    "onload": function(report) {
        $("<style>")
            .prop("type", "text/css")
            .html(`
                /* Force row height */
                
                /* Center content */
                .dt-cell__content {
                    height: 100% !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    // padding: 0px !important;
                }
                
                /* Image styling */
                img {
                    max-height: 100%;
                    width: auto;
                    object-fit: contain;
                }
            `)
            .appendTo("head");
    }
};