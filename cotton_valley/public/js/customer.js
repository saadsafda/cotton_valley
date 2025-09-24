frappe.ui.form.on('Customer', {
    refresh: function (frm) {
        $("[data-label='View']").hide();
        if (!frm.is_new()) {
            frm.add_custom_button(__('Login as Customer'), function () {
                frappe.prompt([
                    {
                        label: 'Select Portal',
                        fieldname: 'portal',
                        fieldtype: 'Select',
                        options: ['Cotton Valley', 'UDC'],
                        reqd: 1
                    }
                ],
                    function (values) {
                        if (values.portal === 'Cotton Valley') {
                            let customer_id = frm.doc.name;
                            // Make login API call
                            frappe.call({
                                method: 'cotton_valley.api.customer.sale_rep_as_customer',
                                args: {
                                    customer_id: customer_id
                                },
                                callback: function (r) {
                                    if (r.message && r.message.status === "success") {
                                        let token = r.message?.message?.access_token;
                                        frappe.msgprint(__('Login successful! Navigating to portal...'));

                                        // Open new window and set cookie
                                        // Open portal in new tab
                                        window.open(`http://156.67.27.94:3001/en/auth/erplogin?token=${token}`, "_blank");

                                    } else {
                                        frappe.msgprint(__('Login failed: ' + (r.message || 'Unknown error')));
                                    }
                                },
                                error: function (r) {
                                    frappe.msgprint(__('Login error: ' + r.responseText));
                                }
                            });

                        } else {
                            frappe.msgprint(__('UDC login flow not implemented yet.'));
                        }
                    },
                    __('Login Options'),
                    __('Next')
                )
            });
        }
    },

    validate: function (frm) {
        if (frm.doc.password !== frm.doc.confirm_password) {
            frappe.throw(__('Password and Confirm Password must be the same'));
        }
    }
});
