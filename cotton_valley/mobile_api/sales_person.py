import frappe


@frappe.whitelist()
def check_current_user_is_sales_person():
    """
    Check if the current logged-in user is an Employee and if that Employee is a Sales Person.
    
    Returns:
        dict: Status with employee and sales person information
    """
    try:
        # Get current user
        current_user = frappe.session.user

        if not current_user or current_user == "Guest":
            return {
                "status": "error",
                "message": "No authenticated user found",
                "is_employee": False,
                "is_sales_person": False
            }
        
        # Check if user is an Employee
        employee = frappe.db.get_value(
            "Employee",
            {"user_id": current_user, "status": "Active"},
            ["name", "employee_name", "user_id", "cell_number", "company"],
            as_dict=True
        )
        
        if not employee:
            return {
                "status": "success",
                "message": "Current user is not an active employee",
                "is_employee": False,
                "is_sales_person": False,
                "user": current_user
            }
        
        # Check if this Employee is linked to a Sales Person
        sales_person = frappe.db.get_value(
            "Sales Person",
            {"employee": employee.name, "enabled": 1},
            ["name", "sales_person_name", "employee", "parent_sales_person", "show_categorywise_details",
             "show_catalog_screen", "show_database_management_screen", "show_submit_invoice_screen",
              "show_local_order_screen", "show_sales_order_screen", "show_tag_screen"],
            as_dict=True
        )
        
        if not sales_person:
            return {
                "status": "success",
                "message": "Employee is not a sales person",
                "is_employee": True,
                "is_sales_person": False,
                "employee": {
                    "id": employee.name,
                    "name": employee.employee_name,
                    "email": employee.user_id,
                    "phone": employee.cell_number,
                    "company": employee.company
                },
                "user": current_user
            }
        
        allocated_lables = frappe.db.get_all(
            "Allowed Price Lable",
            filters={
                "parent": sales_person.name,
                "parenttype": "Sales Person",
            },
            fields=["price"],
            pluck="price"
        )
        # User is both an Employee and a Sales Person
        return {
            "status": "success",
            "message": "User is an active employee and sales person",
            "is_employee": True,
            "is_sales_person": True,
            "show_categorywise_details": bool(sales_person.show_categorywise_details),
            "show_catalog_screen": bool(sales_person.show_catalog_screen),
            "show_database_management_screen": bool(sales_person.show_database_management_screen),
            "show_submit_invoice_screen": bool(sales_person.show_submit_invoice_screen),
            "show_local_order_screen": bool(sales_person.show_local_order_screen),
            "show_sales_order_screen": bool(sales_person.show_sales_order_screen),
            "show_tag_screen": bool(sales_person.show_tag_screen),
        
            "employee": {
                "id": employee.name,
                "name": employee.employee_name,
                "email": employee.user_id,
                "phone": employee.cell_number,
                "company": employee.company
            },
              "sales_person": {
                "id": sales_person.name,
                "name": sales_person.sales_person_name,
                "employee": sales_person.employee,
                "parent_sales_person": sales_person.parent_sales_person,
                "allocated_price_lables": allocated_lables,
               
            },
            "user": current_user
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Check Sales Person Failed")
        return {
            "status": "error",
            "message": str(e),
            "is_employee": False,
            "is_sales_person": False
        }


@frappe.whitelist()
def check_device_active(deviceId):
    current_user = frappe.session.user
    success = False
    message = ''

    employee = frappe.db.get_value("Employee", {"user_id": current_user, "status": "Active"}, ["name"], as_dict=True)
    if employee:
        devices = get_employee_devices(employee.name)

        if devices and len(devices.get('devices', [])) > 0:
            device_found = False
            for device in devices['devices']:
                if deviceId == device['device_id']:
                    device_found = True
                    if device['approved'] == 1:
                        success = True
                        message = "Device is approved and registered."
                    else:
                        success = False
                        message = "Device is not approved yet. Please contact admin.\n\nDevice Id: " + deviceId
                    break
            
            if not device_found:
                success = False
                message = "Device is not registered. Please contact admin.\n\nDevice Id: " + deviceId
        else:
            success = False
            message = "No devices registered for this employee. Please contact admin.\n\nDevice Id: " + deviceId
    else:
        success = False
        message = "No active employee found for the current user."

    return {
        "success": success,
        "message": message
    }


@frappe.whitelist()
def check_device_registration(deviceId, device_model, device_os):
    current_user = frappe.session.user
    success = False
    message = ''

    employee = frappe.db.get_value("Employee", {"user_id": current_user, "status": "Active"}, ["name"], as_dict=True)
    if employee:
        devices = get_employee_devices(employee.name)

        if devices and len(devices.get('devices', [])) > 0:
            device_found = False
            for device in devices['devices']:
                if deviceId == device['device_id']:
                    device_found = True
                    if device['approved'] == 1:
                        success = True
                        message = "Device is approved and registered."
                    else:
                        success = False
                        message = "Device is not approved yet. Please contact admin.\n\nDevice Id: " + deviceId
                    break
            
            if not device_found:
                success = False
                registration = frappe.get_doc("Employee Device Registration", {"employee": employee.name})
                registration.append("employee_devices", {
                    "device_id": deviceId,
                    "device_model": device_model,
                    "device_os": device_os
                })
                registration.save(ignore_permissions=True)
                frappe.db.commit()
                message = "Device is not registered. Please contact admin.\n\nDevice Id: " + deviceId
        else:
            # No devices registered for this employee yet
            if not frappe.db.exists("Employee Device Registration", {"employee": employee.name}):
                # Create new registration
                new_device_registeration = frappe.new_doc("Employee Device Registration")
                new_device_registeration.user = frappe.session.user
                new_device_registeration.employee = employee.name
                new_device_registeration.append("employee_devices", {
                    "device_id": deviceId,
                    "device_model": device_model,
                    "device_os": device_os
                })
                new_device_registeration.insert(ignore_permissions=True)
                frappe.db.commit()
                success = False
                message = "Device registered successfully. Please contact admin to approve the device."
            else:
                # Registration exists but this device not in child table
                # Add device to existing registration
                registration = frappe.get_doc("Employee Device Registration", {"employee": employee.name})
                registration.append("employee_devices", {
                    "device_id": deviceId,
                    "device_model": device_model,
                    "device_os": device_os
                })
                registration.save(ignore_permissions=True)
                frappe.db.commit()
                success = False
                message = "Device registered successfully. Please contact admin to approve the device."
    else:
        success = False
        message = "No active employee found for the current user."

    return {
        "success": success,
        "message": message
    }




def get_employee_devices(employee):
    devices = frappe.db.get_value("Employee Device Registration", {"employee": employee}, "name")
    data = {"devices": []}  # Initialize with empty list instead of empty string
    if devices:
        data["devices"] = frappe.db.sql("""
        SELECT 
            device_id, approved
        FROM 
            `tabEmployee Devices` 
        WHERE 
            parent = %(name)s

        """, values={"name": devices}, as_dict=1)
    return data



@frappe.whitelist()
def create_user_login_log(data):
    """
    Create a User Login Log record.

    Accepts `data` as dict or JSON string with possible keys:
    user, login_time, timezone, ip_address, device_model, device_os,
    app_version, latitude, longitude, country, city, extra

    Returns: {status, name/message}
    """
    try:
        if isinstance(data, str):
            data = frappe.parse_json(data)

        if not isinstance(data, dict):
            return {"status": "error", "message": "Invalid payload"}

        # Prefer session user if available, otherwise accept provided user
        current_user = frappe.session.user
        user = current_user if current_user and current_user != 'Guest' else data.get('user')

        if not user:
            return {"status": "error", "message": "User is required"}

        # Build doc fields
        login_time = data.get('login_time') or data.get('login')
        timezone = data.get('timezone')
        ip_address = data.get('ip_address') or data.get('ip')
        device_model = data.get('device_model')
        device_os = data.get('device_os')
        app_version = data.get('app_version')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        extra = data.get('extra')

        log_doc = frappe.get_doc({
            "doctype": "User Login Log",
            "user": user,
            "login_time": login_time,
            "timezone": timezone,
            "ip_address": ip_address,
            "device_model": device_model,
            "device_os": device_os,
            "app_version": app_version,
            "latitude": latitude,
            "longitude": longitude,
        })

        # If there's extra JSON data and the doctype has an 'extra' field, store it
        try:
            meta = frappe.get_meta('User Login Log')
            if extra is not None and any(f.fieldname == 'extra' for f in meta.fields):
                log_doc.extra = extra if isinstance(extra, str) else frappe.as_json(extra)
        except Exception:
            # ignore metadata errors
            pass

        log_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {"status": "success", "name": log_doc.name}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create User Login Log Failed")
        return {"status": "error", "message": str(e)}
