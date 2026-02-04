frappe.ui.form.on('Item', {
    refresh: function(frm) {
        $("[data-label='View']").hide();
        $("[data-label='Actions']").hide();
        if (!frm.is_new()) {
            frm.add_custom_button(__('Get Prices'), function() {
                frappe.call({
                    method: "cotton_valley.api.products.get_prices",
                    args: {
                        item_code: frm.doc.item_code,
                        company: frm.doc.company
                    },
                    freeze: true,
                    freeze_message: "Fetching Prices...",
                    callback: function(r) {
                        if(r.message) {
                            frappe.msgprint(__(r.message));
                            frm.reload_doc();
                        }
                    }
                });
            });
            frm.add_custom_button(__('Updates Item Data'), function() {
                frappe.call({
                    method: "cotton_valley.api.products.sync_item_from_api",
                    args: {
                        item_code: frm.doc.item_code,
                        company: frm.doc.company
                    },
                    freeze: true,
                    freeze_message: "Updating Item Data...",
                    callback: function(r) {
                        if(r.message) {
                            frappe.msgprint(__(r.message));
                            frm.reload_doc();
                        }
                    }
                });
            });
            frm.add_custom_button(__('View Item'), function() {
                
                let base_url = "";
                let company_name = frm.doc.company;

                if (company_name == "UDC") {
                    base_url = "https://www.universaldc.com/product/"; 
                } else {
                    base_url = "https://www.cottonvalley.net/product/";
                }

                if (base_url) {
                    
                    let full_url = base_url + encodeURIComponent(frm.doc.item_code);
                    
                    window.open(full_url, '_blank');
                } else {
                    frappe.msgprint("No website URL configured for company: " + company_name);
                }
            }).addClass('btn-primary');
        }
    }
});
