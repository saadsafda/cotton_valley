import os
import mimetypes
import frappe
from frappe import _
from io import BytesIO
import json

from cotton_valley.api.sales_order import push_to_erp
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.drawing.image import Image as XLImage
from PIL import Image as PILImage

mimetypes.add_type("image/webp", ".webp")

def increase_stock_on_cancel(doc, method):
    """
    Increase threshold_stock back when Sales Order is cancelled.
    This restores the reserved stock.
    """
    def to_int(value, default=0):
        """Coerce numeric-like values to int, fallback to default on errors."""
        if value is None:
            return default
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    try:
        for item in doc.items:
            current_available = to_int(frappe.db.get_value("Item", item.item_code, "available_stock"))
            qty = to_int(item.qty)
            new_available = current_available + qty
            frappe.db.set_value("Item", item.item_code, "available_stock", new_available)
            current_threshold = to_int(frappe.db.get_value("Item", item.item_code, "threshold_stock"))
            available_stock = to_int(frappe.db.get_value("Item", item.item_code, "available_stock"))
            # Don't exceed available stock
            new_threshold = min(available_stock, current_threshold + qty)
            frappe.db.set_value("Item", item.item_code, "threshold_stock", new_threshold)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error("Threshold Stock Error", f"Error increasing threshold stock: {str(e)}")


def order_cancel(doc, method):
    if not doc.cancellation_reason:
        frappe.throw(_("Please enter a value in the *Cancellation Reason* field before cancelling this Sales Order."))
    cancel_delivery_note(doc, method)

def cancel_delivery_note(doc, method):
    try:
        dn_exists = frappe.db.exists("Delivery Note", {"against_sales_order": doc.name, "docstatus": 1})
        if not dn_exists:
            return
        delivery_notes = frappe.get_all(
            "Delivery Note",
            filters={"against_sales_order": doc.name, "docstatus": 1},
            fields=["name"]
        )

        for dn in delivery_notes:
            dn_doc = frappe.get_doc("Delivery Note", dn.name)
            dn_doc.cancel()
        
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Auto Delivery Note Cancellation Failed")


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

    # make_delivery_note_on_submit(doc, method)
    decrease_stock(doc, method)
    send_sales_order_confirmation_email(doc, method)
    notify_customer_on_status_change(doc, method)

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
                "state": doc.state or "",
                "zip": doc.zip_code or "",
                "country": doc.country or "",
                "billAddress": doc.billing_address_details,
                "city": doc.billing_city or "",
                "phone": doc.custom_billing_phone or "",
                "email": doc.custom_customer_email or "",
                "shipAddress": doc.shipping_address_details or "",
                "shipCity": doc.shipping_city or "",
                "shipState": doc.shipping_state or "",
                "shipZip": doc.shipping_zip_code or "",
                "shipCountry": doc.shipping_country or "",
                "shipPhone": doc.shipping_phone or "",
                "ordersubtotal": doc.total or 0,
                "grandtotal": doc.grand_total,
                "currency": doc.currency,
                "items": doc.items,
                "specialinstructions": doc.custom_notes or "",
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
        
        sender = "order@cottonvalley.net" if doc.company == "Cotton Valley" else "order@universaldc.com"
        # Send the email with CC
        frappe.sendmail(
            sender=sender,
            recipients=recipients,
            cc=cc_emails if cc_emails else None,
            subject=subject,
            message=message,
            now=True
        )

        frappe.log_error("Sales Order Email Sent", f"Sales Order confirmation email sent to: {', '.join(recipients)}")
        
    except Exception as e:
        frappe.log_error("Sales Order Confirmation Email Error", frappe.get_traceback())



