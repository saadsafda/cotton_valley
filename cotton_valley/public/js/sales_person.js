frappe.ui.form.on('Sales Person', {
    setup(frm) {
        if (frm.fields_dict["sales_scheduler"] && frm.fields_dict["sales_scheduler"].grid.get_field("monthly_sales")) {
            frm.fields_dict["sales_scheduler"].grid.get_field("monthly_sales").get_query = function(doc, cdt, cdn){
                var row = locals[cdt][cdn];
                return {
                    filters: {
                        'fiscal_year': row.fiscal_year
                    }
                }
            };
        }

        // Cotton Valley: hierarchical targets (Category -> Subcategory -> Item)
        // Filter Subcategory dropdown by chosen Product Category in the same row.
        if (frm.fields_dict["targets"] && frm.fields_dict["targets"].grid.get_field("product_subcategory")) {
            frm.fields_dict["targets"].grid.get_field("product_subcategory").get_query = function (doc, cdt, cdn) {
                var row = locals[cdt][cdn];
                if (row.product_category) {
                    return {
                        query: "cotton_valley.api.sales_person.get_subcategories_for_category",
                        filters: { product_category: row.product_category }
                    };
                }
                return {};
            };
        }

        // Filter Item dropdown by chosen Subcategory (preferred) or Product Category in the same row.
        if (frm.fields_dict["targets"] && frm.fields_dict["targets"].grid.get_field("item_code")) {
            frm.fields_dict["targets"].grid.get_field("item_code").get_query = function (doc, cdt, cdn) {
                var row = locals[cdt][cdn];
                var filters = { hide: 0 };
                if (row.product_subcategory) {
                    filters.custom_sub_category = row.product_subcategory;
                    return { filters: filters };
                }
                if (row.product_category) {
                    return {
                        query: "cotton_valley.api.sales_person.get_items_for_category",
                        filters: { product_category: row.product_category }
                    };
                }
                return { filters: filters };
            };
        }
    },
});

// Reset child fields when a parent (category/subcategory) is cleared or changed,
// so the Category -> Subcategory -> Item hierarchy stays consistent on each row.
frappe.ui.form.on('Target Detail', {
    product_category: function (frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (!row.product_category) {
            frappe.model.set_value(cdt, cdn, 'product_subcategory', null);
            frappe.model.set_value(cdt, cdn, 'item_code', null);
        }
    },
    product_subcategory: function (frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (!row.product_subcategory) {
            frappe.model.set_value(cdt, cdn, 'item_code', null);
        }
    }
});