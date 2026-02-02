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

	],
    "formatter": function(value, row, column, data, default_formatter) {
        // Ensure row number column shows full number
        if (column.fieldname === "_idx") {
            return row._idx + 1;
        }
        return default_formatter(value, row, column, data);
    },
    "onload": function(report) {
       frappe.dom.set_style(`
        /* Header column target */
        .slick-header-column.row-number, 
        .slick-header-column[id*="_idx_"],
        .slick-header-column:first-child { 
            width: 90px !important; 
            min-width: 90px !important; 
            max-width: 90px !important;
        }

        /* Data cell target */
        .slick-cell.row-number, 
        .slick-cell.l0.r0,
        .slick-cell:first-child { 
            width: 90px !important; 
            min-width: 90px !important; 
            max-width: 90px !important;
            text-align: center !important;
            overflow: visible !important;
        }
        
        /* Ensure text doesn't truncate */
        .datatable .dt-cell__content {
            overflow: visible !important;
            text-overflow: unset !important;
        }
    `);
    }
};
