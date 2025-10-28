frappe.listview_settings['Sales Order'] = {
    onload(listview) {
        if (frappe.get_route()[2] === 'Report' && !frappe.get_route()[3]) {
            frappe.set_route('sales-order', 'view', 'report', 'Sales Order Report');
        }
        // Hide sidebar
        $('.layout-side-section').hide();
        
        // Add "Customer" button
        listview.page.add_inner_button('Customer', () => {
            frappe.set_route("List", "Customer");  // Opens Customer list
        });

        // Add "Sales Reps" button
        listview.page.add_inner_button('Sales Reps', () => {
            frappe.set_route("List", "Sales Person");  // Opens Sales Reps list
        });

        // Add "Push to ERP" button
        listview.page.add_inner_button('Push to ERP', () => {
            const selected = listview.get_checked_items();
            
            if (selected.length === 0) {
                frappe.msgprint(__('Please select at least one Sales Order'));
                return;
            }

            frappe.confirm(
                `Are you sure you want to push ${selected.length} Sales Order(s) to ERP?`,
                () => {
                    // User confirmed, proceed with pushing
                    push_orders_to_erp(selected, listview);
                }
            );
        });
    }
};

function push_orders_to_erp(selected_orders, listview) {
    frappe.call({
        method: 'cotton_valley.api.sales_order.push_to_erp',
        args: {
            sales_orders: selected_orders.map(item => item.name)
        },
        freeze: true,
        freeze_message: __('Pushing orders to ERP...'),
        callback: function(r) {
            if (r.message && r.message.status === 'success') {
                frappe.show_alert({
                    message: r.message.message,
                    indicator: 'green'
                }, 5);
                
                // Refresh the list to show updated status
                listview.refresh();
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message?.message || 'Failed to push orders to ERP',
                    indicator: 'red'
                });
            }
        },
        error: function(r) {
            frappe.msgprint({
                title: __('Error'),
                message: 'An error occurred while pushing to ERP',
                indicator: 'red'
            });
        }
    });
}