import frappe
from frappe import _


@frappe.whitelist()
def get_items():
    items = frappe.get_all("Item", fields=["name", "item_name", "item_group"])
    return items

@frappe.whitelist(allow_guest=True)
def get_home_banners():
    return frappe.get_doc("Homepage Banner Setting")


@frappe.whitelist(allow_guest=True)
def get_country_list():
    return frappe.get_all("Country", fields=["name", "country_name"])


@frappe.whitelist(allow_guest=True)
def get_product_categories():
    return frappe.get_all("Product Category", fields=["name", "title", "category_image"])


@frappe.whitelist(allow_guest=True)
def get_product_categories_with_count():
    # get all categories
    categories = frappe.get_all(
        "Product Category",
        fields=["name", "title", "category_image"]
    )

    # get counts of items from child table
    item_counts = frappe.db.sql("""
        SELECT c.product_category as category, COUNT(DISTINCT i.name) as total
        FROM `tabItem` i
        INNER JOIN `tabProduct Categoris` c
            ON c.parent = i.name
        WHERE c.product_category IS NOT NULL
        GROUP BY c.product_category
    """, as_dict=True)

    # convert to dict for lookup
    counts_map = {row["category"]: row["total"] for row in item_counts}

    # attach count to categories
    for cat in categories:
        cat["item_count"] = counts_map.get(cat["name"], 0)

    return categories

@frappe.whitelist(allow_guest=True)
def register_customer(data):
    try:
        # Ensure incoming data is a dict (from JSON string)
        if isinstance(data, str):
            import json
            data = json.loads(data)

        if frappe.db.exists("Customer", {"custom_email_address": data.get("email")}):
            frappe.local.response["http_status_code"] = 409
            frappe.local.response["message"] = f"{data.get('email')} email is already exist"
            frappe.local.response["status"] = "error"
            return


        # Create Customer
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": data.get("first_name"),
            "custom_last_name": data.get("last_name"),
            "custom_email_address": data.get("email"),
            "custom_cell_phone": data.get("cell_phone"),
            "custom_phone_number": f"{data.get('country_code')}{data.get('phone')}",
            "custom_password": data.get("password"),
            "custom_confirm_password": data.get("password_confirmation"),
            "custom_company_name": data.get("company_name"),
            "custom_store_name": data.get("store_name"),
            "custom_storewarehouse_area_sqft": data.get("square_footage"),
            "tax_id": data.get("federal_tax_id"),
            "website": data.get("website"),
            "custom_manager_name": data.get("manager_name"),
            "custom_manager_number": data.get("manager_number"),
            "custom_how_long_have_you_been_in_years": data.get("years_in_business"),
            "customer_type": "Individual",
            "custom_type_of_buiness": data.get("business_type"),
            "custom_how_did_you_hear_about_us": data.get("hear_about_us"),
            "custom_bank_name": data.get("bank_name"),
            "custom_bank_address": data.get("bank_address"),
            "custom_bank_phone": data.get("bank_phone"),
            "custom_bank_fax": data.get("bank_fax"),
            "custom_bank_account_number": data.get("account_number"),
            "custom_bank_city": data.get("bank_city"),
            "custom_bank_state": data.get("bank_state"),
            "custom_bank_zip_code": data.get("bank_zip_code"),
            "custom_account_type": data.get("account_type"),
            "custom_bank_email": data.get("bank_email"),
        })

        # References
        if isinstance(data.get("references"), list):
            customer.custom_business_refereances = []
            for ref in data.get("references"):
                customer.append("custom_business_refereances", {
                    "company_name": ref.get("company_name"),
                    "address": ref.get("address"),
                    "city": ref.get("city"),
                    "state": ref.get("state"),
                    "zip": ref.get("zip"),
                    "phone": ref.get("phone"),
                    "fax": ref.get("fax"),
                    "email": ref.get("email"),
                })

        customer.insert(ignore_permissions=True)

        # Addresses
        if data.get("shipping_billing_same"):
            make_customer_address(customer.name, data.get("shipping_address"), address_type="Shipping")
            make_customer_address(customer.name, data.get("shipping_address"), address_type="Billing")

        if not data.get("shipping_billing_same") and data.get("billing_address"):
            make_customer_address(customer.name, data.get("billing_address"), address_type="Billing")

        frappe.db.commit()
        return {"status": "success", "message": "Customer registered successfully", "customer_id": customer.name}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Customer Registration Failed")
        return {"status": "error", "message": str(e)}


@frappe.whitelist(allow_guest=True)
def make_customer_address(customer_id, address_data, address_type="Shipping"):
    try:
        address = frappe.get_doc({
            "doctype": "Address",
            "address_title": f"{customer_id}-{address_type}",
            "address_type": address_type,
            "address_line1": address_data.get("address_line1"),
            "address_line2": address_data.get("address_line2"),
            "city": address_data.get("city"),
            "state": address_data.get("state"),
            "pincode": address_data.get("zip"),
            "country": address_data.get("country"),
            "phone": address_data.get("phone"),
            "email_id": address_data.get("email"),
        })

        address.append("links", {
            "link_doctype": "Customer",
            "link_name": customer_id
        })
        address.insert(ignore_permissions=True)
        if address_type == "Shipping":
            frappe.db.set_value("Customer", customer_id, "customer_primary_address", address.name)
        frappe.db.commit()

        return {"status": "success", "message": "Customer address created successfully", "address_id": address.name}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Customer Address Creation Failed")
        return {"status": "error", "message": str(e)}


@frappe.whitelist(allow_guest=True)
def get_hot_products():
    items = frappe.db.sql("""
        SELECT 
            i.name AS item_code,
            i.item_name,
            i.image,
            ip.price_list_rate AS price,
            ip.currency AS currency,
            COALESCE(SUM(b.actual_qty), 0) AS stock_qty
        FROM 
            `tabItem` i
        LEFT JOIN 
            `tabItem Price` ip 
            ON ip.item_code = i.name 
            AND ip.price_list = %s
        LEFT JOIN 
            `tabBin` b
            ON b.item_code = i.name
        WHERE 
            i.disabled = 0 
            AND i.custom_is_hot_item = 1
        GROUP BY 
            i.name, i.item_name, i.image, ip.price_list_rate, ip.currency
    """, ("Standard Selling",), as_dict=True)

    return items
