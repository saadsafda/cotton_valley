
frappe.listview_settings['Customer'] = {
    onload(listview) {
        if (frappe.get_route()[2] === 'Report' && !frappe.get_route()[3]) {
            frappe.set_route('customer', 'view', 'report', 'Defualt Customer Report');
        }
        // Hide sidebar
        $('.layout-side-section').hide();
        // Add "Product" button
        listview.page.add_inner_button('Product', () => {
            frappe.set_route("List", "Item");  // Opens Product (Item) list
        });

        // Add "Sales Reps" button
        listview.page.add_inner_button('Sales Reps', () => {
            frappe.set_route("List", "Sales Person");  // Opens Sales Reps list
        });

        const start_customer_sync = (company) => {
            const random_id = (frappe.utils && frappe.utils.get_random)
                ? frappe.utils.get_random(10)
                : Math.random().toString(36).slice(2, 10);
            const task_id = `customer_sync_${random_id}`;
            const title = company === 'UDC' ? __('Sync UDC Customers') : __('Sync CV Customers');

            const dialog = new frappe.ui.Dialog({
                title: title,
                fields: [
                    { fieldtype: 'HTML', fieldname: 'progress_html' }
                ],
                primary_action_label: __('Close'),
                primary_action() {
                    dialog.hide();
                }
            });

            dialog.show();
            const $wrapper = $(dialog.fields_dict.progress_html.wrapper);
            $wrapper.html(`
                <div>
                    <p><strong>Status:</strong> <span class="status-text">${__('Starting...')}</span></p>
                    <p><strong>Progress:</strong> <span class="current">0</span> / <span class="total">0</span></p>
                    <div class="progress" style="height: 24px;">
                        <div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" style="width: 0%;">0%</div>
                    </div>
                    <p class="text-muted small mt-2"><span class="current-customer">-</span></p>
                </div>
            `);

            const update_ui = (data) => {
                const percent = data.percent || 0;
                $wrapper.find('.status-text').text(data.status || __('Running'));
                $wrapper.find('.current').text(data.current || 0);
                $wrapper.find('.total').text(data.total || 0);
                $wrapper.find('.progress-bar').css('width', `${percent}%`).text(`${percent}%`);
                if (data.customer_id) {
                    $wrapper.find('.current-customer').text(`${__('Customer')}: ${data.customer_id}`);
                }
            };

            const handle_progress = (data) => {
                if (!data || data.task_id !== task_id) {
                    return;
                }
                update_ui(data);
                if (data.status === 'complete' || data.status === 'error') {
                    if (frappe.realtime && frappe.realtime.off) {
                        frappe.realtime.off('customer_sync_progress', handle_progress);
                    }
                }
            };

            frappe.realtime.on('customer_sync_progress', handle_progress);

            frappe.call({
                method: company === 'UDC'
                    ? 'cotton_valley.api.customer.fetch_all_UDC_customer_data'
                    : 'cotton_valley.api.customer.fetch_all_cv_customer_data',
                args: { task_id: task_id },
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        update_ui({
                            status: __('complete'),
                            percent: 100
                        });
                        frappe.show_alert({ message: __('Customer sync completed.'), indicator: 'green' });
                    } else {
                        update_ui({
                            status: __('error'),
                            message: (r.message && r.message.message) || __('Unknown error')
                        });
                        frappe.msgprint(__('Customer sync failed: ') + ((r.message && r.message.message) || __('Unknown error')));
                    }
                },
                error: function(r) {
                    update_ui({ status: __('error') });
                    frappe.msgprint(__('Customer sync error: ') + (r.message || r.responseText || __('Unknown error')));
                }
            });
        };

        listview.page.add_inner_button('Sync Customers (CV)', () => {
            start_customer_sync('Cotton Valley');
        });

        listview.page.add_inner_button('Sync Customers (UDC)', () => {
            start_customer_sync('UDC');
        });

        const start_mass_email = () => {
            const random_id = (frappe.utils && frappe.utils.get_random)
                ? frappe.utils.get_random(10)
                : Math.random().toString(36).slice(2, 10);
            const task_id = `mass_email_${random_id}`;

            const dialog = new frappe.ui.Dialog({
                title: __('Send Mass Email'),
                fields: [
                    { fieldtype: 'HTML', fieldname: 'progress_html' }
                ],
                primary_action_label: __('Close'),
                primary_action() {
                    dialog.hide();
                }
            });

            dialog.show();
            const $wrapper = $(dialog.fields_dict.progress_html.wrapper);
            $wrapper.html(`
                <div>
                    <p><strong>Status:</strong> <span class="status-text">${__('Starting...')}</span></p>
                    <p><strong>Progress:</strong> <span class="current">0</span> / <span class="total">0</span></p>
                    <p><strong>Sent:</strong> <span class="sent">0</span> | <strong>Skipped:</strong> <span class="skipped">0</span> | <strong>Failed:</strong> <span class="failed">0</span></p>
                    <div class="progress" style="height: 24px;">
                        <div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" style="width: 0%;">0%</div>
                    </div>
                    <p class="text-muted small mt-2"><span class="current-customer">-</span></p>
                </div>
            `);

            const update_ui = (data) => {
                const percent = data.percent || 0;
                $wrapper.find('.status-text').text(data.status || __('Running'));
                $wrapper.find('.current').text(data.current || 0);
                $wrapper.find('.total').text(data.total || 0);
                $wrapper.find('.sent').text(data.sent || 0);
                $wrapper.find('.skipped').text(data.skipped || 0);
                $wrapper.find('.failed').text(data.failed || 0);
                $wrapper.find('.progress-bar').css('width', `${percent}%`).text(`${percent}%`);
                if (data.customer_id) {
                    $wrapper.find('.current-customer').text(`${__('Customer')}: ${data.customer_id}`);
                }
            };

            const handle_progress = (data) => {
                if (!data || data.task_id !== task_id) {
                    return;
                }
                update_ui(data);
                if (data.status === 'complete' || data.status === 'error') {
                    if (frappe.realtime && frappe.realtime.off) {
                        frappe.realtime.off('mass_email_progress', handle_progress);
                    }
                }
            };

            frappe.realtime.on('mass_email_progress', handle_progress);

            frappe.call({
                method: 'cotton_valley.server_scripts.customer.send_email_to_all_customers',
                args: { task_id: task_id, publish_progress: 1 },
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        update_ui({
                            status: __('complete'),
                            percent: 100,
                            current: r.message.total,
                            total: r.message.total,
                            sent: r.message.sent,
                            skipped: r.message.skipped,
                            failed: r.message.failed
                        });
                        frappe.show_alert({ message: __('Mass emails completed.'), indicator: 'green' });
                    } else {
                        update_ui({ status: __('error') });
                        frappe.msgprint(__('Mass email failed: ') + ((r.message && r.message.message) || __('Unknown error')));
                    }
                },
                error: function(r) {
                    update_ui({ status: __('error') });
                    frappe.msgprint(__('Mass email error: ') + (r.message || r.responseText || __('Unknown error')));
                }
            });
        };

        listview.page.add_inner_button(__('Send Mass Email (All Customers)'), () => {
            frappe.confirm(__('Are you sure you want to send the Mass Email template to all customers?'), function () {
                start_mass_email();
            });
        });
    }
};
