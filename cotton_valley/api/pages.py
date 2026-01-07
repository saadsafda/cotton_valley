import frappe # type: ignore
from cotton_valley.api.website_theme_setting import get_file


@frappe.whitelist(allow_guest=True)
def get_privacy_policy_page(company=None):
    doctype = "Privacy Policy Page"
    company = "Cotton Valley" if not company or company == "null" else company
    if company == "UDC":
        doctype = f"UDC Privacy Policy Page"
    privacy_page = frappe.get_single(doctype)
    return {
        "banner_image": get_file(privacy_page.banner_image),
        "details": privacy_page.details
    }

@frappe.whitelist(allow_guest=True)
def get_terms_and_conditions_page(company=None):
    doctype = "Terms and Condition Page"
    company = "Cotton Valley" if not company or company == "null" else company
    if company == "UDC":
        doctype = f"UDC Terms and Condition Page"
    terms_page = frappe.get_single(doctype)
    return {
        "banner_image": get_file(terms_page.banner_image),
        "details": terms_page.details
    }

@frappe.whitelist(allow_guest=True)
def get_shipping_and_return_page(company=None):
    doctype = "Shipping and Return Page"
    company = "Cotton Valley" if not company or company == "null" else company
    if company == "UDC":
        doctype = f"UDC Shipping and Return Page"
    shipping_page = frappe.get_single(doctype)
    return {
        "banner_image": get_file(shipping_page.banner_image),
        "details": shipping_page.details
    }

@frappe.whitelist(allow_guest=True)
def get_event_pages(name):
    try:
        page = frappe.get_doc("Event Page", name)
        page.banner_image = get_file(page.banner_image)
        return page
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": f"Event Page with name '{name}' not found."}
    except Exception as e:
        frappe.local.response["http_status_code"] = 500
        return {"error": f"An error occurred: {str(e)}"}