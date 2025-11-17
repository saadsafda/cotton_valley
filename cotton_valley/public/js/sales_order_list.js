frappe.listview_settings['Sales Order'] = {
    refresh: function(listview) {
        listview.page.add_inner_button(__('Export Dual Company Reports'), function() {
            
            // Get selected SO names (list of IDs). If none are checked, this will be an empty array [].
            var selected_sos = listview.get_checked_items(true); 
            
            // --- FIX APPLIED HERE ---
            // If the array is empty, send 'null' to Python.
            // If it has items, send the array.
            var argument_to_send = (selected_sos.length > 0) ? selected_sos : null;

            frappe.call({
                method: "cotton_valley.server_scripts.export_utils.export_dual_company_sales_orders",
                args: {
                    // Pass the list of selected IDs to the Python function
                    selected_so_names: argument_to_send 
                },
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        
                        let download_links_html = r.message.map(function(file_url) {
                            // Extract the filename for display purposes
                            let file_name = decodeURIComponent(file_url).split('/').pop();
                            return `<li><a href="/api/method/frappe.utils.file_manager.download_file?file_url=${encodeURIComponent(file_url)}" target="_blank">${file_name}</a></li>`;
                        }).join('');

                        frappe.msgprint({
                            title: __('Export Complete'),
                            indicator: 'green',
                            message: __('Reports generated successfully. Click the links below to download:') + `<ul>${download_links_html}</ul>`, 
                        });
                    } else {
                        frappe.msgprint({
                            title: __('Export Failed or No Data'),
                            indicator: 'orange',
                            message: __('Could not generate reports. Check server logs or ensure data matches filters.')
                        });
                    }
                }
            });
        }).addClass('btn-warning').removeClass('btn-default');
    },
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
        callback: function (r) {
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
        error: function (r) {
            frappe.msgprint({
                title: __('Error'),
                message: 'An error occurred while pushing to ERP',
                indicator: 'red'
            });
        }
    });
}