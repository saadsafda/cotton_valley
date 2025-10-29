import frappe # type: ignore
from frappe.utils import nowdate # type: ignore
from cotton_valley.api.customer import get_current_customer
from cotton_valley.api.products import get_product, get_all_products
from cotton_valley.api.website_theme_setting import get_file
from cotton_valley.secrets import ERP_USERNAME, ERP_PASSWORD

@frappe.whitelist(allow_guest=True)
def get_submited_orders(company="Cotton Valley", page=None):
    company = "Cotton Valley" if not company or company == "null" else company
    page = None if not page or page == "null" else int(page)
    # --- Pagination ---
    limit_start = (page - 1) * 10 if page and page > 0 else None
    limit_page_length = 10 if page else None
    customer = get_current_customer()
    if not customer or not customer.get("id"):
        return {"data": [], "total": 0, "from": 0, "to": 0, "current_page": 0, "per_page": 0}

    customer_id = customer["id"]
    total_count = frappe.db.count("Sales Order", filters={"customer": customer_id, "company": company, "docstatus": 1})

    orders = frappe.get_all(
        "Sales Order",
        filters={"customer": customer_id, "company": company, "docstatus": 1},
        fields=["name as order_number", "grand_total as total", "status as payment_status", "submit_datetime as created_at", "custom_mode_of_payment as payment_method", "product_type as order_type"],
        order_by="creation desc",
        limit_start=limit_start,
        limit_page_length=limit_page_length
    )
    
    from_showing = limit_start + 1 if limit_start is not None else 1
    to_showing = limit_start + limit_page_length if limit_start is not None else total_count

    return {"data": orders, "total": total_count, "from": from_showing, "to": to_showing, "current_page": page or 1, "per_page": limit_page_length or total_count}


@frappe.whitelist(allow_guest=True)
def get_order_details(order_number):
    customer = get_current_customer()
    if not customer or not customer.get("id"):
        return None

    customer_id = customer["id"]
    so = frappe.get_all(
        "Sales Order",
        filters={"name": order_number, "customer": customer_id, "docstatus": 1},
        fields=["name"],
        limit=1,
    )
    if not so:
        return None

    so_doc = frappe.get_doc("Sales Order", so[0].name)
    items = []
    for item in so_doc.items:
        items.append({
            "id": item.item_code,
            "case_pack": item.custom_case_pack,
            "name": item.item_name,
            "sku": item.item_code,
            "product_thumbnail": get_file(item.image),
            "product_id": item.item_code,
            "quantity": item.qty,
            "sub_total": item.amount,
            "price": item.rate,
        })
    return {
        "order_number": so_doc.name,
        "amount": so_doc.total,
        "total": so_doc.grand_total,
        "payment_status": so_doc.order_status,
        "created_at": so_doc.transaction_date,
        "payment_method": so_doc.custom_mode_of_payment,
        "billing_address_id": so_doc.customer_address,
        "billing_address_details": so_doc.billing_address_details,
        "billing_state": so_doc.state,
        "billing_country": so_doc.country,
        "billing_zip_code": so_doc.zip_code,
        "billing_phone": so_doc.custom_billing_phone,
        "shipping_address_id": so_doc.shipping_address_name,
        "shipping_address_details": so_doc.shipping_address_details,
        "shipping_state": so_doc.shipping_state,
        "shipping_country": so_doc.shipping_country,
        "shipping_zip_code": so_doc.shipping_zip_code,
        "shipping_phone": so_doc.shipping_phone,
        "delivery_description": so_doc.custom_shipping_method,
        "products": items,
        "order_status": {
            "status": so_doc.order_status,
            "sequence": 1 if so_doc.order_status == "Pending" else 2 if so_doc.order_status == "Processing" else 3 if so_doc.order_status == "Shipped" else 1,
        }
    }


