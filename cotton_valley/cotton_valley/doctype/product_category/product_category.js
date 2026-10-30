// Copyright (c) 2025, Saad and contributors
// For license information, please see license.txt

frappe.ui.form.on("SubCategories", {
	product_subcategory(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.product_subcategory) return;

		const duplicate = (frm.doc.subcategories || []).find(
			(d) => d.name !== row.name && d.product_subcategory === row.product_subcategory
		);
		if (duplicate) {
			frappe.msgprint(
				__("Subcategory {0} is already added in row #{1}", [
					row.product_subcategory.bold(),
					duplicate.idx,
				])
			);
			frappe.model.set_value(cdt, cdn, "product_subcategory", "");
		}
	},
});
