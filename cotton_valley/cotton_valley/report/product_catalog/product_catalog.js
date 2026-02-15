frappe.query_reports["Product Catalog"] = {
  filters: [
    { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1 },
    { fieldname: "price_list", label: __("Price List"), fieldtype: "Link", options: "Price List", reqd: 1 },
    { fieldname: "category", label: __("Category"), fieldtype: "Link", options: "Product Category" },
    { fieldname: "subcategory", label: __("Sub-Category"), fieldtype: "Link", options: "Product Subcategory" }
  ],

  onload: function (report) {
  report.page.add_inner_button(__("Download PDF"), function () {
    const filters = report.get_values();

    // ✅ Open immediately (Chrome allows this)
    const w = window.open("about:blank", "_blank");

    frappe.call({
      method: "cotton_valley.cotton_valley.report.product_catalog.product_catalog.download_product_catalog_pdf",
      args: { filters },
      freeze: true,
      freeze_message: __("Preparing PDF..."),
      callback: function (r) {
        if (r.message && r.message.file_url) {
          // ✅ Redirect the opened tab to the PDF
          w.location.href = r.message.file_url + "?download=1";
        } else {
          if (w) w.close();
          frappe.msgprint(__("PDF generated but file_url not returned. Check server logs."));
          console.log("PDF response:", r);
        }
      },
      error: function (err) {
        if (w) w.close();
        frappe.msgprint(__("Error while generating PDF. Check Error Log."));
        console.error(err);
      },
    });
  }).addClass("btn-primary");
}
};
