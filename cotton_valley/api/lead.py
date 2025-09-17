import frappe


@frappe.whitelist(allow_guest=True)
def create_lead(name, company_name, email, phone, square_footage, address, business_type):
    print(name)