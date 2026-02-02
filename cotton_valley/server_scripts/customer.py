import frappe
import requests

def get_location_from_ip(doc, method):
    # Field name check: Standard 'ip_address' ya Custom 'custom_ip_address'
    # Jo field aapke Customer form me hai, wo pehle priority lega
    ip_addr = getattr(doc, 'custom_ip_address', None)
    
    # Agar IP nahi hai to function yahin rok dein
    if not ip_addr:
        return

    if doc.get('custom_country') and doc.get('custom_city'):
        return

    # API URL setup
    api_url = f"http://ip-api.com/json/{ip_addr}"

    try:
        # Request bhejein (Timeout 5 seconds rakha hai taake system hang na ho)
        response = requests.get(api_url, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data.get('status') == 'success':
            country = data.get('country', '')
            city = data.get('city', '')
            lat = data.get('lat')
            lon = data.get('lon')

            # --- Values Set Karna ---
            
            # Country aur City set karein
            if country:
                doc.custom_country = country
            if city:
                doc.custom_city = city
            
            # Lat & Long set karein (Format: "Lat, Long")
            # Check kar lein ki aapke Doctype me field ka naam 'custom_lat_long' hai ya kuch aur
            if lat and lon:
                if hasattr(doc, 'custom_lat_long'):
                    doc.custom_lat_long = f"{lat}, {lon}"
                elif hasattr(doc, 'lat_long'):
                    doc.lat_long = f"{lat}, {lon}"
                
                # Agar aapka field 'custom_latitude' aur 'custom_longitude' alag alag hain:
                if hasattr(doc, 'custom_latitude'):
                    doc.custom_latitude = lat
                if hasattr(doc, 'custom_longitude'):
                    doc.custom_longitude = lon

        else:
            # Agar API fail kare lekin crash na ho (jaise invalid IP)
            frappe.log_error(
                message=f"Message: {data.get('message')}",
                title=f"Customer IP Lookup Failed: {ip_addr}"
            )

    except Exception as e:
        # Koi technical error aaye to log karein
        frappe.log_error(
            message=frappe.get_traceback(),
            title=f"Customer IP API Error: {ip_addr}"
        )



@frappe.whitelist()
def send_mass_email_btn(customer_id, email, first_name, last_name, show_message=1):
    """
    Send Mass Email to Customer using 'Mass Email Template'
    Triggered via Button on Customer Form
    """
    try:
        if not customer_id:
            frappe.throw("Customer ID is required")

        # 2. Get Email Address
        recipient_email = email
        if not recipient_email:
            frappe.msgprint(f"No email address found for customer {customer_id}", alert=True)
            return

        # 3. Setup Template Configuration
        template_name = "Mass Email Template"
        email_subject = "Welcome to Cotton Valley & UDC" # Default Subject
        email_message = ""
        cc_emails = []

        # --- FIX: Safe Name Fetching ---
        # Hum .get() use kar rahe hain taake agar field na ho to Error na aye
        # Pehle 'custom_first_name' check karega, phir 'first_name', phir 'customer_name'
        f_name = first_name or ""
        l_name = last_name or ""

        # 4. Context Mapping
        context = {
            "first_name": f_name,
            "last_name": l_name,
            "email": recipient_email,
            "reset_link": "https://www.cottonvalley.net/auth/forgot-password",
            "customer_name": f"{f_name} {l_name}".strip()
        }

        # 5. Check if Template Exists
        if frappe.db.exists("Email Template", template_name):
            email_template = frappe.get_doc("Email Template", template_name)
            
            # Subject Render
            email_subject = frappe.render_template(email_template.subject, context)
            
            # Get CC emails
            if hasattr(email_template, 'custom_cc_email') and email_template.custom_cc_email:
                cc_emails = [row.email for row in email_template.custom_cc_email if row.email]

            # Body Render
            response_html = email_template.response_html if email_template.use_html else email_template.response
            email_message = frappe.render_template(response_html, context)
            
        else:
            # 6. Fallback HTML (Agar template delete ho jaye)
            email_message = f"""
            <!doctype html>
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <p><b>Dear {context['first_name']} {context['last_name']}</b></p>
                <p>We are thrilled to announce that <b>Cotton Valley LLC</b> and <b>Universal Distribution Center LLC</b> have launched a new website.</p>
                <p>Your Email: <b>{context['email']}</b></p>
                <p><a href="{context['reset_link']}">Click Here to Set Password</a></p>
            </body>
            </html>
            """
            frappe.log_error(f"Template '{template_name}' not found. Used fallback HTML.", "Mass Email Warning")

        # 7. Send the Email
        frappe.sendmail(
            recipients=[recipient_email],
            cc=cc_emails if cc_emails else None,
            subject=email_subject,
            message=email_message,
            reference_doctype="Customer",
            reference_name=customer_id,
            now=True
        )

        if int(show_message or 0):
            frappe.msgprint("Mass Email sent successfully!")

    except Exception as e:
        error_msg = f"Failed to send Mass Email: {str(e)}"
        frappe.log_error(f"{error_msg}\n{frappe.get_traceback()}", "Mass Email Error")
        frappe.throw(error_msg)



# send email to all customers
@frappe.whitelist()
def send_email_to_all_customers(task_id=None, publish_progress=1):
    """
    Send Mass Email to All Customers using 'Mass Email Template'
    Triggered via Button on Customer List
    """
    try:
        # 1. Get All Customers
        customers = frappe.get_all("Customer", fields=["name", "custom_email_address", "customer_name", "custom_last_name"])

        if not customers:
            frappe.msgprint("No customers found to send emails.", alert=True)
            return

        total = len(customers)
        task_id = task_id or frappe.generate_hash(length=12)
        publish_progress = int(publish_progress or 0)

        if publish_progress:
            frappe.publish_realtime(
                "mass_email_progress",
                {
                    "task_id": task_id,
                    "status": "starting",
                    "percent": 0,
                    "current": 0,
                    "total": total,
                    "sent": 0,
                    "skipped": 0,
                    "failed": 0
                },
                user=frappe.session.user
            )

        sent_count = 0
        skipped_count = 0
        failed_count = 0
        progress_interval = max(1, total // 100)

        # 2. Loop through each customer and send email
        for idx, cust in enumerate(customers):
            customer_id = cust.name
            recipient_email = cust.get('custom_email_address')
            if not recipient_email:
                frappe.log_error(f"No email address found for customer {customer_id}", "Mass Email Warning")
                skipped_count += 1
                if publish_progress and ((idx + 1) % progress_interval == 0 or idx == total - 1):
                    percent = int(((idx + 1) / total) * 100)
                    frappe.publish_realtime(
                        "mass_email_progress",
                        {
                            "task_id": task_id,
                            "status": "running",
                            "percent": percent,
                            "current": idx + 1,
                            "total": total,
                            "sent": sent_count,
                            "skipped": skipped_count,
                            "failed": failed_count,
                            "customer_id": customer_id
                        },
                        user=frappe.session.user
                    )
                continue

            # Call the existing function to send email
            try:
                send_mass_email_btn(
                    customer_id,
                    recipient_email,
                    cust.get('customer_name'),
                    cust.get('custom_last_name'),
                    show_message=0
                )
                sent_count += 1
            except Exception as e:
                failed_count += 1
                frappe.log_error(
                    f"Mass Email failed for customer {customer_id}: {str(e)}\n{frappe.get_traceback()}",
                    "Mass Email Error"
                )

            if publish_progress and ((idx + 1) % progress_interval == 0 or idx == total - 1):
                percent = int(((idx + 1) / total) * 100)
                frappe.publish_realtime(
                    "mass_email_progress",
                    {
                        "task_id": task_id,
                        "status": "running",
                        "percent": percent,
                        "current": idx + 1,
                        "total": total,
                        "sent": sent_count,
                        "skipped": skipped_count,
                        "failed": failed_count,
                        "customer_id": customer_id
                    },
                    user=frappe.session.user
                )

        if publish_progress:
            frappe.publish_realtime(
                "mass_email_progress",
                {
                    "task_id": task_id,
                    "status": "complete",
                    "percent": 100,
                    "current": total,
                    "total": total,
                    "sent": sent_count,
                    "skipped": skipped_count,
                    "failed": failed_count
                },
                user=frappe.session.user
            )

        if failed_count:
            frappe.msgprint(
                f"Mass Emails completed with {failed_count} failures and {skipped_count} skipped.",
                alert=True
            )
        else:
            frappe.msgprint("Mass Emails sent to all customers successfully!")

        return {
            "status": "success",
            "task_id": task_id,
            "total": total,
            "sent": sent_count,
            "skipped": skipped_count,
            "failed": failed_count
        }
    except Exception as e:
        error_msg = f"Failed to send Mass Emails to all customers: {str(e)}"
        frappe.log_error(f"{error_msg}\n{frappe.get_traceback()}", "Mass Email Error")
        frappe.throw(error_msg)
