frappe.ui.form.on('Sales Order', {
    customer: function (frm) {
        fetch_customer_details(frm);
    },
    refresh(frm) {
        if (frm.doc.push_to_erp === 1) {
            frm.set_df_property('push_to_erp', 'read_only', 1);
        }
        if (frm.doc.docstatus === 1 && !frm.doc.custom_clear) {
            frm.add_custom_button('Mark Clear', function () {
                frappe.confirm(
                    'Are you sure you want to mark this as Clear?',
                    function () {
                        // If user confirms
                        frm.set_value('custom_clear', 1);
                        frappe.show_alert({ message: 'Marked as Clear ✅', indicator: 'green' });
                    },
                    function () {
                        // If user cancels
                        frappe.show_alert({ message: 'Action cancelled ❌', indicator: 'red' });
                    }
                );
            });
        }

        // populate on load if customer already set
        if (frm.doc.customer) {
            fetch_customer_details(frm);
        }
        // Add "Push to ERP" button
        if (frm.doc.docstatus === 1 && !frm.doc.push_to_erp) {
            frm.add_custom_button(__('Push to ERP'), function () {
                frappe.confirm(
                    __('Are you sure you want to push this Sales Order to ERP?'),
                    function () {
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

        // ===== New Button: Send Email =====
        if (frm.doc.docstatus === 1) { // Only allow for submitted orders
            frm.add_custom_button(__('Send Email'), function () {
                frappe.confirm(
                    __('Are you sure you want to send Sales Order confirmation email?'),
                    function () {
                        // Call backend function
                        frappe.call({
                            method: 'cotton_valley.server_scripts.sales_order.send_sales_order_confirmation_email',
                            args: {
                                doc: frm.doc.name,
                                method: 'manual_trigger'
                            },
                            callback: function (r) {
                                frappe.msgprint(__('Sales Order confirmation email sent successfully!'));
                            },
                            error: function (r) {
                                frappe.msgprint(__('Failed to send email: ' + r.responseText));
                            }
                        });
                    }
                );
            }).addClass('btn-primary');
        }

        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Download Excel'), function () {
                const url =
                    '/api/method/cotton_valley.server_scripts.sales_order.download_sales_order_excel' +
                    '?sales_order=' + encodeURIComponent(frm.doc.name);

                window.open(url);
            });
        }
    },

    push_to_erp: function (frm) {
        if (frm.doc.push_to_erp === 1) {

            frm.set_value('order_status', 'Processing');

            frm.refresh_field('order_status');

            frappe.show_alert({
                message: __('Sales Order successfully marked for ERP sync. Status updated to Processed.'),
                indicator: 'green'
            }, 5);
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
        callback: function (r) {
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
        error: function (r) {
            frappe.msgprint({
                title: __('Error'),
                message: __('An error occurred while pushing to ERP'),
                indicator: 'red'
            });
        }
    });
}

function fetch_customer_details(frm) {
    if (!frm.doc.customer) {
        return;
    }

    frappe.call({
        method: 'frappe.client.get_value',
        args: {
            doctype: 'Customer',
            filters: { name: frm.doc.customer },
            fieldname: ['no_of_orders', 'orders_amount', 'last_order_date']
        },
        callback: function (r) {
            if (r.message) {
                const v = r.message;
                const lastOrder = v.last_order_date || __('N/A');
                const noOfOrders = v.no_of_orders || 0;
                const totalAmount = v.orders_amount || '0.00';

                // Build a nicer HTML card for the HTML field
                const currency = frm.doc.currency ? (frm.doc.currency + ' ') : '';
                const details = `
                    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial; max-width:420px; border:1px solid #e6e9ee; box-shadow: 0 2px 6px rgba(32,33,36,0.08); border-radius:8px; padding:12px; background:#fff;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <div style="font-weight:600; color:#222; font-size:14px;">Customer Summary</div>
                        </div>
                        <div style="display:flex; gap:18px;">
                            <div style="flex:1; color:#555;">
                                <div style="margin-bottom:6px;"><small style="color:#888">Last Order Date</small><div style="font-weight:600; color:#111">${lastOrder}</div></div>
                                <div style="margin-bottom:6px;"><small style="color:#888">No. of Orders</small><div style="font-weight:600; color:#111">${noOfOrders}</div></div>
                            </div>
                            <div style="min-width:140px; text-align:right;">
                                <small style="color:#888">Total Orders Value</small>
                                <div style="font-weight:700; color:#0b5cff; font-size:15px">${currency}${totalAmount}</div>
                            </div>
                        </div>
                    </div>
                `;
                // set HTML content for the HTML field
                frm.set_df_property('custom_customer_details', 'options', details);
                frm.refresh_field("custom_customer_details");
            }
        }
    });
}
