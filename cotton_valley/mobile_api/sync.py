"""Offline sync endpoint for the mobile app.

A rep can create a customer, its addresses and an order while offline. Each of
those was previously synced by its own call, in a fixed order, and any failure
in the middle left the rest stranded: the order referenced a customer id that
only existed on the device, the server refused it, and the rep saw "customer
not created" with no way forward.

This module accepts the whole bundle in one request and resolves it server-side
in dependency order, so the client no longer has to sequence anything.
"""

import frappe

from cotton_valley.api.sales_team import get_user_sales_persons
from cotton_valley.mobile_api.customer import (
    _create_customer_address,
    _resolve_link,
    create_customer,
)
from cotton_valley.mobile_api.sales_order import create_or_update_sales_order

# Device-local ids the app mints while offline. They exist only on that device
# until this endpoint maps them to real names.
LOCAL_CUSTOMER_PREFIX = "LOCAL-"
LOCAL_ADDRESS_PREFIX = "local_addr_"


def _is_local_id(value, prefix):
    return isinstance(value, str) and value.startswith(prefix)


def _existing_customer_for_local_id(local_id):
    """The Customer already created from this device-local id, if any.

    Makes the endpoint idempotent: a retry after a half-finished sync (or a
    response the app never received) must not create a second customer.
    """
    if not local_id:
        return None
    if not frappe.db.has_column("Customer", "custom_app_local_id"):
        return None
    return frappe.db.get_value("Customer", {"custom_app_local_id": local_id}, "name")


def _resolve_customer(customer_id, customer_payload):
    """Return a real Customer name for this order.

    Order of preference: an id the site already knows; a customer previously
    created from this same local id; otherwise create one from the payload the
    app sent alongside the order.
    """
    if customer_id and not _is_local_id(customer_id, LOCAL_CUSTOMER_PREFIX):
        if frappe.db.exists("Customer", customer_id):
            return customer_id, False

    existing = _existing_customer_for_local_id(customer_id)
    if existing:
        return existing, False

    if not isinstance(customer_payload, dict):
        return None, False

    # Reuse the existing creation endpoint rather than duplicating its rules
    # (sales-person attribution, price lists, payment terms, addresses).
    result = create_customer(**customer_payload)
    if not isinstance(result, dict) or result.get("status") != "success":
        message = (
            result.get("message") if isinstance(result, dict) else "Unknown error"
        )
        frappe.throw(f"Could not create the customer: {message}")

    created = (result.get("data") or {}).get("id")
    if not created:
        frappe.throw("Customer was created but the server returned no id")

    # Remember which device-local id this came from, so a retry maps to the
    # same record instead of creating another.
    if customer_id and frappe.db.has_column("Customer", "custom_app_local_id"):
        frappe.db.set_value(
            "Customer", created, "custom_app_local_id", customer_id,
            update_modified=False,
        )

    return created, True


def _sync_addresses(customer_id, addresses, company, phone=None):
    """Create any addresses that do not exist yet.

    Returns a map of the app's local address id -> the real Address name, so
    the order can be repointed and the app can rewrite its cached records.
    """
    mapping = {}
    if not isinstance(addresses, list):
        return mapping

    for entry in addresses:
        if not isinstance(entry, dict):
            continue

        local_id = entry.get("id") or entry.get("local_address_id")
        # Already a server address — nothing to create.
        if local_id and not _is_local_id(local_id, LOCAL_ADDRESS_PREFIX):
            if frappe.db.exists("Address", local_id):
                mapping[local_id] = local_id
                continue

        address_type = entry.get("address_type") or "Shipping"
        if address_type not in ("Shipping", "Billing"):
            address_type = "Shipping"

        try:
            name = _create_customer_address(
                customer_id, entry, address_type, company, phone
            )
        except Exception:
            # One bad address must not cost the rep the whole order; the order
            # is still usable without it.
            frappe.log_error(
                frappe.get_traceback(), "Offline sync: address creation failed"
            )
            continue

        if name and local_id:
            mapping[local_id] = name

    return mapping


