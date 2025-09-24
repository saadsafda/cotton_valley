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
                                callback: function(r) {
                                    if (r.message && r.message.status === 200) {
                                        frappe.msgprint(__('Login successful! Navigating to portal...'));
                                        
                                        // Open new window and set cookie
                                        let newWindow = window.open("http://156.67.27.94:3001/", "_blank");
                                        
                                        // Wait for the window to load then set the cookie
                                        setTimeout(function() {
                                            try {
                                                // Set the UAT cookie with session ID
                                                newWindow.document.cookie = "uat=" + r.message.access_token + "; path=/; domain=156.67.27.94";
                                                // Optionally reload the page after setting cookie
                                                newWindow.location.reload();
                                            } catch (e) {
                                                console.log("Could not set cookie due to CORS policy:", e);
                                                frappe.msgprint(__('Opened portal. Please manually set token: ' + r.message.access_token));
                                            }
                                        }, 2000);
                                        
                                    } else {
                                        frappe.msgprint(__('Login failed: ' + (r.message || 'Unknown error')));
                                    }
                                },
                                error: function(r) {
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
