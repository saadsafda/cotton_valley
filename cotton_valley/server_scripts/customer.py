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
def send_mass_email_btn(customer_id):
    """
    Send Mass Email to Customer using 'Mass Email Template'
    Triggered via Button on Customer Form
    """
    try:
        if not customer_id:
            frappe.throw("Customer ID is required")

        # 1. Get Customer Data
        doc = frappe.get_doc("Customer", customer_id)
        
        # 2. Get Email Address
        recipient_email = doc.email_id or doc.get('custom_email_address')
        if not recipient_email:
            frappe.msgprint(f"No email address found for customer {doc.name}", alert=True)
            return

        # 3. Setup Template Configuration
        template_name = "Mass Email Template"
        email_subject = "Welcome to Cotton Valley & UDC" # Default Subject
        email_message = ""
        cc_emails = []

        # --- FIX: Safe Name Fetching ---
        # Hum .get() use kar rahe hain taake agar field na ho to Error na aye
        # Pehle 'custom_first_name' check karega, phir 'first_name', phir 'customer_name'
        f_name = doc.get('custom_first_name') or doc.get('first_name') or doc.customer_name
        l_name = doc.get('custom_last_name') or doc.get('last_name') or ""

        # 4. Context Mapping
        context = {
            "first_name": f_name,
            "last_name": l_name,
            "email": recipient_email,
            "reset_link": "https://cottonvalley.net/my-account",
            "customer_name": doc.customer_name
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
            now=True,
            header=["", ""]
        )

        frappe.msgprint("Mass Email sent successfully!")

    except Exception as e:
        error_msg = f"Failed to send Mass Email: {str(e)}"
        frappe.log_error(f"{error_msg}\n{frappe.get_traceback()}", "Mass Email Error")
        frappe.throw(error_msg)