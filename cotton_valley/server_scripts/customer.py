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


@frappe.whitelist()
def download_customer_registration_form_pdf_html(customer=None):
    """
    Generate the Customer Registration / Credit Application form (same layout as provided PDF)
    using pure HTML (NO Jinja tags), then download as PDF.
    """
    import os
    import base64
    from frappe.utils.pdf import get_pdf
    from frappe.utils import escape_html

    # -------------------------
    # Helpers
    # -------------------------
    def img_to_data_uri(abs_path):
        if abs_path and os.path.exists(abs_path):
            with open(abs_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            ext = os.path.splitext(abs_path)[1].lower()
            mime = "png" if ext == ".png" else "jpeg" if ext in (".jpg", ".jpeg") else "webp" if ext == ".webp" else "png"
            return f"data:image/{mime};base64,{b64}"
        return ""

    def pick(doc, keys, default=""):
        if not doc:
            return default
        for k in keys:
            val = doc.get(k)
            if val:
                return val
        return default

    # -------------------------
    # Fetch Customer + Address (optional)
    # -------------------------
    cust_doc = frappe.get_doc("Customer", customer) if customer else None

    company_name = pick(cust_doc, ["company_name", "customer_name", "custom_company_name"], "")
    phone = pick(cust_doc, ["phone", "mobile_no", "custom_phone"], "")
    fax = pick(cust_doc, ["fax", "custom_fax"], "")
    email = pick(cust_doc, ["email_id", "custom_email_address"], "")

    reg_address = reg_city = reg_state = reg_zip = ""

    try:
        if customer:
            dl = frappe.get_all(
                "Dynamic Link",
                filters={
                    "link_doctype": "Customer",
                    "link_name": customer,
                    "parenttype": "Address",
                },
                fields=["parent"],
                limit=1,
            )
            if dl:
                addr = frappe.get_doc("Address", dl[0].parent)
                reg_address = addr.get("address_line1") or ""
                reg_city = addr.get("city") or ""
                reg_state = addr.get("state") or ""
                reg_zip = addr.get("pincode") or ""
    except Exception:
        pass

    business_commenced = pick(cust_doc, ["custom_business_commenced"], "")
    parent_company = pick(cust_doc, ["custom_parent_company"], "")
    primary_business_address = pick(cust_doc, ["custom_primary_business_address"], "") or reg_address
    business_city = pick(cust_doc, ["custom_business_city"], "") or reg_city
    business_state = pick(cust_doc, ["custom_business_state"], "") or reg_state
    business_zip = pick(cust_doc, ["custom_business_zip"], "") or reg_zip
    how_long_address = pick(cust_doc, ["custom_how_long_at_address"], "")
    duns = pick(cust_doc, ["custom_duns", "duns"], "")

    # -------------------------
    # Logos (optional) - place in public/files
    # -------------------------
    # sites/[site]/public/files/universal_logo.png
    # sites/[site]/public/files/cotton_valley_logo.png
    uni_logo = ""
    cv_logo = ""

    uni_site = frappe.get_site_path("public", "files", "universal.png")
    cv_site = frappe.get_site_path("public", "files", "logo.webp")

    uni_app = frappe.get_app_path("cotton_valley", "public", "files", "universal.png")
    cv_app = frappe.get_app_path("cotton_valley", "public", "files", "logo.webp")

    uni_logo = img_to_data_uri(uni_site) or img_to_data_uri(uni_app)
    cv_logo = img_to_data_uri(cv_site) or img_to_data_uri(cv_app)

    uni_img_html = f'<img src="{uni_logo}" style="width:140px; height:auto;">' if uni_logo else ""
    cv_img_html = f'<img src="{cv_logo}" style="width:160px; height:auto;">' if cv_logo else ""

    # Escape values (safe)
    company_name = escape_html(company_name or "")
    phone = escape_html(phone or "")
    fax = escape_html(fax or "")
    email = escape_html(email or "")
    reg_address = escape_html(reg_address or "")
    reg_city = escape_html(reg_city or "")
    reg_state = escape_html(reg_state or "")
    reg_zip = escape_html(reg_zip or "")

    business_commenced = escape_html(business_commenced or "")
    parent_company = escape_html(parent_company or "")
    primary_business_address = escape_html(primary_business_address or "")
    business_city = escape_html(business_city or "")
    business_state = escape_html(business_state or "")
    business_zip = escape_html(business_zip or "")
    how_long_address = escape_html(how_long_address or "")
    duns = escape_html(duns or "")

    # -------------------------
    # HTML (NO Jinja tags) - Matches your PDF layout
    # -------------------------
    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    @page {{ size: Letter; margin: 12mm; }}
    body {{ font-family: Arial, Helvetica, sans-serif; font-size: 10.5px; color:#111; }}

    .header-table {{ width:100%; border-collapse:collapse; margin-bottom: 6px; }}
    .header-table td {{ vertical-align: middle; }}
    .center-head {{ text-align:center; line-height:1.25; }}
    .center-head .l1 {{ font-size: 14px; font-weight: 400; }}
    .center-head .l2 {{ font-size: 13px; }}
    .center-head .l3 {{ font-size: 12px; }}
    .center-head .l4 {{ font-size: 12px; }}

    .form-box {{ border:1px solid #8f8f8f; }}
    .title-box {{ text-align:center; font-weight:700; padding: 10px 6px; border-bottom: 1px solid #8f8f8f; }}
    .title-box .t1 {{ font-size: 14px; }}
    .title-box .t2 {{ font-size: 13px; margin-top: 2px; }}

    .bar {{
      background:#a9c3dd;
      text-align:center;
      font-weight:700;
      padding: 4px 6px;
      border-bottom: 1px solid #8f8f8f;
    }}

    table.grid {{ width:100%; border-collapse: collapse; table-layout: fixed; }}
    table.grid td {{
      border:1px solid #8f8f8f;
      padding: 5px 6px;
      vertical-align: middle;
    }}
    .lbl {{ font-weight:700; }}
    .no-top td {{ border-top:none; }}

    .note {{
      background:#000;
      color:#ffe15a;
      font-size: 9px;
      line-height: 1.25;
      text-align:center;
      padding: 7px 10px;
      border-top: none;
      border-left:1px solid #8f8f8f;
      border-right:1px solid #8f8f8f;
      border-bottom:1px solid #8f8f8f;
    }}

    .sig td {{ height: 36px; }}
  </style>
</head>
<body>

  <!-- TOP HEADER (logos + company text) -->
  <table class="header-table">
    <tr>
      <td style="width:120px;">{uni_img_html}</td>
      <td class="center-head">
        <div class="l1">Universal distribution Center LLC</div>
        <div class="l2">Cotton Valley LLC</div>
        <div class="l3">Distribution Blvd, Edison, NJ 08817</div>
        <div class="l4">(732) 248-4276&nbsp;&nbsp;Fax: (732) 248-4279</div>
      </td>
      <td style="width:150px; text-align:right;">{cv_img_html}</td>
    </tr>
  </table>

  <div class="form-box">

    <!-- TITLE -->
    <div class="title-box">
      <div class="t1">CREDIT APPLICATION FOR A BUSINESS ACCOUNT</div>
      <div class="t2">TRADE REFERENCES</div>
    </div>

    <!-- BUSINESS CONTACT INFORMATION -->
    <div class="bar">BUSINESS CONTACT INFORMATION</div>
    <table class="grid" style="border-left:none; border-right:none;">
      <colgroup>
        <col style="width:22%;">
        <col style="width:17%;">
        <col style="width:12%;">
        <col style="width:14%;">
        <col style="width:12%;">
        <col style="width:23%;">
      </colgroup>
      <tr>
        <td class="lbl">Company name:</td>
        <td colspan="5">{company_name}</td>
      </tr>
      <tr>
        <td class="lbl">Phone:</td>
        <td>{phone}</td>
        <td class="lbl">Fax:</td>
        <td>{fax}</td>
        <td class="lbl">E-mail:</td>
        <td>{email}</td>
      </tr>
      <tr>
        <td class="lbl">Registered company address:</td>
        <td colspan="5">{reg_address}</td>
      </tr>
      <tr>
        <td class="lbl">City:</td>
        <td>{reg_city}</td>
        <td></td>
        <td class="lbl">State:</td>
        <td>{reg_state}</td>
        <td><span class="lbl">ZIP Code:</span><br>{reg_zip}</td>
      </tr>
      <tr>
        <td class="lbl">Date business commenced:</td>
        <td colspan="2">{business_commenced}</td>
        <td class="lbl" colspan="2">Parent Company names (if<br>applicable):</td>
        <td>{parent_company}</td>
      </tr>
      <tr>
        <td><span class="lbl">Sole proprietorship:</span></td>
        <td><span class="lbl">Partnership:</span></td>
        <td colspan="2"><span class="lbl">Corporation:</span></td>
        <td colspan="2"><span class="lbl">Other:</span></td>
      </tr>
    </table>

    <!-- BUSINESS AND CREDIT INFORMATION -->
    <div class="bar">BUSINESS&nbsp;&nbsp;AND&nbsp;&nbsp;CREDIT&nbsp;&nbsp;INFORMATION</div>
    <table class="grid" style="border-left:none; border-right:none;">
      <colgroup>
        <col style="width:22%;">
        <col style="width:17%;">
        <col style="width:12%;">
        <col style="width:14%;">
        <col style="width:12%;">
        <col style="width:23%;">
      </colgroup>
      <tr>
        <td class="lbl">Primary business address:</td>
        <td colspan="5">{primary_business_address}</td>
      </tr>
      <tr>
        <td class="lbl">City:</td>
        <td>{business_city}</td>
        <td></td>
        <td class="lbl">State:</td>
        <td>{business_state}</td>
        <td><span class="lbl">ZIP Code:</span><br>{business_zip}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="3">How long at current address?&nbsp;&nbsp;{how_long_address}</td>
        <td class="lbl" colspan="3">DUNS #:&nbsp;&nbsp;{duns}</td>
      </tr>
      <tr>
        <td class="lbl">Telephone:</td>
        <td>{phone}</td>
        <td class="lbl">Fax:</td>
        <td>{fax}</td>
        <td class="lbl">E-mail:</td>
        <td>{email}</td>
      </tr>
    </table>

    <!-- BANK REFERENCE -->
    <div class="bar">BANK&nbsp;&nbsp;REFERENCE</div>
    <table class="grid" style="border-left:none; border-right:none;">
      <colgroup>
        <col style="width:25%;">
        <col style="width:35%;">
        <col style="width:15%;">
        <col style="width:25%;">
      </colgroup>
      <tr>
        <td class="lbl">Bank name:</td>
        <td colspan="3"></td>
      </tr>
      <tr>
        <td class="lbl">Bank address:</td>
        <td></td>
        <td class="lbl">Phone:</td>
        <td></td>
      </tr>
      <tr>
        <td class="lbl">City:</td>
        <td></td>
        <td class="lbl">Fax:</td>
        <td></td>
      </tr>
      <tr>
        <td class="lbl">State:</td>
        <td></td>
        <td class="lbl">ZIP Code:</td>
        <td></td>
      </tr>
      <tr>
        <td class="lbl">E-mail:</td>
        <td colspan="3"></td>
      </tr>
      <tr>
        <td class="lbl">Type of account</td>
        <td>Savings</td>
        <td>Checking</td>
        <td>Other</td>
      </tr>
      <tr>
        <td class="lbl">Account number:</td>
        <td colspan="3"></td>
      </tr>
    </table>

    <!-- BUSINESS/TRADE REFERENCES -->
    <div class="bar">BUSINESS/TRADE&nbsp;&nbsp;REFERENCES</div>
    <table class="grid" style="border-left:none; border-right:none;">
      <colgroup>
        <col style="width:22%;">
        <col style="width:17%;">
        <col style="width:12%;">
        <col style="width:14%;">
        <col style="width:12%;">
        <col style="width:23%;">
      </colgroup>

      <!-- Reference 1 -->
      <tr><td class="lbl">Company name:</td><td colspan="5"></td></tr>
      <tr><td class="lbl">Address:</td><td colspan="5"></td></tr>
      <tr>
        <td class="lbl">City:</td><td></td><td></td>
        <td class="lbl">State:</td><td></td>
        <td class="lbl">ZIP Code:</td>
      </tr>
      <tr>
        <td class="lbl">Phone:</td><td></td>
        <td class="lbl">Fax:</td><td></td>
        <td class="lbl">E-mail:</td><td></td>
      </tr>
      <tr><td class="lbl">Type of account:</td><td colspan="5"></td></tr>

      <!-- Reference 2 -->
      <tr><td class="lbl">Company name:</td><td colspan="5"></td></tr>
      <tr><td class="lbl">Address:</td><td colspan="5"></td></tr>
      <tr>
        <td class="lbl">City:</td><td></td><td></td>
        <td class="lbl">State:</td><td></td>
        <td class="lbl">ZIP Code:</td>
      </tr>
      <tr>
        <td class="lbl">Phone:</td><td></td>
        <td class="lbl">Fax:</td><td></td>
        <td class="lbl">E-mail:</td><td></td>
      </tr>
      <tr><td class="lbl">Type of account:</td><td colspan="5"></td></tr>

      <!-- Reference 3 -->
      <tr><td class="lbl">Company name:</td><td colspan="5"></td></tr>
      <tr><td class="lbl">Address:</td><td colspan="5"></td></tr>
      <tr>
        <td class="lbl">City:</td><td></td><td></td>
        <td class="lbl">State:</td><td></td>
        <td class="lbl">ZIP Code:</td>
      </tr>
      <tr>
        <td class="lbl">Phone:</td><td></td>
        <td class="lbl">Fax:</td><td></td>
        <td class="lbl">E-mail:</td><td></td>
      </tr>
      <tr><td class="lbl">Type of account:</td><td colspan="5"></td></tr>
    </table>

    <!-- Note (black/yellow) -->
    <div class="note">
      The signature below represents and warrants that (a) the party signing below is an authorized representative
      of the company; and (b) that the information provided herein is a complete and accurate representation of the
      company's financial situation as of the date hereof. By signing this form, I expressly authorize Universal /
      Cotton Valley to contact the above references to determine credit worthiness
    </div>

    <!-- Signature row -->
    <table class="grid sig" style="border-left:none; border-right:none; border-top:none;">
      <colgroup>
        <col style="width:30%;">
        <col style="width:25%;">
        <col style="width:8%;">
        <col style="width:15%;">
        <col style="width:8%;">
        <col style="width:14%;">
      </colgroup>
      <tr>
        <td class="lbl">SIGNATURE</td>
        <td class="lbl">NAME:</td>
        <td class="lbl">TITLE:</td>
        <td></td>
        <td class="lbl">DATE:</td>
        <td></td>
      </tr>
    </table>

  </div>
</body>
</html>
"""

    try:
        pdf = get_pdf(html)
        frappe.local.response["filename"] = "Customer registration Form.pdf"
        frappe.local.response["filecontent"] = pdf
        frappe.local.response["type"] = "download"
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Customer Registration PDF (HTML) Error")
        frappe.throw("PDF generate nahi ho raha. Please confirm wkhtmltopdf installed/configured.")
