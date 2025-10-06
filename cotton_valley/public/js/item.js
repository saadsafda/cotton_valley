frappe.ui.form.on('Item', {
    refresh: function(frm) {
        $("[data-label='View']").hide();
        $("[data-label='Actions']").hide();
        if (!frm.is_new()) {
            frm.add_custom_button(__('Get Prices'), function() {
                frappe.call({
                    method: "cotton_valley.api.products.get_prices",
                    args: {
                        item_code: frm.doc.item_code
                    },
                    callback: function(r) {
                        if(r.message) {
                            frappe.msgprint("Prices updated successfully");
                            frm.reload_doc();
                        }
                    }
                });
            });
        }
    }
});
