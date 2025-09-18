import frappe
from cotton_valley.api.customer import get_current_customer


@frappe.whitelist()
def add_address(address):
    customer = get_current_customer()
    address = frappe.get_doc({
        "doctype": "Address",
        "address_title": address.get("address_title"),
        "address_type": address.get("address_type"),
        "address_line1": address.get("address_line1"),
        "address_line2": address.get("address_line2"),
        "city": address.get("city"),
        "state": address.get("state"),
        "pincode": address.get("pincode"),
        "country": address.get("country"),
        "phone": address.get("phone"),
        "links": [{
            "link_doctype": "Customer",
            "link_name": customer.get("id")
        }]
    }).insert(ignore_permissions=True)

    return {
                "id": address.name,
                "title": address.address_title,
                "address_type": address.address_type,
                "street": address.address_line1,
                "city": address.city,
                "pincode": address.pincode,
                "phone": address.phone,
                "country": {"id": address.country, "name": address.country},
                "state": {"id": address.state, "name": address.state},
            }

@frappe.whitelist()
def update_address(address):
    customer = get_current_customer()
    addr = frappe.get_doc("Address", address.get("id"))
    addr.address_title = address.get("address_title")
    addr.address_type = address.get("address_type")
    addr.address_line1 = address.get("address_line1")
    addr.address_line2 = address.get("address_line2")
    addr.city = address.get("city")
    addr.state = address.get("state")
    addr.pincode = address.get("pincode")
    addr.country = address.get("country")
    addr.phone = address.get("phone")
    addr.save(ignore_permissions=True)

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
            }