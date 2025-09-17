import frappe
from cotton_valley.api.website_theme_setting import get_file

@frappe.whitelist(allow_guest=True)
def get_contact_page():
    try:
        about_page = frappe.get_single("Contact Page")
        
        return {
            "status": "success",
            "data": {
                "title": about_page.title,
                "banner_image": get_file(about_page.page_banner),
                "phone": about_page.phone,
                "email": about_page.email,
                "location_title": about_page.location_title,
                "location_address": about_page.location_address,
                "office_title": about_page.office_title,
                "office_address": about_page.office_address,
            }
        }
    except Exception as e:
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}
    
@frappe.whitelist(allow_guest=True)
def submit_contact_form(name, email, phone, subject, message):
    try:
        contact_form = frappe.get_doc({
            "doctype": "Contact",
            "first_name": name,
            "email_id": email,
            "status": "Open",
            "phone": phone,
            "custom_subject": subject,
            "custom_message": message
        })
        contact_form.append("email_ids", {"email_id": email, "is_primary": 1})
        contact_form.insert(ignore_permissions=True)
        return {"status": "success", "message": "Contact form submitted successfully."}
    except Exception as e:
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}