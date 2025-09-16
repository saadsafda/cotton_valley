import frappe
from cotton_valley.api.website_theme_setting import get_file

@frappe.whitelist(allow_guest=True)
def get_testimonials():
    try:
        testimonials = frappe.get_all("Testimonial", fields=["customer_name as name", "title as short_description", "designation", "profile_image", "review", "description"])
        for testimonial in testimonials:
            testimonial["image"] = get_file(testimonial["image"])
        
        return {
            "status": "success",
            "data": testimonials
        }
    except Exception as e:
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}