@frappe.whitelist(allow_guest=True)
def get_cart(company="Cotton Valley"):
    company = "Cotton Valley" if not company or company == "null" else company
    customer = get_current_customer()
    if not customer or not customer.get("id"):
        return {"items": [], "total": 0.0, "count": 0}

    customer_id = customer["id"]
    so = frappe.get_all(
        "Sales Order",
        filters={"customer": customer_id, "docstatus": 0, "company": company},
        fields=["name", "grand_total"],
        limit=1,
    )
    if not so:
        return {"items": [], "total": 0.0, "discount": 0.0, "count": 0}

    so_doc = frappe.get_doc("Sales Order", so[0].name)
    items = []
    for item in so_doc.items:
        # product = get_product(item.item_code)
        all_products = get_all_products(ids=item.item_code, company=company)["data"]
        product = all_products[0] if len(all_products) > 0 else {}
        items.append({
            "id": item.name,
            "product_id": item.item_code,
            "quantity": item.qty,
            "sub_total": item.amount,
            "product": product,
        })
    return {
        "items": items,
        "total": so_doc.grand_total,
        "discount": so_doc.discount_amount,
        "count": len(items),
    }


@frappe.whitelist(allow_guest=True)
def create_or_update_sales_order(items, submit_datetime=nowdate(), company="Cotton Valley", submit=False, billing_address_id=None, shipping_address_id=None, delivery_description=None, payment_method=None, client_ip=None, client_latitude=None, client_longitude=None):
    customer = get_current_customer()
    """
    Create or update a Sales Order from cart.
    items = [
      {"item_code": "ITEM-001", "qty": 2, "rate": 500},
      {"item_code": "ITEM-002", "qty": 1, "rate": 300},
    ]
    """
    items = frappe.parse_json(items)
    company = "Cotton Valley" if not company or company == "null" else company
    billing_address_id = None if not billing_address_id or billing_address_id == "null" else billing_address_id
    shipping_address_id = None if not shipping_address_id or shipping_address_id == "null" else shipping_address_id
    delivery_description = None if not delivery_description or delivery_description == "null" else delivery_description
    payment_method = None if not payment_method or payment_method == "null" else payment_method
    client_ip = None if not client_ip or client_ip == "null" else client_ip
    client_latitude = None if not client_latitude or client_latitude == "null" else client_latitude
    client_longitude = None if not client_longitude or client_longitude == "null" else client_longitude

    if not customer:
        return "Customer not found"

    customer_id = customer["id"]

    if submit and company != "Cotton Valley":
        so = frappe.get_all(
            "Sales Order",
            filters={"customer": customer_id, "docstatus": 0, "company": company},
            fields=["name"],
            limit=1,
        )

        if so:
            draft_doc = frappe.get_doc("Sales Order", so[0].name)
            # delete draft cart after extracting items
            frappe.delete_doc("Sales Order", draft_doc.name, ignore_permissions=True)
            frappe.db.commit()
        
        regular_items = [i for i in items if i.get("product_type") == "Regular"]
        cod_items = [i for i in items if i.get("product_type") == "COD"]

        created_orders = []

        def make_so(item_list, so_type):
            if not item_list:
                return None
            so_doc = frappe.new_doc("Sales Order")
            so_doc.customer = customer_id
            so_doc.order_type = "Shopping Cart"
            so_doc.delivery_date = nowdate()
            so_doc.submit_datetime = submit_datetime
            so_doc.company = company
            so_doc.product_type = so_type
            if client_ip:
                so_doc.customer_ip = client_ip
            if client_latitude and client_longitude:
                so_doc.customer_lat__long = f"{client_latitude}, {client_longitude}"

            if billing_address_id:
                so_doc.customer_address = billing_address_id
            if shipping_address_id:
                so_doc.shipping_address_name = shipping_address_id
            if delivery_description:
                so_doc.custom_shipping_method = delivery_description
            if payment_method:
                so_doc.custom_mode_of_payment = payment_method

            for row in item_list:
                so_doc.append("items", {
                    "item_code": row["item_code"],
                    "qty": row["qty"],
                    "rate": row["rate"],
                    "delivery_date": nowdate(),
                })

            so_doc.save(ignore_permissions=True)
            so_doc.submit()
            frappe.db.commit()

            created_orders.append({"type": so_type, "name": so_doc.name})
            return so_doc.name

        if len(regular_items) > 0:
            make_so(regular_items, "Regular")
        if len(cod_items) > 0:
            make_so(cod_items, "COD")

        return created_orders


    so = frappe.get_all(
        "Sales Order",
        filters={"customer": customer_id, "docstatus": 0, "company": company},
        fields=["name"],
        limit=1,
    )

    so_doc = {}
    if so:
        so_doc = frappe.get_doc("Sales Order", so[0].name)
        so_doc.items = []  # reset items
    else:
        so_doc = frappe.new_doc("Sales Order")
        so_doc.customer = customer_id
        so_doc.order_type = "Shopping Cart"

    so_doc.delivery_date = nowdate()
    so_doc.submit_datetime = submit_datetime
    so_doc.company = company
    if items is None or len(items) == 0:
        so_doc.delete()
        frappe.db.commit()
        return None
    
    if billing_address_id:
        so_doc.customer_address = billing_address_id
    if shipping_address_id:
        so_doc.shipping_address_name = shipping_address_id
    if delivery_description:
        so_doc.custom_shipping_method = delivery_description
    if payment_method:
        so_doc.custom_mode_of_payment = payment_method

    if client_ip:
        so_doc.customer_ip = client_ip
    if client_latitude and client_longitude:
        so_doc.customer_lat__long = f"{client_latitude}, {client_longitude}"


    for row in items:
        so_doc.append("items", {
            "item_code": row["item_code"],
            "qty": row["qty"],
            "rate": row["rate"],
            "delivery_date": nowdate(),
        })
    so_doc.save(ignore_permissions=True)
    if submit:
        so_doc.submit()
    frappe.db.commit()
    return so_doc.name



