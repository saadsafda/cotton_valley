import frappe # type: ignore
from cotton_valley.api.website_theme_setting import get_file


@frappe.whitelist(allow_guest=True)
def get_privacy_policy_page():
    privacy_page = frappe.get_single("Privacy Policy Page")
    return {
        "banner_image": get_file(privacy_page.banner_image),
        "details": privacy_page.details
    }

@frappe.whitelist(allow_guest=True)
def get_terms_and_conditions_page():
    terms_page = frappe.get_single("Terms and Condition Page")
    return {
        "banner_image": get_file(terms_page.banner_image),
        "details": terms_page.details
    }

@frappe.whitelist(allow_guest=True)
def get_shipping_and_return_page():
    shipping_page = frappe.get_single("Shipping and Return Page")
    return {
        "banner_image": get_file(shipping_page.banner_image),
        "details": shipping_page.details
    }