import frappe
from datetime import datetime, timedelta


@frappe.whitelist()
def get_monthly_sales_data():
    """
    Fetch monthly sales data for a current user sales person and current fiscal year.
    """
    """ sales person has employee and employee has user id """
    try:
        user = frappe.session.user
        employee = frappe.get_all("Employee", filters={"user_id": user}, fields=["name"], pluck="name")
        if not employee:
            return {
                "status": "error",
                "message": "No Employee found for the current user.",
                "data": []
            }
        employee_name = employee[0]
        sales_person = frappe.get_all("Sales Person", filters={"employee": employee_name}, fields=["name"], pluck="name")
        if not sales_person:
            return {
                "status": "error",
                "message": "No Sales Person found for the current employee.",
                "data": []
            }
        sales_person_name = sales_person[0]
        sales_person = frappe.get_doc("Sales Person", sales_person_name)
        fiscal_year = frappe.db.get_value("Fiscal Year", {"disabled": 0}, "name")
        if not fiscal_year:
            return {
                "status": "error",
                "message": "No default Fiscal Year found.",
                "data": []
            }
        for ms in sales_person.sales_scheduler:
            if ms.fiscal_year == fiscal_year:
                monthly_sales = frappe.get_doc("Monthly Sales", ms.monthly_sales)
                sales_target = monthly_sales.sales_target
                if len(sales_target) == 0:
                    return {
                        "status": "success",
                        "message": "No sales target data found for the current fiscal year.",
                        "data": {
                            "actualData": [],
                            "targetData": [],
                            "months": []
                        }
                    }
                
                # Month abbreviations mapping
                month_abbr = {
                    "January": "Jan", "February": "Feb", "March": "Mar",
                    "April": "Apr", "May": "May", "June": "Jun",
                    "July": "Jul", "August": "Aug", "September": "Sep",
                    "October": "Oct", "November": "Nov", "December": "Dec"
                }
                
                # Get fiscal year dates for filtering
                fiscal_year_doc = frappe.get_doc("Fiscal Year", fiscal_year)
                year_start_date = fiscal_year_doc.year_start_date
                year_end_date = fiscal_year_doc.year_end_date
                print(year_start_date, year_end_date, "================")
                # Fetch actual sales from Sales Orders for this sales person
                actual_sales_by_month = {}
                sales_orders = frappe.db.sql("""
                    SELECT 
                        MONTHNAME(so.transaction_date) as month,
                        SUM(so.grand_total) as total_sales
                    FROM `tabSales Order` so
                    WHERE so.custom_customer_sales_representative = %s
                        AND so.docstatus = 1
                        AND so.transaction_date BETWEEN %s AND %s
                    GROUP BY MONTHNAME(so.transaction_date)
                """, (sales_person_name, year_start_date, year_end_date), as_dict=True)
                
                # Create a map of month -> actual sales
                for sale in sales_orders:
                    actual_sales_by_month[sale.month] = float(sale.total_sales or 0)
                
                # Get total customers for this sales person
                total_customers = frappe.db.count("Customer", {
                    "sales_person": sales_person_name,
                    "disabled": 0
                })
                
                # Get active customers (ordered in last 90 days)
                ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
                active_customers_result = frappe.db.sql("""
                    SELECT COUNT(DISTINCT so.customer) as active_count
                    FROM `tabSales Order` so
                    WHERE so.custom_customer_sales_representative = %s
                        AND so.docstatus = 1
                        AND so.transaction_date >= %s
                """, (sales_person_name, ninety_days_ago), as_dict=True)
                
                active_customers = active_customers_result[0].active_count if active_customers_result else 0
                
                # Prepare data arrays
                actual_data = []
                target_data = []
                months = []
                
                # Get current month name
                current_month_name = datetime.now().strftime("%B")  # e.g., "October"
                current_month_goal = 0
                current_month_value = 0
                
                for target in sales_target:
                    # Add month abbreviation
                    months.append(month_abbr.get(target.month, target.month[:3]))
                    
                    # Add target amount
                    target_amount = float(target.target_amount or 0)
                    target_data.append(target_amount)
                    
                    # Add actual sales amount from Sales Orders
                    actual_amount = actual_sales_by_month.get(target.month, 0)
                    actual_data.append(actual_amount)
                    
                    # Check if this is the current month
                    if target.month == current_month_name:
                        current_month_goal = target_amount
                        current_month_value = actual_amount
                
                return {
                    "status": "success",
                    "message": "Monthly sales data fetched successfully",
                    "data": {
                        "actualData": actual_data,
                        "targetData": target_data,
                        "months": months,
                        "current_month_goal": current_month_goal,
                        "current_month_value": current_month_value,
                        "total_customers": total_customers,
                        "active_customers": active_customers
                    }
                }
        
        # If no matching fiscal year found
        return {
            "status": "error",
            "message": "No sales data found for the current fiscal year.",
            "data": {
                "actualData": [],
                "targetData": [],
                "months": []
            }
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Monthly Sales Data Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "status": "error",
            "message": f"An error occurred: {str(e)}",
            "data": {
                "actualData": [],
                "targetData": [],
                "months": []
            }
        }