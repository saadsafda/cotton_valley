frappe.ui.form.on('Sales Order', {
    refresh(frm) {
        // Add "Push to ERP" button
        if (frm.doc.docstatus === 1 && !frm.doc.push_to_erp) {
            frm.add_custom_button(__('Push to ERP'), function() {
                frappe.confirm(
                    __('Are you sure you want to push this Sales Order to ERP?'),
                    function() {
                        // User confirmed
                        push_single_order_to_erp(frm);
                    }
                );
            }).addClass('btn-primary');
        }
        
        // Show indicator if already pushed
        if (frm.doc.push_to_erp === 1) {
            frm.dashboard.add_indicator(__('Pushed to ERP'), 'green');
        }
    }
});

function push_single_order_to_erp(frm) {
    frappe.call({
        method: 'cotton_valley.api.sales_order.push_to_erp',
        args: {
            sales_orders: [frm.doc.name]
        },
        freeze: true,
        freeze_message: __('Pushing order to ERP...'),
        callback: function(r) {
            if (r.message && r.message.status === 'success') {
                frappe.show_alert({
                    message: __('Successfully pushed to ERP'),
                    indicator: 'green'
                }, 5);
                
                // Reload the form to show updated status
                frm.reload_doc();
            } else {
                const errorMsg = r.message?.results?.failed?.[0]?.error || 'Failed to push order to ERP';
                frappe.msgprint({
                    title: __('Error'),
                    message: errorMsg,
                    indicator: 'red'
                });
            }
        },
        error: function(r) {
            frappe.msgprint({
                title: __('Error'),
                message: __('An error occurred while pushing to ERP'),
                indicator: 'red'
            });
        }
    });
}
