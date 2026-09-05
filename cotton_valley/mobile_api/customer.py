import secrets

import frappe
from cotton_valley.api.website_theme_setting import get_file
from cotton_valley.api.sales_team import (
    get_customer_sales_team,
    get_customers_for_sales_persons,
    get_user_sales_persons,
)
from datetime import datetime, timedelta

@frappe.whitelist()
def get_all_customers():
    """Fetch all customers from the database."""
    try:
        current_user = frappe.session.user

        # Every Sales Person the current user may act as (Employee link plus
        # any "Sales Person" User Permission rows).
        permitted_sales_persons = get_user_sales_persons(current_user)

        if not permitted_sales_persons:
            return {
                "status": "success",
                "message": "No sales person linked or permitted for current user",
                "data": [],
                "count": 0
            }

        # A customer is visible when any permitted rep is on its sales team,
        # i.e. the primary rep (sales_person / udc_sales_person) OR an extra rep
        # listed in the custom_additional_sales_team child table.
        permitted_customers = get_customers_for_sales_persons(permitted_sales_persons)

        customers = frappe.get_list("Customer",
            filters={"name": ["in", permitted_customers]} if permitted_customers else {"name": ["in", [""]]},
            page_length=0,
            fields=["name", "customer_name", "custom_email_address", "custom_phone_number", "image", "disabled",
                    "mode_of_payment", "sales_person", "udc_sales_person", "custom_company_name", "creation", "modified",
                    "customer_primary_address", "account_number", "udc_account_number", "customer_billing_address", "price_list_for_cv", "price_list_for_udc",
                    "no_of_orders", "orders_amount"]
        )

        new_opt_customers = frappe.get_all("Customer",
            filters={"customer_name": "New Opportunity"},
            page_length=0,
            fields=["name", "customer_name", "custom_email_address", "custom_phone_number", "image", "disabled",
                    "mode_of_payment", "sales_person", "udc_sales_person", "custom_company_name", "creation", "modified",
                    "customer_primary_address", "account_number", "udc_account_number", "customer_billing_address", "price_list_for_cv", "price_list_for_udc",
                    "no_of_orders", "orders_amount"]
        )

        customers.extend(new_opt_customers)
        # Keep unique customers by name to avoid duplicates (e.g. New Opportunity already matched above).
        customers = list({c.name: c for c in customers}.values())

        if not customers:
            return {
                "status": "success",
                "message": "No customers found",
                "data": [],
                "count": 0
            }
        
        # Calculate date 90 days ago
        ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        
        # Get all customer IDs for batch query
        customer_ids = [c.name for c in customers]
    
        # Batch query to check last order date for all customers
        last_orders = frappe.db.sql("""
            SELECT customer, MAX(transaction_date) as last_order_date
            FROM `tabSales Order`
            WHERE customer IN %s
            AND docstatus = 1
            GROUP BY customer
        """, (customer_ids,), as_dict=True)
        
        # Create a dictionary for quick lookup
        last_order_map = {order.customer: order.last_order_date for order in last_orders}
        
        # OPTIMIZATION: Batch fetch ALL addresses for ALL customers in ONE query (instead of N+M queries)
        all_addresses = frappe.db.sql("""
            SELECT 
                dl.link_name as customer,
                a.name,
                a.address_title,
                a.address_line1,
                a.address_type,
                a.city,
                a.pincode,
                a.phone,
                a.country,
                a.state
            FROM `tabDynamic Link` dl
            INNER JOIN `tabAddress` a ON a.name = dl.parent
            WHERE dl.link_doctype = 'Customer' 
                AND dl.link_name IN %s
                AND dl.parenttype = 'Address'
        """, (customer_ids,), as_dict=True)
        
        # Group addresses by customer
        addresses_by_customer = {}
        for addr in all_addresses:
            addresses_by_customer.setdefault(addr.customer, []).append(addr)

        # Batch fetch additional sales reps for all customers in one query so the
        # app can show the full team, not just the primary rep.
        additional_team_rows = frappe.get_all(
            "Customer Sales Team",
            filters={"parenttype": "Customer", "parent": ["in", customer_ids]},
            fields=["parent", "sales_person", "sales_person_name", "company"]
        )
        additional_team_by_customer = {}
        for row in additional_team_rows:
            additional_team_by_customer.setdefault(row.parent, []).append(row)
        
        customer_list = []
        for customer in customers:
            # Check if customer has ordered in last 90 days
            last_order_date = last_order_map.get(customer.name)
            active_customer = customer.disabled
            # if last_order_date:
            #     active_customer = last_order_date.strftime('%Y-%m-%d') >= ninety_days_ago
            
            # --- Base Customer Info ---
            customer_data = {
                "id": customer.name or '',
                "name": customer.customer_name or '',
                "email": customer.custom_email_address or '',
                "country_code": customer.custom_phone_number[:1] if customer.custom_phone_number else '',
                "phone": customer.custom_phone_number or '',
                "profile_image_id": customer.image or '',
                "status": customer.disabled,
                "sales_person": customer.sales_person or '',
                "udc_sales_person": customer.udc_sales_person or '',
                "additional_sales_persons": [
                    {
                        "id": row.sales_person or '',
                        "name": row.sales_person_name or '',
                        "company": row.company or '',
                    }
                    for row in additional_team_by_customer.get(customer.name, [])
                ],
                "sales_team": list(dict.fromkeys(
                    [sp for sp in [customer.sales_person, customer.udc_sales_person] if sp]
                    + [row.sales_person for row in additional_team_by_customer.get(customer.name, []) if row.sales_person]
                )),
                "active_customer": active_customer,
                "mode_of_payment": customer.mode_of_payment or '',
                "company": customer.custom_company_name or '',
                "account_number": customer.account_number or '',
                "udc_account_number": customer.udc_account_number or '',
                "price_list_for_cv": customer.price_list_for_cv or '',
                "price_list_for_udc": customer.price_list_for_udc or '',
                "no_of_orders": customer.no_of_orders or 0,
                "orders_amount": customer.orders_amount or 0.0,
                "last_order_date": last_order_date.strftime('%Y-%m-%d') if last_order_date else '',
                "created_at": customer.creation or '',
                "updated_at": customer.modified or '',
            }
            # --- Addresses (OPTIMIZED: Use pre-fetched data) ---
            addresses = []
            for addr in addresses_by_customer.get(customer.name, []):
                is_default = 0
                if addr.address_type == "Shipping" and addr.name == customer.customer_primary_address:
                    is_default = 1
                if addr.address_type == "Billing" and addr.name == customer.customer_billing_address:
                    is_default = 1

                addresses.append({
                    "id": addr.name or '',
                    "title": addr.address_title or '',
                    "street": addr.address_line1 or '',
                    "address_type": addr.address_type or '',
                    "city": addr.city or '',
                    "pincode": addr.pincode or '',
                    "is_default": is_default or 0,
                    "country_code": customer_data["country_code"] or '',
                    "phone": addr.phone or '',
                    "country": addr.country or '',
                    "state": addr.state or '',
                })
            customer_data["address"] = addresses

            # --- Profile Image ---
            customer_data["profile_image"] = get_file(customer.image)

            customer_list.append(customer_data)

        return {
            "status": "success",
            "message": "Customers fetched successfully",
            "data": customer_list,
            "count": len(customer_list)
        }
        
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "status": "error",
            "message": "Customer doctype does not exist"
        }
    except frappe.PermissionError:
        frappe.local.response["http_status_code"] = 403
        return {
            "status": "error",
            "message": "You do not have permission to access customers"
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get All Customers Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "status": "error",
            "message": "An error occurred while fetching customers",
            "error": str(e)
        }


