frappe.ui.form.on('Sales Person', {
    setup(frm) {
        frm.fields_dict["sales_scheduler"].grid.get_field("monthly_sales").get_query = function(doc, cdt, cdn){
			var row = locals[cdt][cdn];
			return {
				filters: {
					'fiscal_year': row.fiscal_year
				}
			}
		};
    },
});