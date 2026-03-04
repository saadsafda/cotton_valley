frappe.dom.set_style(`
  .dt-cell--col-0 { min-width: 55px !important; width: 55px !important; }
  .dt-cell--col-0 .dt-cell__content { overflow: visible !important; }
`);

frappe.query_reports["Product Catalog"] = {
  filters: [
    { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1,
      on_change: function () {
        // Clear dependent filters when company changes
        frappe.query_report.set_filter_value("category", "");
        frappe.query_report.set_filter_value("subcategory", "");
      }
    },
    { fieldname: "price_list", label: __("Price List"), fieldtype: "Link", options: "Price List", reqd: 1 },
    { fieldname: "category", label: __("Category"), fieldtype: "Link", options: "Product Category",
      get_query: function () {
        var company = frappe.query_report.get_filter_value("company");
        return { filters: company ? { company: company } : {} };
      }
    },
    { fieldname: "subcategory", label: __("Sub-Category"), fieldtype: "Link", options: "Product Subcategory",
      get_query: function () {
        var company = frappe.query_report.get_filter_value("company");
        var category = frappe.query_report.get_filter_value("category");
        return {
          query: "cotton_valley.cotton_valley.report.product_catalog.product_catalog.get_subcategories",
          filters: { company: company || "", category: category || "" }
        };
      }
    },
    { fieldname: "hide_price", label: __("Hide Price in PDF"), fieldtype: "Check", default: 0 }
  ],

  onload: function (report) {
  report.page.add_inner_button(__("Download PDF"), function () {
    const current = report.get_values();
    let d = new frappe.ui.Dialog({
      title: __("Download Product Catalog PDF"),
      fields: [
        { fieldname: "header_title", fieldtype: "Data", label: __("Header Title"), default: (current.header_title || "PRODUCT CATALOG") },
        { fieldname: "header_sub", fieldtype: "Data", label: __("Header Subtitle"), default: (current.header_sub || "") },
        { fieldname: "header_note", fieldtype: "Small Text", label: __("Header Note"), description: __("This text will appear below the heading in the PDF"), default: (current.header_note || "") },
        { fieldname: "footer_note", fieldtype: "Data", label: __("Footer Custom Text"), description: __("Optional text shown below 'Total Products' in the footer"), default: (current.footer_note || "") },
        { fieldname: "hide_price", fieldtype: "Check", label: __("Hide Price in PDF"), default: (current.hide_price || 0) },
      ],
      primary_action_label: __("Download"),
      primary_action: function (values) {
        d.hide();
        const filters = report.get_values();
        // copy dialog values into filters (override or add)
        filters.header_title = values.header_title || "PRODUCT CATALOG";
        filters.header_sub = values.header_sub || "";
        filters.header_note = values.header_note || "";
        if (values.footer_note) filters.footer_note = values.footer_note;
        filters.hide_price = values.hide_price ? 1 : 0;
        const args = encodeURIComponent(JSON.stringify(filters));
        const url = `/api/method/cotton_valley.cotton_valley.report.product_catalog.product_catalog.download_product_catalog_pdf?filters=${args}`;
        window.open(url, "_blank");
      }
    });
    d.show();
  }).addClass("btn-primary");
}
};
