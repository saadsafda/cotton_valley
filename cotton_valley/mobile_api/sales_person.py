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
            ["name", "sales_person_name", "employee", "parent_sales_person"],
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
        
        # User is both an Employee and a Sales Person
        return {
            "status": "success",
            "message": "User is an active employee and sales person",
            "is_employee": True,
            "is_sales_person": True,
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
                "parent_sales_person": sales_person.parent_sales_person
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
