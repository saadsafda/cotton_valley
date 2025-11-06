import frappe

def update_customer_order_summary(doc, method):
    if not doc.customer:
        return

    # Get all submitted sales orders of this customer
    sales_orders = frappe.get_all(
        "Sales Order",
        filters={"customer": doc.customer, "docstatus": 1},
        fields=["grand_total", "transaction_date"]
    )

    total_orders = len(sales_orders)
    total_amount = sum([so.grand_total for so in sales_orders])

    # doc.total_orders = total_orders
    # doc.total_order_amount = total_amount
    doc.custom_last_order_date = max((so.transaction_date for so in sales_orders), default=None)
    
    # Update Customer fields
    frappe.db.set_value("Customer", doc.customer, {
        "no_of_orders": total_orders,
        "orders_amount": total_amount,
        "last_order_date": doc.custom_last_order_date
    })

    frappe.db.commit()

    make_delivery_note_on_submit(doc, method)
    send_sales_order_confirmation_email(doc, method)

@frappe.whitelist()
def send_sales_order_confirmation_email(doc, method):
    """
    Send email notification to customer and sales person when sales order is submitted.
    Uses Email Template for easy updates from ERPNext UI.
    """
    try:
        # Get customer email
        customer_email = frappe.db.get_value("Customer", doc.customer, "custom_email_address")
        
        # Get sales person email
        sales_person_email = None
        sales_person = None
        if doc.custom_customer_sales_representative:
            sales_person = frappe.get_doc("Sales Person", doc.custom_customer_sales_representative)
            if sales_person.employee:
                sales_person_email = frappe.db.get_value("Employee", sales_person.employee, "user_id")
        
        recipients = []
        if customer_email:
            recipients.append(customer_email)
        if sales_person_email:
            recipients.append(sales_person_email)
        
        if not recipients:
            frappe.log_error("No recipients found for Sales Order confirmation email", "Sales Order Email")
            return
        
        # Try to get Email Template
        try:
            template_name = ""
            if doc.company == "Cotton Valley":
                template_name = "New Orders Message -CVL"
            else:
                template_name = "New Orders Message -UDC"

            if not frappe.db.exists("Email Template", template_name):
                raise frappe.DoesNotExistError

            email_template = frappe.get_doc("Email Template", template_name)

            # Collect CC emails from template child table `custom_cc_email` (if any)
            cc_emails = []
            if email_template.custom_cc_email:
                cc_emails = [row.email for row in email_template.custom_cc_email if row.email]

            # Prepare template arguments
            template_args = {
                "firstname": frappe.db.get_value("Customer", doc.customer, "customer_name"),
                "lastname": frappe.db.get_value("Customer", doc.customer, "custom_last_name"),
                "order": doc.name,
                "salesRepName": doc.custom_customer_sales_representative,
                "salesRepPhone": frappe.db.get_value("Employee", sales_person.employee, "cell_number") if doc.custom_customer_sales_representative else None,
                "salesRepEmail": sales_person_email,
                "paymentmethod": doc.custom_mode_of_payment,
                "company": doc.company,
                "address1": doc.billing_address_details,
                "state": doc.state or "",
                "zip": doc.zip_code or "",
                "country": doc.country or "",
                "shipAddress1": doc.shipping_address_details or "",
                "shipState": doc.shipping_state or "",
                "shipZip": doc.shipping_zip_code or "",
                "shipCountry": doc.shipping_country or "",
                "shipPhone": doc.shipping_phone or "",
                "ordersubtotal": doc.total or 0,
                "grandtotal": doc.grand_total,
                "currency": doc.currency,
                "items": doc.items,
            }
            
            # Render template
            subject = frappe.render_template(email_template.subject, template_args)
            response = email_template.response_html if email_template.use_html else email_template.response
            message = frappe.render_template(response, template_args)

        except frappe.DoesNotExistError:
            # Fallback to default message if template doesn't exist
            frappe.log_error("Email Template 'Sales Order Confirmation' not found. Using default message.", "Sales Order Email Template Missing")
            
            subject = f"Order Confirmation - {doc.name}"
            message = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #333;">Order Confirmation</h2>
                <p>Dear Customer,</p>
                <p>Your order <strong>{doc.name}</strong> has been confirmed.</p>
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Order Number:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{doc.name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Order Date:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{doc.transaction_date}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Total Amount:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{doc.currency} {doc.grand_total}</td>
                    </tr>
                </table>
                <p>Thank you for your business!</p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                <p style="color: #666; font-size: 12px;">This is an automated message, please do not reply to this email.</p>
            </div>
            """
        
        # Send email (include CC if present)
        frappe.sendmail(
            recipients=recipients,
            cc=cc_emails if cc_emails else None,
            subject=subject,
            message=message,
            now=True
        )

        frappe.log_error("Sales Order Email Sent", f"Sales Order confirmation email sent to: {', '.join(recipients)}")
        
    except Exception as e:
        frappe.log_error("Sales Order Confirmation Email Error", frappe.get_traceback())


def make_delivery_note_on_submit(doc, method):
    try:
        dn = frappe.new_doc("Delivery Note")
        dn.customer = doc.customer
        dn.company = doc.company
        dn.posting_date = frappe.utils.nowdate()
        dn.set_warehouse = doc.set_warehouse or None

        for item in doc.items:
            dn.append("items", {
                "item_code": item.item_code,
                "qty": item.qty,
                "rate": item.rate,
                "against_sales_order": doc.name,
                "so_detail": item.name,
                "warehouse": item.warehouse,
            })

        dn.save(ignore_permissions=True)
        dn.submit()
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Auto Delivery Note Creation Failed")


@frappe.whitelist()
def send_abandoned_cart_emails():
    """
    Scheduled task to email customers who have Sales Orders in Draft (docstatus=0).
    Sends emails for orders created between 48 and 24 hours ago (one-time window per order)
    using the Email Template 'Abandoned Cart -CVL' (or company-specific variant).
    """
    try:
        from datetime import timedelta
        from frappe.utils import now_datetime

        now = now_datetime()
        # start = (now - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
        creation = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

        sales_orders = frappe.get_all(
            "Sales Order",
            filters=[
                ["Sales Order", "docstatus", "=", 0],
                ["Sales Order", "creation", ">=", creation],
            ],
            fields=["name", "customer", "company", "items", "grand_total", "currency", "creation"]
        )

        if not sales_orders:
            return

        for so in sales_orders:
            try:
                if not so.customer:
                    continue

                customer_email = frappe.db.get_value("Customer", so.customer, "custom_email_address")
                if not customer_email:
                    continue

                # choose template based on company
                template_name = "Abandoned Cart -CVL" if so.company == "Cotton Valley" else "Abandoned Cart -UDC"

                if not frappe.db.exists("Email Template", template_name):
                    # skip if template missing
                    frappe.log_error(f"Email Template {template_name} not found", "Abandoned Cart Email")
                    continue

                email_template = frappe.get_doc("Email Template", template_name)

                # Collect CC emails from template child table `custom_cc_email` (if any)
                cc_emails = []
                if getattr(email_template, 'custom_cc_email', None):
                    cc_emails = [row.email for row in email_template.custom_cc_email if getattr(row, 'email', None)]

                items = frappe.get_all(
                    "Sales Order Item",
                    filters=[
                        ["Sales Order Item", "parent", "=", so.name],
                    ],
                    fields=["name", "item_name", "item_code", "description", "image"]
                )

                # prepare template args
                template_args = {
                    "firstname": frappe.db.get_value("Customer", so.customer, "customer_name"),
                    "lastname": frappe.db.get_value("Customer", so.customer, "custom_last_name"),
                    "order": so.name,
                    "company": so.company,
                    "ordersubtotal": so.get('grand_total') or 0,
                    "grand_total": so.get('grand_total'),
                    "currency": so.get('currency'),
                    "items": items or [],
                    "creation": so.creation,
                }

                subject = frappe.render_template(email_template.subject, template_args)
                response = email_template.response_html if email_template.use_html else email_template.response
                message = frappe.render_template(response, template_args)

                frappe.sendmail(
                    recipients=[customer_email],
                    cc=cc_emails if cc_emails else None,
                    subject=subject,
                    message=message,
                    now=True
                )

                frappe.log_error(f"Abandoned cart email sent for {so.name} to {customer_email}", "Abandoned Cart Email Sent")

            except Exception:
                frappe.log_error(frappe.get_traceback(), "Abandoned Cart Email Error")

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Abandoned Cart Scheduler Failed")