@frappe.whitelist()
def sync_offline_bundle(customer=None, customer_payload=None, addresses=None, order=None, company=None):
    """Create an offline-captured customer, its addresses and its order at once.

    All three parts are optional, so the app can send whatever it has queued.
    Everything is resolved in dependency order and reported back with the real
    server ids, which the app uses to repoint its local records.

    Args:
        customer: the id the app used locally (a "LOCAL-..." placeholder when
            the customer was created offline), or a real Customer name.
        customer_payload: the create-customer fields, used only when `customer`
            does not resolve.
        addresses: list of address dicts captured offline. Each may carry an
            `id`; a "local_addr_..." one is created here and mapped.
        order: the order payload, exactly as `create_or_update_sales_order`
            expects it. Its `customer` and address ids are rewritten to the
            resolved names before it is created.
        company: company context, defaults to Cotton Valley.

    Returns a payload carrying `customer_id`, `address_map` and `order`, plus
    `created` flags so the app can tell what was new.
    """
    company = "Cotton Valley" if not company or company == "null" else company

    customer_payload = frappe.parse_json(customer_payload) if isinstance(customer_payload, str) else customer_payload
    addresses = frappe.parse_json(addresses) if isinstance(addresses, str) else addresses
    order = frappe.parse_json(order) if isinstance(order, str) else order

    # Only a rep may sync a bundle; without this the endpoint would let any
    # authenticated session mint customers.
    if not get_user_sales_persons(frappe.session.user):
        frappe.local.response["http_status_code"] = 403
        return {
            "status": "error",
            "message": "Your user is not linked to a sales person.",
        }

    local_customer_id = customer

    try:
        customer_id, customer_created = _resolve_customer(customer, customer_payload)
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Offline sync: customer failed")
        frappe.local.response["http_status_code"] = 400
        return {"status": "error", "message": str(e), "stage": "customer"}

    if not customer_id:
        frappe.local.response["http_status_code"] = 400
        return {
            "status": "error",
            "message": "No existing customer and no customer details to create one from.",
            "stage": "customer",
        }

    phone = (customer_payload or {}).get("phone") if isinstance(customer_payload, dict) else None
    address_map = _sync_addresses(customer_id, addresses, company, phone)

    result = {
        "status": "success",
        "customer_id": customer_id,
        "customer_created": customer_created,
        "local_customer_id": local_customer_id,
        "address_map": address_map,
        "order": None,
    }

    if not isinstance(order, dict) or not order.get("items"):
        return result

    # Repoint the order at whatever the server actually has.
    order = dict(order)
    order["customer"] = customer_id
    order["company"] = order.get("company") or company
    for field in ("shipping_address_id", "billing_address_id"):
        mapped = address_map.get(order.get(field))
        if mapped:
            order[field] = mapped
        elif _is_local_id(order.get(field), LOCAL_ADDRESS_PREFIX):
            # Unmapped placeholder: drop it and let the order endpoint create
            # the address from the inline payload it already accepts.
            order[field] = None

    # Strip keys the order endpoint does not take, so an app-side addition
    # cannot break the call with an unexpected-argument error.
    allowed = {
        "items", "customer", "notes", "customer_details", "submit_datetime",
        "company", "submit", "billing_address_id", "shipping_address_id",
        "delivery_description", "payment_method", "client_ip", "client_latitude",
        "client_longitude", "payment_reference", "billing_address",
        "shipping_address",
    }
    order_args = {k: v for k, v in order.items() if k in allowed}

    try:
        created_order = create_or_update_sales_order(**order_args)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Offline sync: order failed")
        # The customer and addresses are already committed and must not be
        # rolled back — the app repoints its records from this response and a
        # later retry then syncs only the order.
        result["status"] = "partial"
        result["order_error"] = str(e)
        result["stage"] = "order"
        return result

    result["order"] = created_order
    return result
