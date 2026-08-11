// Self-executing function to set up image view fixes immediately
(function() {
    // Add CSS to ensure checkbox is visible and clickable in image view
    if (!$('#item-image-view-fix').length) {
        $('head').append(`
            <style id="item-image-view-fix">
                .image-view-item .image-view-header {
                    position: relative;
                    z-index: 10;
                    pointer-events: auto !important;
                }
                .image-view-item .image-view-header input[type="checkbox"] {
                    pointer-events: auto !important;
                    cursor: pointer !important;
                    position: relative;
                    z-index: 11;
                }
                .image-view-item .image-view-header .like-action {
                    pointer-events: auto !important;
                    cursor: pointer !important;
                }
            </style>
        `);
    }

    // Fix: Handle checkbox click directly
    $(document).off('click.item_checkbox_fix').on('click.item_checkbox_fix', '.image-view-item .list-row-checkbox', function(e) {
        e.stopPropagation();
        e.stopImmediatePropagation();
    });

    // Fix: Handle click on header area (but not on checkbox or like button)
    $(document).off('click.item_header_fix').on('click.item_header_fix', '.image-view-item .image-view-header', function(e) {
        if ($(e.target).is('input[type="checkbox"]') || $(e.target).closest('.like-action').length) {
            e.stopPropagation();
            return;
        }
        e.preventDefault();
        e.stopPropagation();
        const $checkbox = $(this).find('input[type="checkbox"]');
        if ($checkbox.length) {
            $checkbox.prop('checked', !$checkbox.prop('checked')).trigger('change');
        }
    });
})();

frappe.listview_settings['Item'] = {
    add_fields: ["hide"],
    get_indicator: function (doc) {
        if (cint(doc.hide)) {
            return [__("Disabled"), "red", "hide,=,1"];
        }
        return [__("Enabled"), "green", "hide,=,0"];
    },
    onload(listview) {
        let route = frappe.get_route();

        listview.page.add_inner_button(__('Export Catalog'), function () {

            // 1. Get Selected Items
            const selected_items = listview.get_checked_items();

            if (selected_items.length === 0) {
                frappe.msgprint(__("Please select at least one item."));
                return;
            }

            // Extract just the 'name' (ID) of the items
            const item_names = selected_items.map(i => i.name);

            let export_dialog = null;

            export_dialog = new frappe.ui.Dialog({
                title: __('Export Catalog'),
                fields: [
                    {
                        fieldname: 'company',
                        label: __('Company'),
                        fieldtype: 'Link',
                        options: 'Company',
                        reqd: 1,
                        onchange: function () {
                            export_dialog.set_value('price_list', '');
                            export_dialog.set_value('item_group', '');
                        }
                    },
                    {
                        fieldname: 'price_list',
                        label: __('Price List'),
                        fieldtype: 'Link',
                        options: 'Price List',
                        get_query: function () {
                            const company = export_dialog ? export_dialog.get_value('company') : '';
                            return {
                                query: 'cotton_valley.api.products.get_catalog_price_list_link_options',
                                filters: {
                                    company: company || ''
                                }
                            };
                        },
                        reqd: 1,
                        onchange: function () {
                            export_dialog.set_value('item_group', '');
                        }
                    },
                    {
                        fieldname: 'item_group',
                        label: __('Product Type'),
                        fieldtype: 'Link',
                        options: 'Item Group',
                        get_query: function () {
                            const company = export_dialog ? export_dialog.get_value('company') : '';
                            const price_list = export_dialog ? export_dialog.get_value('price_list') : '';
                            return {
                                query: 'cotton_valley.cotton_valley.report.product_catalog.product_catalog.get_product_types',
                                filters: {
                                    company: company || '',
                                    price_list: price_list || ''
                                }
                            };
                        }
                    }
                ],
                primary_action_label: __('Export'),
                primary_action: function (values) {
                    if (!values.company || !values.price_list) {
                        frappe.msgprint(__('Please select both Company and Price List.'));
                        return;
                    }

                    export_dialog.hide();

                    // 2. Trigger Download - use open_url_post for file downloads via POST
                    frappe.msgprint({
                        title: __('Generating Catalog'),
                        message: __('Please wait while we generate your catalog...'),
                        indicator: 'blue'
                    });

                    setTimeout(() => {
                        const form = document.createElement('form');
                        form.method = 'POST';
                        form.action = '/api/method/cotton_valley.api.products.download_custom_catalog';
                        form.target = '_blank';

                        const input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = 'items';
                        input.value = JSON.stringify(item_names);
                        form.appendChild(input);

                        const company_input = document.createElement('input');
                        company_input.type = 'hidden';
                        company_input.name = 'company';
                        company_input.value = values.company;
                        form.appendChild(company_input);

                        const price_list_input = document.createElement('input');
                        price_list_input.type = 'hidden';
                        price_list_input.name = 'price_list';
                        price_list_input.value = values.price_list;
                        form.appendChild(price_list_input);

                        if (values.item_group) {
                            const item_group_input = document.createElement('input');
                            item_group_input.type = 'hidden';
                            item_group_input.name = 'item_group';
                            item_group_input.value = values.item_group;
                            form.appendChild(item_group_input);
                        }

                        const csrf = document.createElement('input');
                        csrf.type = 'hidden';
                        csrf.name = 'csrf_token';
                        csrf.value = frappe.csrf_token;
                        form.appendChild(csrf);

                        document.body.appendChild(form);
                        form.submit();
                        document.body.removeChild(form);
                    }, 250);
                }
            });

            export_dialog.show();
        });

        if (frappe.get_route()[2] === 'Report' && !frappe.get_route()[3]) {
            frappe.set_route('item', 'view', 'report', 'Product Report');
        }
        // Hide sidebar
        $('.layout-side-section').hide();
        // Add "Product" button
        listview.page.add_inner_button('Customer', () => {
            frappe.set_route("List", "Customer");  // Opens Product (Item) list
        });

        // Add "Sales Reps" button
        listview.page.add_inner_button('Sales Reps', () => {
            frappe.set_route("List", "Sales Person");  // Opens Sales Reps list
        });
    }
};

