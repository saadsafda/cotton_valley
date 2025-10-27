// Copyright (c) 2025, Saad and contributors
// For license information, please see license.txt

frappe.ui.form.on("Monthly Sales", {
    onload(frm) {
        if (frm.doc.__islocal) {
            return frm.call('get_months').then(() => {
                frm.refresh_field('sales_target');
            });
        }
    },
});
