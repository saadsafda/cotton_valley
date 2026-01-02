import frappe


@frappe.whitelist(allow_guest=True)
def create_lead(name, company_name, email, phone, square_footage, address, business_type, company=None):
    try:
        company = "Cotton Valley" if not company or company == "null" else company
        lead = frappe.get_doc({
            "doctype": "Lead",
            "status": "Lead",
            "first_name": name,
            "company_name": company_name,
            "email_id": email,
            "phone": phone,
            "custom_square_footage": square_footage,
            "custom_address": address,
            "custom_type_of_business": business_type,
            "company": company
        })
        lead.insert(ignore_permissions=True)
        return {"status": "success", "message": "Lead created successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}