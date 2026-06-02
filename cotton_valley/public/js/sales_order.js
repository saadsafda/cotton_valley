frappe.ui.form.on('Sales Order', {
    customer: function (frm) {
        fetch_customer_details(frm);
    },
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Restore Last Deleted Items'), function() {
                frappe.confirm(
                    'This will check the last saved version and restore any items that are currently missing. Proceed?',
                    function() {
                        frappe.call({
                            method: 'cotton_valley.server_scripts.sales_order.restore_items_from_history',
                            args: {
                                doc_name: frm.doc.name
                            },
                            freeze: true,
                            freeze_message: __('Restoring items...'),
                            callback: function(r) {
                                if (r.message.status === 'success') {
                                    frappe.msgprint({
                                        title: __('Success'),
                                        indicator: 'green',
                                        message: r.message.message
                                    });
                                    frm.reload_doc();
                                } else {
                                    frappe.msgprint({
                                        title: __('Notice'),
                                        indicator: 'orange',
                                        message: r.message.message
                                    });
                                }
                            }
                        });
                    }
                );
            }, __('Actions'));
        }
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

        if ([0, 1].includes(frm.doc.docstatus)) {
            frm.add_custom_button(__('Download Excel'), function () {
                const url =
                    '/api/method/cotton_valley.server_scripts.sales_order.download_sales_order_excel' +
                    '?sales_order=' + encodeURIComponent(frm.doc.name);

                window.open(url);
            });
        }

        // Render the ERP response as a table with row count + Export to Excel
        render_erp_response_table(frm);
    },

    response(frm) {
        // Re-render whenever the stored response changes
        render_erp_response_table(frm);
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

function get_erp_response_rows(frm) {
    // Returns a normalized array of rows from the `response` field.
    // Success format: [ {item_code, http_status, response}, ... ]
    // Failure format: { error, responses: [ ... ] }
    if (!frm.doc.response) {
        return { rows: [], error: null };
    }
    let parsed;
    try {
        parsed = JSON.parse(frm.doc.response);
    } catch (e) {
        return { rows: [], error: null };
    }

    let raw_rows = [];
    let error = null;
    if (Array.isArray(parsed)) {
        raw_rows = parsed;
    } else if (parsed && typeof parsed === 'object') {
        raw_rows = parsed.responses || [];
        error = parsed.error || null;
    }

    const rows = raw_rows.map(function (r, i) {
        let order_no = '';
        try {
            order_no = (JSON.parse(r.response || '{}')).newOrderNo || '';
        } catch (e) {
            order_no = '';
        }
        return {
            idx: i + 1,
            item_code: r.item_code || '',
            http_status: r.http_status || '',
            order_no: order_no,
            raw: r.response || ''
        };
    });

    return { rows: rows, error: error };
}

function render_erp_response_table(frm) {
    const field = frm.get_field('response_table');
    if (!field) {
        return;
    }

    const data = get_erp_response_rows(frm);
    const rows = data.rows;

    if (!rows.length) {
        const msg = data.error
            ? `<div class="text-danger" style="padding:8px;">${frappe.utils.escape_html(data.error)}</div>`
            : '<div class="text-muted" style="padding:8px;">No ERP response available.</div>';
        field.$wrapper.html(msg);
        return;
    }

    let body = '';
    rows.forEach(function (r) {
        const ok = r.http_status >= 200 && r.http_status < 300;
        const status_badge =
            `<span class="indicator-pill ${ok ? 'green' : 'red'}">${frappe.utils.escape_html(String(r.http_status))}</span>`;
        body += `
            <tr>
                <td style="text-align:center;">${r.idx}</td>
                <td>${frappe.utils.escape_html(r.item_code)}</td>
                <td style="text-align:center;">${status_badge}</td>
                <td>${frappe.utils.escape_html(r.order_no)}</td>
            </tr>`;
    });

    const html = `
        <div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <div style="font-weight:600;">${__('Total Rows')}: <span class="indicator-pill blue">${rows.length}</span></div>
                <button type="button" class="btn btn-default btn-sm btn-export-erp-response">
                    <i class="fa fa-download"></i> ${__('Export to Excel')}
                </button>
            </div>
            <div style="overflow-x:auto;">
                <table class="table table-bordered" style="margin-bottom:0;">
                    <thead>
                        <tr>
                            <th style="width:50px; text-align:center;">#</th>
                            <th>${__('Item Code')}</th>
                            <th style="width:120px; text-align:center;">${__('HTTP Status')}</th>
                            <th>${__('New Order No')}</th>
                        </tr>
                    </thead>
                    <tbody>${body}</tbody>
                </table>
            </div>
        </div>`;

    field.$wrapper.html(html);
    field.$wrapper.find('.btn-export-erp-response').on('click', function () {
        export_erp_response_to_excel(frm, rows);
    });
}

function export_erp_response_to_excel(frm, rows) {
    let table = '<table border="1"><thead><tr>' +
        '<th>#</th><th>Item Code</th><th>HTTP Status</th><th>New Order No</th>' +
        '</tr></thead><tbody>';
    rows.forEach(function (r) {
        table += `<tr>
            <td>${r.idx}</td>
            <td>${frappe.utils.escape_html(r.item_code)}</td>
            <td>${frappe.utils.escape_html(String(r.http_status))}</td>
            <td>${frappe.utils.escape_html(r.order_no)}</td>
        </tr>`;
    });
    table += '</tbody></table>';

    const html =
        '<html xmlns:o="urn:schemas-microsoft-com:office:office" ' +
        'xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">' +
        '<head><meta charset="utf-8"></head><body>' + table + '</body></html>';

    const blob = new Blob(['﻿', html], { type: 'application/vnd.ms-excel' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${frm.doc.name}_ERP_Response.xls`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
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
                const totalAmount = Number(v.orders_amount) || 0;
                const formattedTotalAmount = totalAmount.toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });

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
                                <div style="font-weight:700; color:#0b5cff; font-size:15px">${currency}${formattedTotalAmount}</div>
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
