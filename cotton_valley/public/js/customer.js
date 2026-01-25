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
                                        window.open(`https://cottonvalley.destrotechnologies.website/en/auth/erplogin?token=${token}`, "_blank");

                                    } else {
                                        window.open(`https://universal.destrotechnologies.website/en/auth/erplogin?token=${token}`, "_blank");
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
                            method: 'cotton_valley.api.api.send_registration_email',
                            args: {
                                customer_email: frm.doc.custom_email_address,
                                sales_person: frm.doc.sales_person,
                                firstname: frm.doc.customer_name,
                                lastname: frm.doc.custom_last_name || "",
                                company: frm.doc.register_company
                            },
                            callback: function (r) {
                                frappe.msgprint(__('Email sent successfully!'));
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



        // ===== EMAIL WITH TEMPLATE BUTTON =====
    //     if (!frm.is_new()) {
    //         frm.add_custom_button(__('Send Email with Template'), function () {
    //             frappe.db.get_list('Email Template', {
    //                 fields: ['name', 'subject'],
    //                 limit: 100
    //             }).then(templates => {
    //                 if (!templates || templates.length === 0) {
    //                     frappe.msgprint(__('No Email Templates found.'));
    //                     return;
    //                 }

    //                 let options = templates.map(t => t.name);

    //                 frappe.prompt([
    //                     {
    //                         label: 'Select Email Template',
    //                         fieldname: 'template',
    //                         fieldtype: 'Select',
    //                         options: options,
    //                         reqd: 1
    //                     }
    //                 ], function (values) {
    //                     let template_name = values.template;
    //                     let recipient = frm.doc.custom_email_address;

    //                     if (!recipient) {
    //                         frappe.msgprint(__('Customer Email not found.'));
    //                         return;
    //                     }

    //                     frappe.call({
    //                         method: 'cotton_valley.api.customer.send_registration_email',
    //                         args: {
    //                             customer_email: frm.doc.custom_email_address,
    //                             firstname: frm.doc.customer_name,
    //                             lastname: frm.doc.custom_last_name || "",
    //                             company: frm.doc.register_company,
    //                             template_name:template_name 
    //                         },
    //                         callback: function (r) {
    //                             frappe.msgprint(__('Email sent successfully to ') + frm.doc.custom_email_address);
    //                         },
    //                         error: function (r) {
    //                             frappe.msgprint(__('Error sending email: ' + r.responseText));
    //                         }
    //                     });

    //                 }, __('Select Email Template'), __('Send'));
    //             });
    //         });
    //     }

    // --- Fetch Customer Data Button ---
        if (!frm.is_new()) {
            frm.add_custom_button(__('Fetch Customer Data'), function () {
                let d = new frappe.ui.Dialog({
                    title: __('Fetch Customer Data'),
                    fields: [
                        {
                            label: 'Company',
                            fieldname: 'company',
                            fieldtype: 'Select',
                            options: ['Cotton Valley', 'UDC'],
                            reqd: 1
                        }
                    ],
                    primary_action_label: __('Fetch'),
                    primary_action(values) {
                        d.set_primary_action(__('Fetching...'), null, true);
                        frappe.call({
                            method: 'cotton_valley.api.customer.fetch_customer_data',
                            args: {
                                customer_id: frm.doc.name,
                                company: values.company
                            },
                            callback: function(r) {
                                d.hide();
                                if (r.message && r.message.status === 'success') {
                                    frappe.msgprint(__('Customer data fetched and updated successfully.'));
                                    frm.reload_doc();
                                } else {
                                    console.log(r.message, "sadfasdfsa");
                                    
                                    frappe.msgprint(__('Failed to fetch: ') + (r.message && r.message.message ? r.message.message : 'Unknown error'));
                                }
                            },
                            error: function(r) {
                                d.hide();
                                frappe.msgprint(__('Error: ') + r.message);
                            }
                        });
                    }
                });
                d.show();
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
