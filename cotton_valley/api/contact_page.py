import frappe
from cotton_valley.utils.file import get_file

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