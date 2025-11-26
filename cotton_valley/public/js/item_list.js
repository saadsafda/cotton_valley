frappe.listview_settings['Item'] = {
    onload(listview) {
        listview.page.add_inner_button(__('Export Custom Catalog'), function () {

            // 1. Get Selected Items
            const selected_items = listview.get_checked_items();

            if (selected_items.length === 0) {
                frappe.msgprint(__("Please select at least one item."));
                return;
            }

            // Extract just the 'name' (ID) of the items
            const item_names = selected_items.map(i => i.name);

            // 2. Trigger Download - use open_url_post for file downloads
            frappe.msgprint({
                title: __('Generating Catalog'),
                message: __('Please wait while we generate your catalog...'),
                indicator: 'blue'
            });

            // Use open_url_post which handles binary file downloads
            window.open(
                frappe.urllib.get_full_url(
                    '/api/method/cotton_valley.api.products.download_custom_catalog?items=' + 
                    encodeURIComponent(JSON.stringify(item_names))
                )
            );

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

