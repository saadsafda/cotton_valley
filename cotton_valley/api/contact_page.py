import frappe
from cotton_valley.api.website_theme_setting import get_file

@frappe.whitelist(allow_guest=True)
def get_contact_page(company=None):
    try:
        doctype = "Contact Page"
        company = "Cotton Valley" if not company or company == "null" else company
        if company == "UDC":
            doctype = f"UDC Contact Page"
        contact = frappe.get_single(doctype)
        
        return {
            "status": "success",
            "data": {
                "title": contact.title,
                "banner_image": get_file(contact.page_banner),
                "phone": contact.phone,
                "email": contact.email,
                "location_title": contact.location_title,
                "location_address": contact.location_address,
                "office_title": contact.office_title,
                "office_address": contact.office_address,
            }
        }
    except Exception as e:
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}
    
@frappe.whitelist(allow_guest=True)
def submit_contact_form(name, email, phone, subject, message, company=None):
    try:
        company = "Cotton Valley" if not company or company == "null" else company
        contact_form = frappe.get_doc({
            "doctype": "Contact",
            "first_name": name,
            "email_id": email,
            "status": "Open",
            "phone": phone,
            "custom_subject": subject,
            "custom_message": message,
            "company": company
        })
        contact_form.append("email_ids", {"email_id": email, "is_primary": 1})
        contact_form.insert(ignore_permissions=True)
        return {"status": "success", "message": "Contact form submitted successfully."}
    except Exception as e:
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}