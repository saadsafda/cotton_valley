import frappe
from cotton_valley.api.website_theme_setting import get_file

@frappe.whitelist(allow_guest=True)
def get_about_page():
    try:
        about_page = frappe.get_single("About Page")
        clients = []
        for client in about_page.clients:
            clients.append({
                "title": client.title,
                "image_icon": get_file(client.image_icon),
                "description": client.description,
                "count": client.count
            })
        return {
            "status": "success",
            "data": {
                "title": about_page.title,
                "description": about_page.description,
                "banner_image": get_file(about_page.page_banner),
                "first_image": get_file(about_page.first_image),
                "second_image": get_file(about_page.sec_image),
                "client_title": about_page.client_title,
                "client_subtitle": about_page.client_sub_title,
                "clients": about_page.get("clients")
            }
        }
    except Exception as e:
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}