@frappe.whitelist()
def create_customer_address(customer_id, address, address_type="Shipping", is_default=0, company=None):
    """
    Create an address for a specific customer.

    Args:
        customer_id (str): Customer document name.
        address (str|dict): Address payload (JSON string or dict).
        address_type (str): Shipping or Billing.
        is_default (int|str|bool): Mark as default for selected type.
        company (str): Optional company name.
    """
    try:
        customer_id = None if not customer_id or customer_id == "null" else customer_id
        company = "Cotton Valley" if not company or company == "null" else company
        address_type = "Shipping" if not address_type or address_type == "null" else address_type
        is_default = frappe.utils.cint(is_default)

        if not customer_id:
            return {
                "status": "error",
                "message": "Customer is required"
            }

        if not frappe.db.exists("Customer", customer_id):
            return {
                "status": "error",
                "message": "Customer not found"
            }

        address = frappe.parse_json(address) if isinstance(address, str) else address
        if not isinstance(address, dict):
            return {
                "status": "error",
                "message": "Invalid address payload"
            }

        address_type = address.get("address_type") or address_type
        if address_type not in ["Shipping", "Billing"]:
            return {
                "status": "error",
                "message": "address_type must be Shipping or Billing"
            }

        address_doc = frappe.get_doc({
            "doctype": "Address",
            "address_title": address.get("address_title") or f"{customer_id}-{address_type}",
            "address_type": address_type,
            "address_line1": address.get("address_line1") or address.get("street"),
            "address_line2": address.get("address_line2"),
            "city": address.get("city"),
            "state": address.get("state"),
            "pincode": address.get("pincode"),
            "country": address.get("country"),
            "phone": address.get("phone"),
            "email_id": address.get("email_id"),
            "company": company,
            "links": [{
                "link_doctype": "Customer",
                "link_name": customer_id
            }]
        })
        address_doc.insert(ignore_permissions=True)

        if is_default and address_type == "Shipping":
            frappe.db.set_value("Customer", customer_id, "customer_primary_address", address_doc.name)
        if is_default and address_type == "Billing":
            frappe.db.set_value("Customer", customer_id, "customer_billing_address", address_doc.name)

        frappe.db.commit()

        return {
            "status": "success",
            "message": "Customer address created successfully",
            "data": {
                "id": address_doc.name,
                "customer_id": customer_id,
                "title": address_doc.address_title or "",
                "address_type": address_doc.address_type or "",
                "street": address_doc.address_line1 or "",
                "city": address_doc.city or "",
                "pincode": address_doc.pincode or "",
                "phone": address_doc.phone or "",
                "country": address_doc.country or "",
                "state": address_doc.state or "",
                "is_default": is_default
            }
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error("Create Customer Address Mobile API Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist()
def edit_customer_address(customer_id, address_id, address, address_type=None, is_default=0, company=None):
    """
    Edit an existing address for a specific customer.

    Args:
        customer_id (str): Customer document name.
        address_id (str): Address document name.
        address (str|dict): Address payload (JSON string or dict).
        address_type (str): Shipping or Billing (optional override).
        is_default (int|str|bool): Mark as default for selected type.
        company (str): Optional company name.
    """
    try:
        customer_id = None if not customer_id or customer_id == "null" else customer_id
        address_id = None if not address_id or address_id == "null" else address_id
        company = "Cotton Valley" if not company or company == "null" else company
        address_type = None if not address_type or address_type == "null" else address_type
        is_default = frappe.utils.cint(is_default)

        if not customer_id:
            return {
                "status": "error",
                "message": "Customer is required"
            }

        if not address_id:
            return {
                "status": "error",
                "message": "Address is required"
            }

        if not frappe.db.exists("Customer", customer_id):
            return {
                "status": "error",
                "message": "Customer not found"
            }

        if not frappe.db.exists("Address", address_id):
            return {
                "status": "error",
                "message": "Address not found"
            }

        has_link = frappe.db.exists("Dynamic Link", {
            "parent": address_id,
            "parenttype": "Address",
            "link_doctype": "Customer",
            "link_name": customer_id
        })
        if not has_link:
            return {
                "status": "error",
                "message": "Address does not belong to this customer"
            }

        address = frappe.parse_json(address) if isinstance(address, str) else address
        if not isinstance(address, dict):
            return {
                "status": "error",
                "message": "Invalid address payload"
            }

        addr_doc = frappe.get_doc("Address", address_id)
        final_address_type = address.get("address_type") or address_type or addr_doc.address_type
        if final_address_type not in ["Shipping", "Billing"]:
            return {
                "status": "error",
                "message": "address_type must be Shipping or Billing"
            }

        addr_doc.address_title = address.get("address_title") or addr_doc.address_title or f"{customer_id}-{final_address_type}"
        addr_doc.address_type = final_address_type
        addr_doc.address_line1 = address.get("address_line1") or address.get("street") or addr_doc.address_line1
        addr_doc.address_line2 = address.get("address_line2") if "address_line2" in address else addr_doc.address_line2
        addr_doc.city = address.get("city") if "city" in address else addr_doc.city
        addr_doc.state = address.get("state") if "state" in address else addr_doc.state
        addr_doc.pincode = address.get("pincode") if "pincode" in address else addr_doc.pincode
        addr_doc.country = address.get("country") if "country" in address else addr_doc.country
        addr_doc.phone = address.get("phone") if "phone" in address else addr_doc.phone
        addr_doc.email_id = address.get("email_id") if "email_id" in address else addr_doc.email_id
        addr_doc.company = address.get("company") or company
        addr_doc.save(ignore_permissions=True)

        if is_default and final_address_type == "Shipping":
            frappe.db.set_value("Customer", customer_id, "customer_primary_address", addr_doc.name)
        if is_default and final_address_type == "Billing":
            frappe.db.set_value("Customer", customer_id, "customer_billing_address", addr_doc.name)

        frappe.db.commit()

        return {
            "status": "success",
            "message": "Customer address updated successfully",
            "data": {
                "id": addr_doc.name,
                "customer_id": customer_id,
                "title": addr_doc.address_title or "",
                "address_type": addr_doc.address_type or "",
                "street": addr_doc.address_line1 or "",
                "city": addr_doc.city or "",
                "pincode": addr_doc.pincode or "",
                "phone": addr_doc.phone or "",
                "country": addr_doc.country or "",
                "state": addr_doc.state or "",
                "is_default": is_default
            }
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error("Edit Customer Address Mobile API Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist()
def get_customer_sales_persons(customer_id, company=None):
    """Return every sales representative attached to a customer.

    Includes the ERP-owned primary rep for each company plus every additional
    rep from the custom_additional_sales_team child table.
    """
    try:
        customer_id = None if not customer_id or customer_id == "null" else customer_id
        company = None if not company or company == "null" else company

        if not customer_id:
            return {"status": "error", "message": "Customer is required"}

        if not frappe.db.exists("Customer", customer_id):
            return {"status": "error", "message": "Customer not found"}

        primaries = frappe.db.get_value(
            "Customer", customer_id, ["sales_person", "udc_sales_person"], as_dict=True
        ) or {}

        data = []
        for sp_name in get_customer_sales_team(customer_id, company):
            sp = frappe.db.get_value(
                "Sales Person", sp_name,
                ["name", "sales_person_name", "employee"], as_dict=True
            )
            if not sp:
                continue

            sp_employee = {}
            if sp.employee:
                sp_employee = frappe.db.get_value(
                    "Employee", {"name": sp.employee}, ["user_id", "cell_number"], as_dict=True
                ) or {}

            is_primary = sp_name in (primaries.get("sales_person"), primaries.get("udc_sales_person"))
            data.append({
                "id": sp.name,
                "name": sp.sales_person_name or "",
                "email": sp_employee.get("user_id") or "",
                "phone": sp_employee.get("cell_number") or "",
                "is_primary": 1 if is_primary else 0,
            })

        return {
            "status": "success",
            "message": "Customer sales persons fetched successfully",
            "data": data,
            "count": len(data)
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Customer Sales Persons Error")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def assign_sales_person_to_customer(customer_id, sales_person, company="Cotton Valley"):
    """Add an additional sales representative to a customer.

    The primary rep stays untouched (the ERP sync owns it); this only appends to
    the custom_additional_sales_team child table.
    """
    try:
        customer_id = None if not customer_id or customer_id == "null" else customer_id
        sales_person = None if not sales_person or sales_person == "null" else sales_person
        company = "Cotton Valley" if not company or company == "null" else company

        if not customer_id:
            return {"status": "error", "message": "Customer is required"}
        if not sales_person:
            return {"status": "error", "message": "Sales Person is required"}

        if not frappe.db.exists("Customer", customer_id):
            return {"status": "error", "message": "Customer not found"}
        if not frappe.db.exists("Sales Person", sales_person):
            return {"status": "error", "message": "Sales Person not found"}

        if sales_person in get_customer_sales_team(customer_id, company):
            return {
                "status": "success",
                "message": "Sales person is already on this customer's sales team",
                "data": get_customer_sales_team(customer_id, company)
            }

        customer_doc = frappe.get_doc("Customer", customer_id)
        customer_doc.append("custom_additional_sales_team", {
            "sales_person": sales_person,
            "company": company,
        })
        customer_doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": "Sales person assigned successfully",
            "data": get_customer_sales_team(customer_id, company)
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Assign Sales Person Error")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def remove_sales_person_from_customer(customer_id, sales_person, company=None):
    """Remove an additional sales representative from a customer.

    The primary rep cannot be removed here: it is owned by the ERP sync and must
    be changed on the Customer record itself.
    """
    try:
        customer_id = None if not customer_id or customer_id == "null" else customer_id
        sales_person = None if not sales_person or sales_person == "null" else sales_person
        company = None if not company or company == "null" else company

        if not customer_id:
            return {"status": "error", "message": "Customer is required"}
        if not sales_person:
            return {"status": "error", "message": "Sales Person is required"}

        if not frappe.db.exists("Customer", customer_id):
            return {"status": "error", "message": "Customer not found"}

        primaries = frappe.db.get_value(
            "Customer", customer_id, ["sales_person", "udc_sales_person"], as_dict=True
        ) or {}
        if sales_person in (primaries.get("sales_person"), primaries.get("udc_sales_person")):
            return {
                "status": "error",
                "message": "Cannot remove the primary sales representative. Change it on the customer record instead."
            }

        customer_doc = frappe.get_doc("Customer", customer_id)
        remaining = [
            row for row in (customer_doc.custom_additional_sales_team or [])
            if not (row.sales_person == sales_person and (not company or row.company == company))
        ]

        if len(remaining) == len(customer_doc.custom_additional_sales_team or []):
            return {"status": "error", "message": "Sales person is not on this customer's sales team"}

        customer_doc.custom_additional_sales_team = remaining
        customer_doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": "Sales person removed successfully",
            "data": get_customer_sales_team(customer_id, company)
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Remove Sales Person Error")
        return {"status": "error", "message": str(e)}


def _resolve_link(doctype, value, extra_filters=None):
    """Resolve a user-supplied value to an existing link target, or None.

    Matches on the document name first, then on the doctype's title-ish field,
    so the app can send either the id or the label shown in its dropdown.
    """
    if not value:
        return None

    value = str(value).strip()
    if not value:
        return None

    if frappe.db.exists(doctype, value):
        return value

    title_field = {
        "Price List": "price_list_name",
        "Mode of Payment": "mode_of_payment",
    }.get(doctype)

    if title_field:
        filters = {title_field: value}
        if extra_filters:
            filters.update(extra_filters)
        match = frappe.db.get_value(doctype, filters, "name")
        if match:
            return match

    return None


@frappe.whitelist()
def get_customer_form_options():
    """Dropdown options for the app's create-customer form.

    Returns the selling price lists and the modes of payment used as payment
    terms. Both are returned as plain name lists, which is what the app's
    dropdowns bind to.
    """
    try:
        price_levels = frappe.get_all(
            "Price List",
            filters={"enabled": 1, "selling": 1},
            pluck="name",
            order_by="name asc",
        )
        payment_terms = frappe.get_all(
            "Mode of Payment",
            filters={"enabled": 1},
            pluck="name",
            order_by="name asc",
        )

        return {
            "status": "success",
            "message": "Customer form options fetched successfully",
            "data": {
                "price_levels": price_levels,
                "payment_terms": payment_terms,
                "countries": frappe.get_all("Country", pluck="name", order_by="name asc"),
            },
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Customer Form Options Error")
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}


def _create_customer_address(customer_id, address, address_type, company, phone=None):
    """Insert one Address linked to `customer_id`. Returns its name, or None."""
    if not isinstance(address, dict):
        return None

    street = (address.get("address_line1") or address.get("street") or "").strip()
    if not street:
        return None

    country = _resolve_link("Country", address.get("country")) or address.get("country")

    address_doc = frappe.get_doc({
        "doctype": "Address",
        "address_title": (address.get("address_title") or customer_id)[:100],
        "address_type": address_type,
        "address_line1": street,
        "address_line2": address.get("address_line2"),
        "city": address.get("city"),
        "state": address.get("state"),
        "pincode": address.get("pincode"),
        "country": country,
        "phone": address.get("phone") or phone,
        "email_id": address.get("email_id"),
        "company": company,
        "links": [{"link_doctype": "Customer", "link_name": customer_id}],
    })
    address_doc.insert(ignore_permissions=True)
    return address_doc.name


@frappe.whitelist()
def create_customer(**kwargs):
    """Create a customer from the mobile app (feature #222).

    Records which sales rep created it so the portal can report on app-created
    customers, assigns the rep as the customer's sales person, and creates the
    shipping/billing addresses.
    """
    try:
        data = kwargs
        # Frappe passes a JSON body through as individual kwargs, but tolerate a
        # single `data`/`payload` blob too.
        for key in ("data", "payload"):
            if key in data and isinstance(data.get(key), (str, dict)):
                blob = data.get(key)
                data = frappe.parse_json(blob) if isinstance(blob, str) else blob
                break

        def val(*keys):
            for k in keys:
                v = data.get(k)
                if v is not None and str(v).strip() not in ("", "null"):
                    return str(v).strip()
            return None

        first_name = val("first_name")
        last_name = val("last_name")
        customer_name = val("customer_name") or " ".join(
            [p for p in [first_name, last_name] if p]
        )

        if not customer_name:
            frappe.local.response["http_status_code"] = 400
            return {"status": "error", "message": "Customer name is required"}

        email = val("email", "custom_email_address")
        phone = val("phone", "custom_phone_number")
        company_name = val("company_name", "custom_company_name")
        company = val("company") or "Cotton Valley"

        # The rep who is creating this customer. Trust the session over the
        # payload so attribution cannot be spoofed by the client.
        session_sales_persons = get_user_sales_persons(frappe.session.user)
        creator_sales_person = session_sales_persons[0] if session_sales_persons else None

        sales_person = creator_sales_person or _resolve_link(
            "Sales Person", val("sales_person")
        )
        udc_sales_person = creator_sales_person or _resolve_link(
            "Sales Person", val("udc_sales_person")
        )

        # "Same for UDC" is resolved by the app, but re-apply it defensively so
        # a partial payload still lands consistently.
        price_cv = _resolve_link("Price List", val("price_list_for_cv"))
        price_udc = _resolve_link("Price List", val("price_list_for_udc"))
        if frappe.utils.cint(data.get("same_price_level_for_udc")) or not price_udc:
            price_udc = price_udc or price_cv

        mop_cv = _resolve_link("Mode of Payment", val("payment_terms_for_cv", "mode_of_payment"))
        mop_udc = _resolve_link("Mode of Payment", val("payment_terms_for_udc", "udc_mode_of_payment"))
        if frappe.utils.cint(data.get("same_payment_terms_for_udc")) or not mop_udc:
            mop_udc = mop_udc or mop_cv

        customer = frappe.new_doc("Customer")
        customer.customer_name = customer_name
        customer.customer_type = "Company" if company_name else "Individual"

        # `custom_password` is the customer's web-portal login and is mandatory.
        # App-created customers don't get a portal login here, so store a random
        # secret rather than a blank or guessable value; the customer resets it
        # through the normal forgot-password flow if they ever need portal access.
        if customer.meta.get_field("custom_password"):
            customer.custom_password = val("password") or secrets.token_urlsafe(24)

        defaults = {
            "customer_group": frappe.db.get_single_value("Selling Settings", "customer_group")
            or frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
            "territory": frappe.db.get_single_value("Selling Settings", "territory")
            or frappe.db.get_value("Territory", {"is_group": 0}, "name"),
        }
        for field, value in defaults.items():
            if value:
                setattr(customer, field, value)

        optional_fields = {
            "custom_last_name": last_name,
            "custom_email_address": email,
            "custom_phone_number": phone,
            "custom_company_name": company_name,
            "custom_store_name": company_name,
            "price_list_for_cv": price_cv,
            "price_list_for_udc": price_udc,
            "mode_of_payment": mop_cv,
            "udc_mode_of_payment": mop_udc,
            "sales_person": sales_person,
            "udc_sales_person": udc_sales_person,
            # Attribution: who created this customer, and that it came from the app.
            "custom_created_from_app": 1,
            "custom_created_by_sales_person": creator_sales_person,
        }
        for field, value in optional_fields.items():
            if value not in (None, "") and customer.meta.get_field(field):
                setattr(customer, field, value)

        customer.insert(ignore_permissions=True)

        # --- Addresses ---
        shipping = data.get("shipping_address")
        billing = data.get("billing_address")
        if isinstance(shipping, str):
            shipping = frappe.parse_json(shipping)
        if isinstance(billing, str):
            billing = frappe.parse_json(billing)

        billing_same = frappe.utils.cint(data.get("billing_same_as_shipping"))
        if billing_same and shipping and not billing:
            billing = dict(shipping)

        shipping_name = _create_customer_address(
            customer.name, shipping, "Shipping", company, phone
        )
        billing_name = _create_customer_address(
            customer.name, billing, "Billing", company, phone
        )

        if shipping_name:
            customer.db_set("customer_primary_address", shipping_name, update_modified=False)
        if billing_name:
            customer.db_set("customer_billing_address", billing_name, update_modified=False)

        frappe.db.commit()

        customer.reload()
        return {
            "status": "success",
            "message": "Customer created successfully",
            "data": _customer_payload(customer, shipping_name, billing_name),
        }
    except frappe.DuplicateEntryError:
        frappe.db.rollback()
        frappe.local.response["http_status_code"] = 409
        return {"status": "error", "message": "A customer with this name already exists"}
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Create Customer Mobile API Error")
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}


def _customer_payload(customer, shipping_name=None, billing_name=None):
    """Shape a Customer doc like `get_all_customers` does, for the app's parser."""
    addresses = []
    for addr in frappe.get_all(
        "Dynamic Link",
        filters={"link_doctype": "Customer", "link_name": customer.name, "parenttype": "Address"},
        pluck="parent",
    ):
        a = frappe.db.get_value(
            "Address", addr,
            ["name", "address_title", "address_line1", "address_type", "city",
             "pincode", "phone", "country", "state"],
            as_dict=True,
        )
        if not a:
            continue
        addresses.append({
            "id": a.name or "",
            "title": a.address_title or "",
            "street": a.address_line1 or "",
            "address_type": a.address_type or "",
            "city": a.city or "",
            "pincode": a.pincode or "",
            "is_default": 1 if a.name in (shipping_name, billing_name) else 0,
            "country_code": (customer.custom_phone_number or "")[:1],
            "phone": a.phone or "",
            "country": a.country or "",
            "state": a.state or "",
        })

    return {
        "id": customer.name or "",
        "name": customer.customer_name or "",
        "email": customer.get("custom_email_address") or "",
        "country_code": (customer.get("custom_phone_number") or "")[:1],
        "phone": customer.get("custom_phone_number") or "",
        "profile_image_id": customer.get("image") or "",
        "status": customer.get("disabled") or 0,
        "sales_person": customer.get("sales_person") or "",
        "udc_sales_person": customer.get("udc_sales_person") or "",
        "sales_team": get_customer_sales_team(customer.name),
        "additional_sales_persons": [],
        "active_customer": customer.get("disabled") or 0,
        "mode_of_payment": customer.get("mode_of_payment") or "",
        "company": customer.get("custom_company_name") or "",
        "account_number": customer.get("account_number") or "",
        "udc_account_number": customer.get("udc_account_number") or "",
        "price_list_for_cv": customer.get("price_list_for_cv") or "",
        "price_list_for_udc": customer.get("price_list_for_udc") or "",
        "no_of_orders": customer.get("no_of_orders") or 0,
        "orders_amount": customer.get("orders_amount") or 0.0,
        "last_order_date": "",
        "created_from_app": 1 if customer.get("custom_created_from_app") else 0,
        "created_by_sales_person": customer.get("custom_created_by_sales_person") or "",
        "created_at": customer.creation or "",
        "updated_at": customer.modified or "",
        "address": addresses,
        "profile_image": get_file(customer.get("image")),
    }