def decrease_stock(doc, method):
    """
    Decrease threshold_stock for each item when Sales Order is submitted.
    This reserves stock for website display.
    """
    def to_int(value, default=0):
        """Coerce numeric-like values to int, fallback to default on errors."""
        if value is None:
            return default
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    try:
        for item in doc.items:
            current_available = to_int(frappe.db.get_value("Item", item.item_code, "available_stock"))
            qty = to_int(item.qty)
            new_available = max(0, current_available - qty)  # Don't go below 0
            frappe.db.set_value("Item", item.item_code, "available_stock", new_available)
            current_threshold = to_int(frappe.db.get_value("Item", item.item_code, "threshold_stock"))
            new_threshold = max(0, current_threshold - qty)  # Don't go below 0
            frappe.db.set_value("Item", item.item_code, "threshold_stock", new_threshold)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error("Threshold Stock Error", f"Error decreasing threshold stock: {str(e)}")


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

                sender = "order@cottonvalley.net" if so.company == "Cotton Valley" else "order@universaldc.com"
                # Send the email with CC
                frappe.sendmail(
                    sender=sender,
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



def notify_customer_on_status_change(doc, method):


    # 1. Validation: Ensure there is a customer
    if not doc.customer:
        return

    # 2. Get the previous state
    doc_before_save = doc.get_doc_before_save()
    
    # USE YOUR CUSTOM FIELD: order_status
    previous_status = doc_before_save.order_status if doc_before_save else None
    current_status = doc.order_status

    # 3. Only proceed if the order_status has actually changed
    # if current_status == previous_status:
    #     return

    message = None
    
    # 4. Define HTML Messages based on order_status
    if current_status == "Pending":
        message = f"Your order #{doc.name} has been updated and current order status is in Pending. Thank you for your patience!"
        
    elif current_status == "Processing":
       message = f"Your order #{doc.name} has been updated and current order status is in Processing. Thank you for your patience!"
        
    elif current_status == "Shipped":
       message = f"Your order has been successfully placed. Order ID: #{doc.name}. Thank you for choosing us."

    # 5. Update the Customer Record
    if message:
        try:
            customer_doc = frappe.get_doc("Customer", doc.customer)
            
            # --- FIELD MAPPING ---
            # 'custom_notifications': This is the TABLE name in Customer. 
            # (If your table field is named just 'notifications', change it below!)
            
            customer_doc.append("custom_notifications", {
                "message": message,                  # HTML Field
                "date_and_time": frappe.utils.now()  # Datetime Field (Updated)
            })
            
            customer_doc.save(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Error updating customer notification: {str(e)}", "Sales Order Notification Script")


def on_update_after_submit(doc, method):
    """Server Script hook: run after a submitted Sales Order is updated."""
    notify_customer_on_status_change(doc, method)
    push_to_erp([doc.name])



@frappe.whitelist()
def download_sales_order_excel(sales_order):
    doc = frappe.get_doc("Sales Order", sales_order)

    wb = Workbook()
    ws = wb.active
    ws.title = "Sales Order"

    bold = Font(bold=True)
    title_font = Font(bold=True, size=14)
    head_font = Font(bold=True, size=12)

    left = Alignment(horizontal="left", vertical="top", wrap_text=True)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    right = Alignment(horizontal="right", vertical="top", wrap_text=True)

    thin = Side(style="thin", color="999999")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def put(r, c, v, f=None, a=None, b=None):
        cell = ws.cell(row=r, column=c, value=v)
        if f:
            cell.font = f
        if a:
            cell.alignment = a
        if b:
            cell.border = b
        return cell

    # =========================
    # HEADER
    # =========================
    r = 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
    put(r, 1, (doc.company or "Company"), title_font, center)
    r += 1

    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
    put(r, 1, doc.doctype, head_font, center)
    r += 2

    put(r, 1, "Billing Information:", bold, left)
    put(r, 4, "Shipping Information:", bold, left)
    put(r, 8, "Order #", bold, left)
    put(r, 9, doc.name, bold, left)
    r += 1

    billing_lines = []
    if doc.get("customer_address"):
        a = frappe.get_doc("Address", doc.customer_address)
        billing_lines = [
            a.get("address_title") or "",
            a.get("address_line1") or "",
            a.get("address_line2") or "",
            " ".join([x for x in [a.get("city"), a.get("state"), a.get("pincode")] if x]),
            a.get("country") or "",
            f"Phone: {a.get('phone')}" if a.get("phone") else "",
        ]
        mobile = a.get("mobile_no") or a.get("mobile") or a.get("mobile_number")
        if mobile:
            billing_lines.append(f"Mobile: {mobile}")

    shipping_lines = []
    if doc.get("shipping_address_name"):
        s = frappe.get_doc("Address", doc.shipping_address_name)
        shipping_lines = [
            s.get("address_title") or "",
            s.get("address_line1") or "",
            s.get("address_line2") or "",
            " ".join([x for x in [s.get("city"), s.get("state"), s.get("pincode")] if x]),
            s.get("country") or "",
            f"Phone: {s.get('phone')}" if s.get("phone") else "",
        ]
        mobile = s.get("mobile_no") or s.get("mobile") or s.get("mobile_number")
        if mobile:
            shipping_lines.append(f"Mobile: {mobile}")

    sales_rep_name = doc.sales_team[0].sales_person if doc.get("sales_team") else ""

    sales_rep_email = ""
    sales_rep_phone = ""
    if sales_rep_name:
        emp_name = frappe.db.get_value("Employee", {"employee_name": sales_rep_name}, "name")
        if emp_name:
            emp = frappe.get_doc("Employee", emp_name)
            sales_rep_email = emp.get("user_id") or emp.get("company_email") or emp.get("personal_email") or ""
            sales_rep_phone = emp.get("mobile") or emp.get("cell_number") or emp.get("phone_number") or ""

    # ✅ Processed By: always sales rep (avoid Guest)
    processed_by = sales_rep_name or "—"

    account_no = (
        doc.get("customer_account_number")
        or doc.get("account_no")
        or doc.get("customer_account")
        or "—"
    )

    order_date = str(doc.transaction_date or doc.posting_date or "")

    meta_rows = [
        ("Order Date", order_date),
        ("Sales Rep", sales_rep_name or "—"),
        ("Sales Rep Phone", sales_rep_phone or "—"),
        ("Sales Rep Email", sales_rep_email or "—"),
        ("Processed By", processed_by or "—"),
        ("Account #", account_no or "—"),
        ("Status", doc.status or "—"),
        ("Order Type", doc.get("order_type") or "—"),
    ]

    max_lines = max(len(billing_lines), len(shipping_lines), len(meta_rows))
    for i in range(max_lines):
        btxt = billing_lines[i] if i < len(billing_lines) else ""
        ws.merge_cells(start_row=r + i, start_column=1, end_row=r + i, end_column=3)
        put(r + i, 1, btxt, None, Alignment(horizontal="left", vertical="center", wrap_text=True))

        stxt = shipping_lines[i] if i < len(shipping_lines) else ""
        ws.merge_cells(start_row=r + i, start_column=4, end_row=r + i, end_column=7)
        put(r + i, 4, stxt, None, Alignment(horizontal="left", vertical="center", wrap_text=True))

        if i < len(meta_rows):
            put(r + i, 8, meta_rows[i][0], bold, Alignment(horizontal="left", vertical="center", wrap_text=True))
            put(r + i, 9, meta_rows[i][1], None, Alignment(horizontal="left", vertical="center", wrap_text=True))
        else:
            put(r + i, 8, "", None, Alignment(horizontal="left", vertical="center", wrap_text=True))
            put(r + i, 9, "", None, Alignment(horizontal="left", vertical="center", wrap_text=True))

    r += max_lines + 1

    # ✅ Customer email from Customer doctype field: custom_customer_email
    customer_email = doc.get("custom_customer_email") or ""
    put(r, 1, "Email Address:", bold, Alignment(horizontal="left", vertical="center", wrap_text=True))
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
    put(r, 2, customer_email, None, Alignment(horizontal="left", vertical="center", wrap_text=True))
    r += 2

    # =========================
    # ITEMS TABLE (✅ Image column)
    # =========================
    headers = ["Line#", "SKU", "Image", "Item Name", "Case Pack", "Qty", "UOM", "Rate", "Amount"]
    for i, h in enumerate(headers, start=1):
        put(r, i, h, bold, center, border)
    r += 1

    def resolve_image_path(image_url: str):
        """Return local path for /files/ or /private/files/ urls. Otherwise None."""
        if not image_url:
            return None
        if image_url.startswith("http://") or image_url.startswith("https://"):
            return None  # skip external
        if image_url.startswith("/private/files/"):
            return frappe.get_site_path(image_url.lstrip("/"))
        if image_url.startswith("/files/"):
            return frappe.get_site_path("public", image_url.lstrip("/"))
        if image_url.startswith("files/"):
            return frappe.get_site_path("public", image_url)
        if image_url.startswith("private/files/"):
            return frappe.get_site_path(image_url)
        return None

    def convert_webp_to_png(webp_path: str):
        """Convert .webp to .png in /tmp and return png path."""
        if not webp_path:
            return None
        ext = os.path.splitext(webp_path)[1].lower()
        if ext != ".webp":
            return webp_path

        base = os.path.splitext(os.path.basename(webp_path))[0]
        png_path = f"/tmp/{base}.png"

        im = PILImage.open(webp_path).convert("RGBA")
        im.save(png_path, "PNG")
        return png_path

    line_no = 1
    for it in doc.items:
        case_pack = it.get("custom_case_pack") or ""

        # Row height for image
        ws.row_dimensions[r].height = 55

        row_values = [
            line_no,
            it.item_code or "",
            "",  # Image inserted
            it.item_name or "",
            case_pack,
            float(it.qty or 0),
            it.uom or "",
            float(it.rate or 0),
            float(it.amount or 0),
        ]

        for c, v in enumerate(row_values, start=1):
            align = center  # Center align all columns by default
            put(r, c, v, None, align, border)

        # ✅ Insert image into column C (webp safe) - centered in cell
        img_path = resolve_image_path(it.get("image"))
        if img_path and os.path.exists(img_path):
            try:
                img_path = convert_webp_to_png(img_path)  # ✅ FIX
                xl_img = XLImage(img_path)
                xl_img.width = 45
                xl_img.height = 45
                
                # Center image in cell - calculate pixel offsets
                # Column C width is 12 (~84 pixels), Row height is 55 pixels
                col_width_px = 84
                row_height_px = 55
                img_width = 45
                img_height = 45
                
                # Calculate offset to center
                x_offset_px = (col_width_px - img_width) // 2
                y_offset_px = (row_height_px - img_height) // 2
                
                # Convert to EMUs (914400 EMUs per inch, ~9525 EMUs per pixel)
                x_offset_emu = x_offset_px * 9525
                y_offset_emu = y_offset_px * 9525
                
                from openpyxl.drawing.spreadsheet_drawing import OneCellAnchor, AnchorMarker
                from openpyxl.drawing.xdr import XDRPositiveSize2D
                from openpyxl.utils.units import pixels_to_EMU
                
                # Column C is index 2 (0-based), row is r-1 (0-based)
                marker = AnchorMarker(col=2, colOff=x_offset_emu, row=r-1, rowOff=y_offset_emu)
                size = XDRPositiveSize2D(pixels_to_EMU(img_width), pixels_to_EMU(img_height))
                xl_img.anchor = OneCellAnchor(_from=marker, ext=size)
                ws.add_image(xl_img)
            except Exception:
                # Fallback to simple placement
                try:
                    ws.add_image(xl_img, f"C{r}")
                except:
                    pass

        r += 1
        line_no += 1

    r += 1

    # =========================
    # Totals
    # =========================
    put(r, 8, "Subtotal", bold, right)
    put(r, 9, float(doc.total or 0), None, right)
    r += 1

    put(r, 8, "Tax", bold, right)
    put(r, 9, float(doc.total_taxes_and_charges or 0), None, right)
    r += 1

    put(r, 8, "Grand Total", bold, right)
    put(r, 9, float(doc.grand_total or 0), bold, right)

    # Column widths
    widths = [18, 18, 14, 40, 14, 12, 12, 18, 24]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    bio = BytesIO()
    wb.save(bio)

    frappe.response["filename"] = f"{doc.name}.xlsx"
    frappe.response["filecontent"] = bio.getvalue()
    frappe.response["type"] = "binary"



@frappe.whitelist()
def restore_items_from_history(doc_name):
    doc = frappe.get_doc("Sales Order", doc_name)
    current_item_names = [row.name for row in doc.items]
    
    # 2. Fetch the last 15 version logs to increase chances of finding the data
    versions = frappe.get_all("Version", 
        filters={
            "ref_doctype": "Sales Order", 
            "docname": doc_name
        }, 
        fields=["data", "creation"],
        order_by="creation desc", 
        limit=15
    )

    if not versions:
        return {"status": "failed", "message": "No version history found."}

    restored_count = 0
    
    # 3. Iterate through history
    for v in versions:
        if not v.data:
            continue
            
        try:
            version_data = json.loads(v.data)
        except Exception:
            continue
        # Check for removed items
        if "removed" in version_data and version_data["removed"]:
            for removed_item in version_data["removed"]:
                
                # Safety Check: We need at least 2 elements: [Doctype, Name, DataDict]
                if len(removed_item) < 2:
                    continue

                rd_doctype = removed_item[0]
                rd_name = removed_item[1]
                rd_data = removed_item[1]  # Fixed: get the data dict from index 2
                
                # Verify it is a Sales Order Item and NOT already in the table
                if rd_doctype == "items" and rd_name not in current_item_names:
                    
                    # Additional check: Avoid duplicate item codes
                    if isinstance(rd_data, dict):
                        item_code = rd_data.get("item_code")
                        existing_item_codes = [row.item_code for row in doc.items]
                        
                        # Skip if this item_code is already in the order
                        if item_code and item_code in existing_item_codes:
                            continue
                    
                    # Create a new row
                    new_row = doc.append("items", {})
                    
                    # Restore data
                    for key, value in rd_data.items():
                        # Skip system fields
                        if key not in ["name", "parent", "parentfield", "parenttype", "creation", "modified", "docstatus"]:
                            new_row.set(key, value)
                    
                    # Track that we restored this ID so we don't duplicate
                    current_item_names.append(rd_name) 
                    restored_count += 1

    # 4. Save and Return
    if restored_count > 0:
        doc.save()
        return {"status": "success", "message": f"Restored {restored_count} item(s) from history."}
    else:
        return {"status": "empty", "message": "No valid deleted item data found in recent history."}