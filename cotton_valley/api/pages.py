import frappe # type: ignore
from cotton_valley.api.website_theme_setting import get_file


@frappe.whitelist(allow_guest=True)
def get_privacy_policy_page(company="Cotton Valley"):
    doctype = "Privacy Policy Page"
    company = "Cotton Valley" if not company or company == "null" else company
    if company != "Cotton Valley":
        doctype = f"UDC Privacy Policy Page"
    privacy_page = frappe.get_single(doctype)
    return {
        "banner_image": get_file(privacy_page.banner_image),
        "details": privacy_page.details
    }

@frappe.whitelist(allow_guest=True)
def get_terms_and_conditions_page(company="Cotton Valley"):
    doctype = "Terms and Condition Page"
    company = "Cotton Valley" if not company or company == "null" else company
    if company != "Cotton Valley":
        doctype = f"UDC Terms and Condition Page"
    terms_page = frappe.get_single(doctype)
    return {
        "banner_image": get_file(terms_page.banner_image),
        "details": terms_page.details
    }

@frappe.whitelist(allow_guest=True)
def get_shipping_and_return_page(company="Cotton Valley"):
    doctype = "Shipping and Return Page"
    company = "Cotton Valley" if not company or company == "null" else company
    if company != "Cotton Valley":
        doctype = f"UDC Shipping and Return Page"
    shipping_page = frappe.get_single(doctype)
    return {
        "banner_image": get_file(shipping_page.banner_image),
        "details": shipping_page.details
    }