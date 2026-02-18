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
    let d = new frappe.ui.Dialog({
      title: __("Download Product Catalog PDF"),
      fields: [
        {
          fieldname: "header_note",
          fieldtype: "Small Text",
          label: __("Header Note"),
          description: __("This text will appear below the heading in the PDF")
        }
      ],
      primary_action_label: __("Download"),
      primary_action: function (values) {
        d.hide();
        const filters = report.get_values();
        filters.header_note = values.header_note || "";
        const args = encodeURIComponent(JSON.stringify(filters));
        const url = `/api/method/cotton_valley.cotton_valley.report.product_catalog.product_catalog.download_product_catalog_pdf?filters=${args}`;
        window.open(url, "_blank");
      }
    });
    d.show();
  }).addClass("btn-primary");
}
};
