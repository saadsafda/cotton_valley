frappe.ui.form.on('Customer', {
    refresh: function (frm) {
        $("[data-label='View']").hide();
        $("[data-label='Create']").hide();
        $("[data-label='Actions']").hide();

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
                                    if (values.portal === 'Cotton Valley') {

                                        // Open new window and set cookie
                                        // Open portal in new tab
                                        window.open(`http://156.67.27.94:3001/en/auth/erplogin?token=${token}`, "_blank");

                                    } else {
                                        window.open(`http://156.67.27.94:3002/en/auth/erplogin?token=${token}`, "_blank");
                                    }
                                } else {
                                    frappe.msgprint(__('Login failed: ' + (r.message || 'Unknown error')));
                                }
                            },
                            error: function (r) {
                                frappe.msgprint(__('Login error: ' + r.responseText));
                            }
                        });

                    },
                    __('Login Options'),
                    __('Next')
                )
            });
        }

        if (!frm.doc.disabled) {
            frm.add_custom_button(__('Send Email'), function () {
                frappe.confirm(
                    __('Are you sure you want to send email to this customer?'),
                    function () {
                        // User confirmed, proceed with sending email
                        frappe.call({
                            method: 'cotton_valley.api.api.send_customer_email',
                            args: {
                                customer: frm.doc,
                                company: frm.doc.register_company
                            },
                            callback: function (r) {
                                if (r.message && r.message.status === "success") {
                                    frappe.msgprint(__('Email sent successfully!'));
                                } else {
                                    frappe.msgprint(__('Failed to send email: ' + (r.message?.message || 'Unknown error')));
                                }
                            },
                            error: function (r) {
                                frappe.msgprint(__('Error sending email: ' + r.responseText));
                            }
                        });
                    },
                    function () {
                        // User cancelled
                        frappe.show_alert({
                            message: __('Email sending cancelled'),
                            indicator: 'orange'
                        });
                    }
                );
            });
        }

    },

    setup: function (frm) {
        frm.set_query("customer_billing_address", function (doc) {
            return {
                filters: {
                    link_doctype: "Customer",
                    link_name: doc.name,
                },
            };
        });
    },

    validate: function (frm) {
        if (frm.doc.password !== frm.doc.confirm_password) {
            frappe.throw(__('Password and Confirm Password must be the same'));
        }
    },
});
