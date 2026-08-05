// Copyright (c) 2026, Saad and contributors
// For license information, please see license.txt

frappe.query_reports["Buyer Catalog"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			on_change: function () {
				frappe.query_report.set_filter_value("item_group", "");
				frappe.query_report.set_filter_value("category", "");
				frappe.query_report.set_filter_value("subcategory", "");
			}
		},
		{
			fieldname: "price_list",
			label: __("Price List"),
			fieldtype: "Link",
			options: "Price List",
			reqd: 1
		},
		{
			fieldname: "item_group",
			label: __("Product Type"),
			fieldtype: "Link",
			options: "Item Group",
			get_query: function () {
				const company = frappe.query_report.get_filter_value("company");
				const price_list = frappe.query_report.get_filter_value("price_list");
				return {
					query: "cotton_valley.cotton_valley.report.buyer_catalog.buyer_catalog.get_product_types",
					filters: {
						company: company || "",
						price_list: price_list || ""
					}
				};
			}
		},
		{
			fieldname: "category",
			label: __("Category"),
			fieldtype: "Link",
			options: "Product Category",
			get_query: function () {
				const company = frappe.query_report.get_filter_value("company");
				return { filters: company ? { company: company } : {} };
			}
		},
		{
			fieldname: "subcategory",
			label: __("Sub-Category"),
			fieldtype: "Link",
			options: "Product Subcategory",
			get_query: function () {
				const company = frappe.query_report.get_filter_value("company");
				const category = frappe.query_report.get_filter_value("category");
				return {
					query: "cotton_valley.cotton_valley.report.buyer_catalog.buyer_catalog.get_subcategories",
					filters: {
						company: company || "",
						category: category || ""
					}
				};
			}
		},
		{ fieldname: "in_stock_only", label: __("In Stock Only"), fieldtype: "Check", default: 0 },
		{
			fieldname: "sort",
			label: __("Sort"),
			fieldtype: "Select",
			options: [
				"",
				"Ascending Order",
				"Descending Order",
				"Low-High Price",
				"High-Low Price",
				"A-Z Order",
				"Z-A Order"
			].join("\n"),
			default: ""
		}
	],

	onload: function (report) {
		report.page.add_inner_button(__("Download PDF"), function () {
			const current = report.get_values();
			const openDialog = function (selectedCategory) {
			const dialog = new frappe.ui.Dialog({
				title: __("Download Buyer Catalog PDF"),
				fields: [
					{
						fieldname: "header_title",
						fieldtype: "Data",
						label: __("Header Title"),
						default: selectedCategory
					},
					{
						fieldname: "section_title",
						fieldtype: "Data",
						label: __("Section Ribbon"),
						default: selectedCategory
					},
					{
						fieldname: "footer_text",
						fieldtype: "Data",
						label: __("Footer Text"),
						default: current.footer_text || "To place an order call us at : (732) 248-2766  Fax:(732) 248-4279  www.cottonvalley.net"
					},
					{
						fieldname: "hide_price",
						fieldtype: "Check",
						label: __("Hide Price in PDF"),
						default: current.hide_price || 0
					}
				],
				primary_action_label: __("Download"),
				primary_action: function (values) {
					dialog.hide();
					const filters = report.get_values() || {};
					filters.header_title = values.header_title || selectedCategory;
					filters.section_title = values.section_title || selectedCategory;
					filters.footer_text = values.footer_text || "";
					filters.hide_price = values.hide_price ? 1 : 0;
					filters.show_logo = 1;
					const args = encodeURIComponent(JSON.stringify(filters));
					const url = `/api/method/cotton_valley.cotton_valley.report.buyer_catalog.buyer_catalog.download_buyer_catalog_pdf?filters=${args}`;
					window.open(url, "_blank");
				}
			});
			dialog.show();
			};

			if (current.category) {
				frappe.db.get_value("Product Category", current.category, ["title"]).then((r) => {
					const categoryTitle = (r && r.message && r.message.title) ? r.message.title : current.category;
					openDialog((categoryTitle || "HARDWARE & ELECTRONICS").toString().toUpperCase());
				}).catch(() => {
					openDialog((current.category || "HARDWARE & ELECTRONICS").toString().toUpperCase());
				});
			} else {
				openDialog("HARDWARE & ELECTRONICS");
			}
		}).addClass("btn-primary");
	}
};
