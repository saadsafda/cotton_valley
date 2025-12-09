frappe.ui.form.on('Tag', {
    refresh: function (frm) {
        if (frm.doc.company) {
            frm.set_query("product_name", "products", function(doc, cdt, cdn) {
                return {
                    filters: {
                        company: doc.company
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
                        company: doc.company
                    }
                };
            });
        }
    }
});
