frappe.ui.form.on('Tag', {
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