@frappe.whitelist(allow_guest=True)
def apply_coupon(code, company="Cotton Valley"):
    company = "Cotton Valley" if not company or company == "null" else company
    if not code or code == "null":
        return {"success": False, "message": "Coupon code is required."}

    customer = get_current_customer()
    if not customer or not customer.get("id"):
        return {"success": False, "message": "Customer not found."}

    customer_id = customer["id"]
    so = frappe.get_all(
        "Sales Order",
        filters={"customer": customer_id, "docstatus": 0, "company": company},
        fields=["name"],
        limit=1,
    )
    if not so:
        return {"success": False, "message": "Sales Order not found."}

    so_doc = frappe.get_doc("Sales Order", so[0].name)
    coupon = frappe.get_all(
        "Coupon Code",
        filters={"coupon_code": code, "valid_from": ("<=", nowdate()), "valid_upto": (">=", nowdate())},
        fields=["name", "max_order_amount", "min_order_amount"],
        limit=1,
    )
    if not coupon:
        return {"success": False, "message": "Invalid or expired coupon code."}

    coupon_doc = frappe.get_doc("Coupon Code", coupon[0].name)
    if so_doc.grand_total < coupon_doc.min_order_amount:
        return {"success": False, "message": f"Minimum purchase amount for this coupon is {coupon_doc.min_order_amount}."}

    if coupon_doc.max_order_amount and so_doc.grand_total > coupon_doc.max_order_amount:
        return {"success": False, "message": f"Maximum purchase amount for this coupon is {coupon_doc.max_order_amount}."}

    so_doc.coupon_code = coupon_doc.name
    so_doc.delivery_date = nowdate()
    so_doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True, "message": f"Coupon applied successfully. You saved {so_doc.discount_amount}!", "discount_amount": so_doc.discount_amount, "new_total": so_doc.grand_total}


