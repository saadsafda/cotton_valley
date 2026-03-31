import frappe
from cotton_valley.api.customer import get_current_customer
from cotton_valley.api.common import get_customer_from_token


@frappe.whitelist(allow_guest=True)
def add_address(address, company=None):
    customer = get_customer_from_token()
    company = "Cotton Valley" if not company or company == "null" else company
    addre = frappe.get_doc({
        "doctype": "Address",
        "address_title": f"{customer}-{address.get('address_type')}",
        "address_type": address.get("address_type"),
        "address_line1": address.get("address_line1"),
        "address_line2": address.get("address_line2"),
        "city": address.get("city"),
        "state": address.get("state"),
        "pincode": address.get("pincode"),
        "country": address.get("country"),
        "phone": address.get("phone"),
        "company": company,
        "links": [{
            "link_doctype": "Customer",
            "link_name": customer
        }]
    }).insert(ignore_permissions=True)

    if address.get("is_default") and addre.address_type == "Shipping":
        frappe.db.set_value("Customer", customer, "customer_primary_address", addre.name)

    if address.get("is_default") and addre.address_type == "Billing":
        frappe.db.set_value("Customer", customer, "customer_billing_address", addre.name)

    return {
                "id": addre.name,
                "title": addre.address_title,
                "address_type": addre.address_type,
                "street": addre.address_line1,
                "city": addre.city,
                "pincode": addre.pincode,
                "phone": addre.phone,
                "country": {"id": addre.country, "name": addre.country},
                "state": {"id": addre.state, "name": addre.state},
                "is_default": address.get("is_default"),
                "company": addre.company
            }

@frappe.whitelist(allow_guest=True)
def update_address(address, company=None):
    customer = get_customer_from_token()
    company = "Cotton Valley" if not company or company == "null" else company

    addr = frappe.get_doc("Address", address.get("id"))
    addr.address_type = address.get("address_type")
    addr.address_line1 = address.get("address_line1")
    addr.address_line2 = address.get("address_line2")
    addr.city = address.get("city")
    addr.state = address.get("state")
    addr.pincode = address.get("pincode")
    addr.country = address.get("country")
    addr.phone = address.get("phone")
    addr.company = company
    addr.save(ignore_permissions=True)

    if address.get("is_default") and addr.address_type == "Shipping":
        frappe.db.set_value("Customer", customer, "customer_primary_address", addr.name)

    if address.get("is_default") and addr.address_type == "Billing":
        frappe.db.set_value("Customer", customer, "customer_billing_address", addr.name)

    return {
                "id": addr.name,
                "title": addr.address_title,
                "address_type": addr.address_type,
                "street": addr.address_line1,
                "city": addr.city,
                "pincode": addr.pincode,
                "phone": addr.phone,
                "country": {"id": addr.country, "name": addr.country},
                "state": {"id": addr.state, "name": addr.state},
                "is_default": address.get("is_default"),
                "company": addr.company
            }


@frappe.whitelist(allow_guest=True)
def delete_address(address_id):
    try:
        # Authenticate and get customer id
        customer_id = get_customer_from_token()
        if not customer_id:
            return {"status": "error", "message": "Authentication required"}

        # Validate address exists
        if not frappe.db.exists("Address", address_id):
            return {"status": "error", "message": "Address not found"}

        addr = frappe.get_doc("Address", address_id)

        # Check if already disabled
        if addr.disabled == 1:
            return {"status": "error", "message": "Address already deleted"}

        # Verify address belongs to current customer
        link = frappe.get_value("Dynamic Link", {
            "parent": address_id,
            "link_doctype": "Customer",
            "link_name": customer_id
        })
        if not link:
            return {"status": "error", "message": "Address does not belong to the authenticated customer"}

        # If this address is set as customer's primary or billing address, clear those references
        try:
            cust = frappe.get_doc("Customer", customer_id)
            changed = False
            if cust.customer_primary_address == address_id:
                frappe.db.set_value("Customer", customer_id, "customer_primary_address", None)
                changed = True
            if cust.customer_billing_address == address_id:
                frappe.db.set_value("Customer", customer_id, "customer_billing_address", None)
                changed = True
            if changed:
                frappe.db.commit()
        except Exception:
            # non-fatal, continue to disable address
            frappe.log_error(frappe.get_traceback(), "Clear Customer Address Reference Failed")

        # Soft-delete the address by marking disabled flag
        frappe.db.set_value("Address", address_id, "disabled", 1)
        frappe.db.commit()

        return {"status": "success", "message": "Address deleted successfully"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete Address Failed")
        return {"status": "error", "message": str(e)}