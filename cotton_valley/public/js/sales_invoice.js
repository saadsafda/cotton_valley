frappe.ui.form.on('Sales Invoice', {
  refresh(frm) {
    if (frm.doc.docstatus === 1) {
      frm.add_custom_button(__('Download Excel'), function () {
        const url =
          `/api/method/cotton_valley.server_scripts.sales_invoice.download_sales_invoice_excel` +
          `?sales_invoice=${encodeURIComponent(frm.doc.name)}`;

        window.open(url);
      })
    }
  }
});