@frappe.whitelist()
def push_to_erp(sales_orders):
    """
    Push Sales Orders to external ERP system using curl.
    Updates push_to_erp field to 1 after successful push.
    """
    import json
    import subprocess
    import time
    
    if isinstance(sales_orders, str):
        sales_orders = json.loads(sales_orders)
    
    # ERP API configuration
    ERP_URL = "https://erp.cottonvalley.us/ords/unvdst/order/ord"
    username = ERP_USERNAME
    password = ERP_PASSWORD
    
    results = {
        "success": [],
        "failed": []
    }
    
    for so_name in sales_orders:
        try:
            # Get Sales Order document
            so_doc = frappe.get_doc("Sales Order", so_name)
            
            # Check if already pushed
            if so_doc.get("push_to_erp") == 1:
                results["failed"].append({
                    "order": so_name,
                    "error": "Already pushed to ERP"
                })
                continue
            
            # Track successful item pushes
            pushed_items = []
            
            # Prepare payload for each item in the Sales Order
            for item in so_doc.items:
                customer_erp_id = ""
                if so_doc.company == "Cotton Valley":
                    customer_erp_id = frappe.db.get_value("Customer", so_doc.customer, "cv_customer_id") or ""
                else:
                    customer_erp_id = frappe.db.get_value("Customer", so_doc.customer, "udc_customer_id") or ""
                    
                payload = {
                    "order_date": so_doc.transaction_date.strftime("%d-%b-%y").lower(),
                    "customer_id": customer_erp_id,
                    "trnrefno": so_doc.name,
                    "customer_note": so_doc.get("custom_customer_note") or "",
                    "everst_so_no": so_doc.name,
                    "item_id": item.item_code,
                    "qty": str(int(item.qty)),
                    "rate": str(float(item.rate))
                }
                
                # Make API call using curl (more reliable for problematic connections)
                max_attempts = 3
                last_error = None
                
                for attempt in range(max_attempts):
                    try:
                        # Prepare curl command with TLS settings for Oracle ORDS
                        curl_command = [
                            'curl',
                            '-X', 'POST',
                            '-H', 'Content-Type: application/json',
                            '-H', 'Accept: application/json',
                            '-u', f'{username}:{password}',
                            '--data', json.dumps(payload),
                            '--insecure',  # Skip SSL verification
                            '--tlsv1.2',  # Force TLS 1.2 (Oracle ORDS common requirement)
                            '--max-time', '60',
                            '--connect-timeout', '30',
                            '--compressed',  # Enable compression
                            '-v',  # Verbose output for debugging
                            ERP_URL
                        ]
                        
                        # Execute curl command
                        result = subprocess.run(
                            curl_command,
                            capture_output=True,
                            text=True,
                            timeout=90
                        )
                        
                        # Check if curl succeeded
                        if result.returncode == 0:
                            # Parse response if needed
                            response_text = result.stdout.strip()
                            pushed_items.append(item.item_code)
                            frappe.log_error(
                                message=f"Successfully pushed item {item.item_code} for order {so_name}.\nResponse: {response_text}\nDebug: {result.stderr}",
                                title="ERP Push Success"
                            )
                            break  # Success, exit retry loop
                        else:
                            error_msg = f"Curl failed with code {result.returncode}.\nStderr: {result.stderr}\nStdout: {result.stdout}"
                            last_error = error_msg
                            
                            # Check for specific SSL/TLS errors
                            if "Connection reset by peer" in result.stderr or result.returncode == 35:
                                error_msg = "SSL/TLS Connection Error: The ERP server is rejecting the connection. This typically means:\n1. Your server IP needs to be whitelisted on their firewall\n2. Contact the ERP administrator to add your IP to their allowlist\n3. Or there may be SSL/TLS certificate issues on their end"
                            
                            if attempt < max_attempts - 1:  # Not last attempt
                                frappe.log_error(
                                    message=f"Attempt {attempt + 1} failed for {item.item_code}: {error_msg}. Retrying...",
                                    title="ERP Push Retry"
                                )
                                time.sleep(5)  # Longer wait before retry
                            else:
                                raise Exception(error_msg)
                            
                    except Exception as e:
                        last_error = str(e)
                        if attempt < max_attempts - 1:  # Not last attempt
                            frappe.log_error(
                                message=f"Attempt {attempt + 1} failed for {item.item_code}: {str(e)}. Retrying...",
                                title="ERP Push Error"
                            )
                            time.sleep(3)  # Wait before retry
                        else:
                            raise Exception(f"All {max_attempts} attempts failed. Last error: {last_error}")
            
            # Only mark as pushed if all items were successfully pushed
            if len(pushed_items) == len(so_doc.items):
                so_doc.db_set("push_to_erp", 1, update_modified=True)
                frappe.db.commit()
                
                results["success"].append({
                    "order": so_name,
                    "message": f"Successfully pushed {len(pushed_items)} item(s) to ERP"
                })
            else:
                raise Exception(f"Only {len(pushed_items)} of {len(so_doc.items)} items were pushed successfully")
            
        except Exception as e:
            frappe.log_error(
                message=f"Error pushing Sales Order {so_name} to ERP: {str(e)}",
                title="ERP Push Error"
            )
            results["failed"].append({
                "order": so_name,
                "error": str(e)
            })
    
    # Prepare response message
    success_count = len(results["success"])
    failed_count = len(results["failed"])
    
    if failed_count == 0:
        message = f"Successfully pushed {success_count} order(s) to ERP"
        status = "success"
    elif success_count == 0:
        message = f"Failed to push all {failed_count} order(s) to ERP"
        status = "error"
    else:
        message = f"Pushed {success_count} order(s) successfully, {failed_count} failed"
        status = "partial"
    
    return {
        "status": status,
        "message": message,
        "results": results
    }
