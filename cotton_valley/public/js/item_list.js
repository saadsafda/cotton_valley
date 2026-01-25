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
    onload(listview) {
        let route = frappe.get_route();
        console.log(route, "fdffer");

        listview.page.add_inner_button(__('Export Catalog'), function () {

            // 1. Get Selected Items
            const selected_items = listview.get_checked_items();

            if (selected_items.length === 0) {
                frappe.msgprint(__("Please select at least one item."));
                return;
            }

            // Extract just the 'name' (ID) of the items
            const item_names = selected_items.map(i => i.name);

            // 2. Trigger Download - use open_url_post for file downloads via POST
            frappe.msgprint({
                title: __('Generating Catalog'),
                message: __('Please wait while we generate your catalog...'),
                indicator: 'blue'
            });

            // Use open_url_post which properly handles file downloads with POST data
            setTimeout(() => {
                frappe.call({
                    method: 'frappe.core.doctype.file.file.download_file',
                    args: {
                        file_url: '/api/method/cotton_valley.api.products.download_custom_catalog',
                        download: true
                    },
                    freeze: true,
                    freeze_message: __('Generating catalog for {0} items...', [item_names.length]),
                    callback: function(r) {
                        // This won't work for binary downloads, need different approach
                    }
                });
                
                // Direct POST approach for file download
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = '/api/method/cotton_valley.api.products.download_custom_catalog';
                form.target = '_blank';
                
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'items';
                input.value = JSON.stringify(item_names);
                form.appendChild(input);
                
                const csrf = document.createElement('input');
                csrf.type = 'hidden';
                csrf.name = 'csrf_token';
                csrf.value = frappe.csrf_token;
                form.appendChild(csrf);
                
                document.body.appendChild(form);
                form.submit();
                document.body.removeChild(form);
            }, 500);

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

