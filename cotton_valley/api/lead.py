import frappe


@frappe.whitelist(allow_guest=True)
def create_lead(name, company_name, email, phone, square_footage, address, business_type):
    try:
        lead = frappe.get_doc({
            "doctype": "Lead",
            "status": "Lead",
            "first_name": name,
            "company_name": company_name,
            "email_id": email,
            "phone": phone,
            "custom_square_footage": square_footage,
            "custom_address": address,
            "custom_type_of_business": business_type
        })
        lead.insert(ignore_permissions=True)
        return {"status": "success", "message": "Lead created successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}