frappe.ui.form.on('Customer', {
    refresh: function (frm) {
        $("[data-label='View']").hide();
        $("[data-label='Create']").hide();
        $("[data-label='Actions']").hide();

        frm.trigger('load_address_html');

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
                                        window.open(`https://www.cottonvalley.net/auth/erplogin?token=${token}`, "_blank");

                                    } else {
                                        window.open(`https://www.universaldc.com/auth/erplogin?token=${token}`, "_blank");
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
                                    console.log(r, "sadfasdfsa");
                                    
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

        // ============================================================
        if (!frm.is_new()) {
            frm.add_custom_button(__('Send Mass Email'), function () {
                frappe.confirm(__('Are you sure you want to send the Mass Email template?'), function () {
                    // Server API call
                    frappe.call({
                        method: 'cotton_valley.server_scripts.customer.send_mass_email_btn',
                        args: {
                            customer_id: frm.doc.name,
                            email: frm.doc.custom_email_address,
                            first_name: frm.doc.customer_name,
                            last_name: frm.doc.custom_last_name || ""
                        },
                        freeze: true,
                        freeze_message: "Sending Email...",
                        callback: function (r) {
                            if (!r.exc) {
                                frappe.msgprint(__('Email has been sent successfully!'));
                            }
                        }
                    });
                });
            });
        }
        // ============================================================

    },

    setup: function (frm) {
        frm.set_query("customer_billing_address", function (doc) {
            return {
                query: 'frappe.contacts.doctype.address.address.address_query', 
                filters: {
                    link_doctype: "Customer",
                    link_name: doc.name, 
                    address_type: "Billing"
                },
            };
        });


        frm.set_query("customer_primary_address", function (doc) {
            return {
                query: 'frappe.contacts.doctype.address.address.address_query',
                filters: {
                    link_doctype: "Customer",
                    link_name: doc.name,      
                    address_type: "Shipping"  
                }
            };
        });

        frm.set_query("custom_udc_customer_primary_address", function (doc) {
            return {
                query: 'frappe.contacts.doctype.address.address.address_query',
                filters: {
                    link_doctype: "Customer",
                    link_name: doc.name,      
                    address_type: "Shipping"  
                }
            };
        });

        frm.set_query("custom_udc_customer_billing_address", function (doc) {
            return {
                query: 'frappe.contacts.doctype.address.address.address_query',
                filters: {
                    link_doctype: "Customer",
                    link_name: doc.name,      
                    address_type: "Billing"  
                }
            };
        });
    },

    validate: function (frm) {
        if (frm.doc.password !== frm.doc.confirm_password) {
            frappe.throw(__('Password and Confirm Password must be the same'));
        }
    },

    // ============================================================
    //  ADDRESS LIST NAVIGATION FUNCTION
    // ============================================================
    load_address_html: function(frm) {
        if(frm.is_new()) return;

        // Backend se data fetch karte hain taake Preview dikha sakein (Optional, but looks good)
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Address',
                filters: [
                    ['Dynamic Link', 'link_doctype', '=', 'Customer'],
                    ['Dynamic Link', 'link_name', '=', frm.doc.name]
                ],
                fields: ['name', 'address_type', 'address_line1', 'city', 'state', 'pincode', 'country', 'company']
            },
            callback: function(r) {
                let cv_rows = "";  // Cotton Valley Rows
                let udc_rows = ""; // UDC Rows
                
                if (r.message && r.message.length > 0) {
                    r.message.forEach(function(addr) {
                        let row_html = `
                            <tr>
                                <td><a href="/app/address/${addr.name}">${addr.address_type || 'Address'}</a></td>
                                <td>${addr.address_line1 || '-'}</td>
                                <td>${addr.city || '-'}</td>
                                <td>${addr.state || '-'}</td>
                                <td>${addr.pincode || '-'}</td>

                            </tr>
                        `;
                        
                        let company_value = addr.company || addr.custom_company;
                        if (company_value === 'UDC') {
                            udc_rows += row_html;
                        } else {
                            cv_rows += row_html;
                        }
                    });
                }

                // --- 1. FUNCTION TO GENERATE HTML WITH "GO TO LIST" BUTTON ---
                function get_html_with_link(rows, type) {
                    // Button ID unique honi chahiye
                    let btn_id = type === 'UDC' ? 'btn-go-udc' : 'btn-go-cv';
                    
                    // Agar data empty hai tab bhi button dikhayein
                    let table_html = rows ? rows : `<tr><td colspan="3" class="text-muted text-center">No addresses found in preview</td></tr>`;

                    return `
                        <div style="padding: 10px; border: 1px solid #d1d8dd; background-color: #fff;">
                            
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                                <h5 style="margin: 0; font-weight: bold;">${type} Addresses</h5>
                                <button class="btn btn-xs btn-primary ${btn_id}">
                                    <i class="fa fa-external-link"></i> Open Full List
                                </button>
                            </div>

                            <table class="table table-bordered table-condensed" style="margin:0; font-size: 12px;">
                                <thead>
                                    <tr style="background-color: #f7fafc;">
                                        <th width="15%">Type</th>
                                        <th width="40%">Address</th>
                                        <th width="15%">City</th>
                                        <th width="15%">State</th>
                                        <th width="15%">Pincode</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${table_html}
                                </tbody>
                            </table>
                        </div>
                    `;
                }

                // --- 2. INJECT HTML INTO FIELDS ---

                // Cotton Valley Field
                if (frm.fields_dict['custom_customer_addresses']) {
                    let $wrapper = $(frm.fields_dict['custom_customer_addresses'].wrapper);
                    $wrapper.html(get_html_with_link(cv_rows, 'Cotton Valley'));

                    // BUTTON CLICK LOGIC (Cotton Valley)
                    $wrapper.find('.btn-go-cv').on('click', function() {
                        frappe.route_options = {
                            "link_doctype": "Customer",
                            "link_name": frm.doc.name,
                            "company": "Cotton Valley" 
                        };
                        frappe.set_route("List", "Address");
                    });
                }

                // UDC Field
                if (frm.fields_dict['custom_udc_customer_addresses']) {
                    let $wrapper = $(frm.fields_dict['custom_udc_customer_addresses'].wrapper);
                    $wrapper.html(get_html_with_link(udc_rows, 'UDC'));

                    // BUTTON CLICK LOGIC (UDC)
                    $wrapper.find('.btn-go-udc').on('click', function() {
                        frappe.route_options = {
                            "link_doctype": "Customer",
                            "link_name": frm.doc.name,
                            "company": "UDC" 
                        };
                        frappe.set_route("List", "Address");
                    });
                }
            }
        });
    },
});