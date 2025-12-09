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
		}
	],

	// 1. THIS IS THE KEY FIX: Tell the grid the rows are 200px tall
	"get_datatable_options": function (options) {
		return Object.assign(options, {
			rowHeight: 200,  // Matches the image height in your Python script
		});
	},

	// 2. CSS for alignment only (centering the images)
	"onload": function (report) {
		$("<style>")
			.prop("type", "text/css")
			.html(`
                /* Center content in the cells */
				
                // .dt-cell__content {
                //     display: flex !important;	
                //     align-items: center !important;
                //     justify-content: center !important;
				// 	// padding: 0 !important;
				// }
				
				
                /* Ensure images don't overflow */
                img {
					object-fit: contain;
                }
            `)
			.appendTo("head");
	}
};
