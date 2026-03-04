frappe.ui.form.on('Tag', {
    refresh: function (frm) {
        if (frm.doc.company || frm.doc.product_type) {
            frm.set_query("product_name", "products", function(doc, cdt, cdn) {
                return {
                    filters: {
                        company: doc.company,
                        item_group: doc.product_type
                    }
                };
            });
        }
    },
    company: function (frm) {
        if (frm.doc.company) {
            frm.set_query("product_name", "products", function(doc, cdt, cdn) {
                return {
                    filters: {
                        company: doc.company,
                        item_group: doc.product_type
                    }
                };
            });
        }
    },
    product_type: function (frm) {
        if (frm.doc.product_type) {
            frm.set_query("product_name", "products", function(doc, cdt, cdn) {
                return {
                    filters: {
                        company: doc.company,
                        item_group: doc.product_type
                    }
                };
            });
        }
    }
});
