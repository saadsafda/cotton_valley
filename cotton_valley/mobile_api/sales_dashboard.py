import frappe
from datetime import datetime, timedelta
from frappe.utils import nowdate
from erpnext.accounts.utils import get_fiscal_year



@frappe.whitelist(allow_guest=False)
def get_sales_achievement(fiscal_year=None, item_group=None, product_category=None):
    """
    Retrieves the total *achieved* sales, grouped by MONTH and PRODUCT CATEGORY,
    for the logged-in user's Sales Person.

    This version joins the Item's child table for categories.
    """

    # ---
    # !! ACTION REQUIRED: SET THESE PLACEHOLDERS !!
    # ---
    # 1. The DocType name of the child table in `Item` (e.g., "Item Category")
    ITEM_CATEGORY_DOCTYPE = "Product Categoris"
    
    # 2. The field name in that child table that links to `Product Category` (e.g., "category")
    CATEGORY_FIELDNAME = "product_category"
    # ---
    
    # 1. Get the Sales Person for the current user
    user = frappe.session.user
    employee = frappe.get_all("Employee", filters={"user_id": user}, fields=["name"], pluck="name")
    if not employee:
        return {"status": "error", "message": "No Employee found for the current user."}
    
    employee_name = employee[0]
    sales_person = frappe.get_all("Sales Person", filters={"employee": employee_name}, fields=["name"], pluck="name")
    if not sales_person:
        return {"status": "error", "message": "No Sales Person found for the current employee."}
    
    sales_person_name = sales_person[0]

    # 2. Get Fiscal Year start and end dates
    if not fiscal_year:
        fiscal_year = frappe.db.get_value("Fiscal Year", {"disabled": 0}, "name")
        if not fiscal_year:
            frappe.throw("No active Fiscal Year found.")
            
    fy_doc = frappe.get_doc("Fiscal Year", fiscal_year)
    start_date = fy_doc.year_start_date
    end_date = fy_doc.year_end_date
    
    # 3. Get Target Categories for Scaffolding (from your get_monthly_targets logic)
    target_filter_dict = {
        "parenttype": "Sales Person",
        "parent": sales_person_name,
        "fiscal_year": fiscal_year,
    }
    if item_group:
        target_filter_dict["item_group"] = item_group
    if product_category:
        target_filter_dict["product_category"] = product_category

    target_categories_list = frappe.get_all(
        "Target Detail", # This is the DocType for your sales targets
        filters=target_filter_dict,
        fields=["product_category"],
        distinct=True,
        pluck="product_category"
    )
    all_categories = set(c for c in target_categories_list if c)

    # 4. Build the SQL Query
    # This query joins the item's category child table
    query = f"""
        SELECT
            MONTHNAME(si.posting_date) as month,
            ic.{CATEGORY_FIELDNAME} as product_category,
            SUM(sii.base_amount) as achieved_amount
        FROM
            `tabSales Invoice` as si,
            `tabSales Invoice Item` as sii,
            `tab{ITEM_CATEGORY_DOCTYPE}` as ic
        WHERE
            si.name = sii.parent
            AND sii.item_code = ic.parent  -- Join invoice item to item category table
            AND si.docstatus = 1
            AND si.posting_date BETWEEN %(start_date)s AND %(end_date)s
            
            -- Subquery to filter by Sales Person
            AND si.name IN (
                SELECT st.parent
                FROM `tabSales Team` as st
                WHERE st.sales_person = %(sales_person)s
            )
    """
    
    filters = {
        "sales_person": sales_person_name,
        "start_date": start_date,
        "end_date": end_date
    }
    
    if item_group:
        query += " AND sii.item_group = %(item_group)s"
        filters["item_group"] = item_group
        
    if product_category:
        # Filter on the joined child table's category field
        query += f" AND ic.{CATEGORY_FIELDNAME} = %(product_category)s"
        filters["product_category"] = product_category

    query += f"""
        GROUP BY
            MONTH(si.posting_date), MONTHNAME(si.posting_date),
            ic.{CATEGORY_FIELDNAME}
        ORDER BY
            ic.{CATEGORY_FIELDNAME}, MONTH(si.posting_date)
    """
    
    achieved_data = frappe.db.sql(query, filters, as_dict=True)
    
    # 5. Format the data (This logic is the same as before)
    MONTHS = ["January", "February", "March", "April", "May", "June", 
              "July", "August", "September", "October", "November", "December"]
    
    achieved_map = {}
    for d in achieved_data:
        cat = d.product_category or "Uncategorized"
        achieved_map[(d.month, cat)] = d.achieved_amount
        if cat not in all_categories:
            all_categories.add(cat)

    final_achievements = []
    for category in sorted(list(all_categories)):
        for month in MONTHS:
            key = (month, category)
            amount = achieved_map.get(key, 0.0)
            
            final_achievements.append({
                "month": month,
                "product_category": category,
                "achieved_amount": amount
            })

    if not final_achievements and not product_category and not item_group:
        for month in MONTHS:
            final_achievements.append({
                "month": month,
                "product_category": None,
                "achieved_amount": 0.0
            })

    return {"achievements": final_achievements}

@frappe.whitelist(allow_guest=False)
def get_monthly_targets(item_group=None, product_category=None):
    """
    Retrieves monthly *planned* target distribution for a given Sales Person and Fiscal Year.
    """
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
    sales_person_doc = frappe.get_doc("Sales Person", sales_person_name) # <-- CHANGED: Need the doc

    fiscal_year = frappe.db.get_value("Fiscal Year", {"disabled": 0}, "name")

    if not sales_person_doc or not fiscal_year:
        frappe.throw("Sales Person and Fiscal Year are mandatory.")

    # 1. Build the main query filters
    filters = {
        "parenttype": "Sales Person",
        "parent": sales_person_doc.name, 
        "fiscal_year": fiscal_year,
    }

    if item_group:
        filters["item_group"] = item_group
    if product_category:
        filters["product_category"] = product_category

    group_key_field = ""
    if item_group:
        group_key_field = "item_group"
    elif product_category:
        group_key_field = "product_category"

    # 2. Fetch all matching target records
    # ASSUMPTION: Your child table DocType is named Target Detail"
    # based on the screenshot and convention.
    target_items = frappe.get_all(
        "Target Detail",
        filters=filters,
        fields=["name", "item_group", "product_category", "target_amount", "target_qty", "distribution_id"],
        order_by="idx asc"
    )

    print(target_items, filters, "=================target_items")

    if not target_items:
        return {"targets": []}

    aggregated_targets = {}
    aggregated_qtys = {}
    MONTHS = ["January", "February", "March", "April", "May", "June", 
              "July", "August", "September", "October", "November", "December"]

    # 3. Iterate through each matching target and retrieve its distribution
    for target_item in target_items:
        
        # This is the total target amount for this specific row (e.g., $100,000)
        base_target_amount = target_item.target_amount or 0.0
        base_target_qty = target_item.target_qty or 0.0
        
        # Check if a distribution ID is set
        if not target_item.distribution_id:
            continue

        distribution_details = frappe.get_all(
            "Monthly Distribution Percentage", 
            # <-- CHANGED: Link field is 'distribution_id' from screenshot
            filters={"parent": target_item.distribution_id}, 
            fields=["month", "percentage_allocation"] 
        )

        for detail in distribution_details:
            month = detail.month
            percentage = detail.percentage_allocation or 0.0
            
            # <-- CHANGED: Calculate the *actual amount* for the month
            monthly_target_amount = base_target_amount * (percentage / 100.0)
            monthly_target_qty = base_target_qty * (percentage / 100.0)

            group_value = "All Targets"
            if group_key_field:
                group_value = target_item.get(group_key_field)

            key = (month, group_value)
            
            # <-- CHANGED: Aggregate the calculated monetary amount
            aggregated_targets[key] = aggregated_targets.get(key, 0.0) + monthly_target_amount
            aggregated_qtys[key] = aggregated_qtys.get(key, 0.0) + monthly_target_qty

    # 4. Format the final output structure (This part was correct)
    final_targets = []
    unique_groups = sorted(list(set([k[1] for k in aggregated_targets.keys()])))

    for group in unique_groups:
        group_data = {
            "group_type": group_key_field or "All",
            "group_value": group,
            "monthly_targets": []
        }
        
        for month in MONTHS:
            key = (month, group)
            amount = aggregated_targets.get(key, 0.0)
            qty = aggregated_qtys.get(key, 0.0)
            
            group_data["monthly_targets"].append({
                "month": month,
                "target_amount": amount,
                "target_qty": qty
            })
            
        final_targets.append(group_data)

    return {"targets": final_targets}






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
                target_qty_data = []
                months = []
                
                # Get current month name
                current_month_name = datetime.now().strftime("%B")  # e.g., "October"
                current_month_goal = 0
                current_month_goal_qty = 0
                current_month_value = 0
                
                for target in sales_target:
                    # Add month abbreviation
                    months.append(month_abbr.get(target.month, target.month[:3]))
                    
                    # Add target amount
                    target_amount = float(target.target_amount or 0)
                    target_qty = float(getattr(target, 'target_qty', 0) or 0)
                    target_data.append(target_amount)
                    target_qty_data.append(target_qty)
                    
                    # Add actual sales amount from Sales Orders
                    actual_amount = actual_sales_by_month.get(target.month, 0)
                    actual_data.append(actual_amount)
                    
                    # Check if this is the current month
                    if target.month == current_month_name:
                        current_month_goal = target_amount
                        current_month_goal_qty = target_qty
                        current_month_value = actual_amount
                
                return {
                    "status": "success",
                    "message": "Monthly sales data fetched successfully",
                    "data": {
                        "actualData": actual_data,
                        "targetData": target_data,
                        "targetQtyData": target_qty_data,
                        "months": months,
                        "current_month_goal": current_month_goal,
                        "current_month_goal_qty": current_month_goal_qty,
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
    

@frappe.whitelist()
def get_monthly_data():
    # --- 1. Get Sales Person (Same as your code) ---
    user = frappe.session.user
    employee = frappe.get_all("Employee", filters={"user_id": user}, fields=["name"], pluck="name")
    if not employee:
        # FİX: Return the requested format, but empty
        return { 'actualData': [], 'targetData': [], 'months': [] }
        
    employee_name = employee[0]
    sales_person = frappe.get_all("Sales Person", filters={"employee": employee_name}, fields=["name"], pluck="name")
    if not sales_person:
        # FİX: Return the requested format, but empty
        return { 'actualData': [], 'targetData': [], 'months': [] }

    sales_person_name = sales_person[0]
    
    # --- 2. Get Fiscal Year Dates (Same as your code) ---
    current_fiscal_year = get_fiscal_year(nowdate())[0]
    fy_dates = frappe.db.get_value("Fiscal Year", current_fiscal_year, ["year_start_date", "year_end_date"], as_dict=True)
    
    if not fy_dates:
        frappe.throw(f"Fiscal Year {current_fiscal_year} not found.")

    query_params = {
        "user": sales_person_name,
        "fiscal_year": current_fiscal_year,
        "fy_start_date": fy_dates.year_start_date,
        "fy_end_date": fy_dates.year_end_date
    }

    # --- 3. Run the SQL Query (Slightly optimized) ---
    # I've simplified the final SELECT to get only what's needed.
    query_results = frappe.db.sql("""
        WITH MonthlyTargets AS (
            SELECT
                dist_pct.month,
                sp_target.fiscal_year,
                SUM(sp_target.target_amount * (dist_pct.percentage_allocation / 100)) AS monthly_target,
                SUM(sp_target.target_qty * (dist_pct.percentage_allocation / 100)) AS monthly_target_qty
            FROM
                `tabTarget Detail` AS sp_target
            JOIN
                `tabMonthly Distribution Percentage` AS dist_pct ON sp_target.distribution_id = dist_pct.parent
            WHERE
                sp_target.parent = %(user)s 
                AND sp_target.fiscal_year = %(fiscal_year)s
            GROUP BY
                dist_pct.month, sp_target.fiscal_year
        ),
        
        MonthlyAchieved AS (
            SELECT
                MONTHNAME(si.posting_date) AS month,
                SUM(sii.net_amount * (st.allocated_percentage / 100)) AS achieved_amount
            FROM
                `tabSales Invoice` AS si
            JOIN
                `tabSales Invoice Item` AS sii ON si.name = sii.parent
            JOIN
                `tabSales Team` AS st ON si.name = st.parent
            WHERE
                si.docstatus = 1
                AND st.sales_person = %(user)s
                AND si.posting_date BETWEEN %(fy_start_date)s AND %(fy_end_date)s
            GROUP BY
                MONTHNAME(si.posting_date)
        )

        -- Final step: Combine and select only the 3 columns we need
        SELECT
            CombinedData.month AS "Month",
            SUM(CombinedData.monthly_target) AS "Target Amount",
            SUM(CombinedData.monthly_target_qty) AS "Target Qty",
            SUM(CombinedData.achieved_amount) AS "Achieved Amount"
        FROM (
            SELECT
                month, fiscal_year,
                monthly_target, monthly_target_qty, 0 AS achieved_amount
            FROM
                MonthlyTargets
            UNION ALL
            SELECT
                month, 
                %(fiscal_year)s AS fiscal_year,
                0 AS monthly_target, 
                0 AS monthly_target_qty, 
                achieved_amount
            FROM
                MonthlyAchieved
        ) AS CombinedData
        GROUP BY
            CombinedData.month, CombinedData.fiscal_year
        ORDER BY
            CombinedData.fiscal_year,
            FIELD(CombinedData.month, 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December');
    """, query_params, as_dict=True)

    # --- 4. Transform the Data (NEW SECTION) ---
    if not query_results:
        return { 'actualData': [], 'targetData': [], 'targetQtyData': [], 'months': [] }

    # Use list comprehensions to create the arrays
    months = [row["Month"] for row in query_results]
    actualData = [row["Achieved Amount"] for row in query_results]
    targetData = [row["Target Amount"] for row in query_results]
    targetQtyData = [row["Target Qty"] for row in query_results]

    # Return the final dictionary in your requested format
    return {
        'actualData': actualData,
        'targetData': targetData,
        'targetQtyData': targetQtyData,
        'months': months,
    }




@frappe.whitelist()
def get_category_wise_monthly_data():
    """
    Monthly target vs achieved per Target Detail row, including the
    Product Category, Product Subcategory and Item set on each target row.

    A Target Detail row may be at one of three levels of specificity:
      - Item       (item_code set)
      - Subcategory (product_subcategory set, item_code blank)
      - Category   (only product_category set)

    Achieved sales are matched at the same level so the comparison stays
    consistent with how the target was defined:
      - Item level       -> Sales Invoice Item where item_code matches.
      - Subcategory level -> Items whose Item.custom_sub_category matches.
      - Category level    -> Items linked via the Product Categoris child
        table (custom_product_categories on Item).
    """

    # 1) Resolve sales person from the logged-in user.
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

    # 2) Current fiscal year + its date range.
    current_fiscal_year = get_fiscal_year(nowdate())[0]
    fy_dates = frappe.db.get_value(
        "Fiscal Year", current_fiscal_year,
        ["year_start_date", "year_end_date"], as_dict=True
    )
    if not fy_dates:
        frappe.throw(f"Fiscal Year {current_fiscal_year} not found.")

    params = {
        "user": sales_person_name,
        "fiscal_year": current_fiscal_year,
        "fy_start_date": fy_dates.year_start_date,
        "fy_end_date": fy_dates.year_end_date,
    }

    # 3) Monthly targets at (category, subcategory, item, month) granularity.
    targets = frappe.db.sql("""
        SELECT
            sp_target.product_category    AS product_category,
            sp_target.category_name       AS category_name,
            sp_target.product_subcategory AS product_subcategory,
            sp_target.subcategory_name    AS subcategory_name,
            sp_target.item_code           AS item_code,
            sp_target.item_name           AS item_name,
            dist_pct.month                AS month,
            SUM(sp_target.target_amount * (dist_pct.percentage_allocation / 100)) AS monthly_target,
            SUM(sp_target.target_qty * (dist_pct.percentage_allocation / 100)) AS monthly_target_qty
        FROM `tabTarget Detail` AS sp_target
        JOIN `tabMonthly Distribution Percentage` AS dist_pct
            ON sp_target.distribution_id = dist_pct.parent
        WHERE sp_target.parent = %(user)s
          AND sp_target.fiscal_year = %(fiscal_year)s
        GROUP BY
            sp_target.product_category,
            sp_target.product_subcategory,
            sp_target.item_code,
            dist_pct.month
    """, params, as_dict=True)

    # 4) Achieved at item level (most specific).
    achieved_by_item = frappe.db.sql("""
        SELECT
            sii.item_code               AS item_code,
            MONTHNAME(si.posting_date)  AS month,
            SUM(sii.net_amount * (st.allocated_percentage / 100)) AS achieved_amount
        FROM `tabSales Invoice` AS si
        JOIN `tabSales Invoice Item` AS sii ON si.name = sii.parent
        JOIN `tabSales Team`         AS st  ON si.name = st.parent
        WHERE si.docstatus = 1
          AND st.sales_person = %(user)s
          AND si.posting_date BETWEEN %(fy_start_date)s AND %(fy_end_date)s
        GROUP BY sii.item_code, MONTHNAME(si.posting_date)
    """, params, as_dict=True)

    # 5) Achieved at subcategory level (Item.custom_sub_category).
    achieved_by_subcat = frappe.db.sql("""
        SELECT
            it.custom_sub_category      AS product_subcategory,
            MONTHNAME(si.posting_date)  AS month,
            SUM(sii.net_amount * (st.allocated_percentage / 100)) AS achieved_amount
        FROM `tabSales Invoice` AS si
        JOIN `tabSales Invoice Item` AS sii ON si.name = sii.parent
        JOIN `tabSales Team`         AS st  ON si.name = st.parent
        JOIN `tabItem`               AS it  ON it.name  = sii.item_code
        WHERE si.docstatus = 1
          AND st.sales_person = %(user)s
          AND si.posting_date BETWEEN %(fy_start_date)s AND %(fy_end_date)s
          AND it.custom_sub_category IS NOT NULL
          AND it.custom_sub_category <> ''
        GROUP BY it.custom_sub_category, MONTHNAME(si.posting_date)
    """, params, as_dict=True)

    # 6) Achieved at category level (via Product Categoris child table on Item).
    achieved_by_category = frappe.db.sql("""
        SELECT
            ipc.product_category        AS product_category,
            MONTHNAME(si.posting_date)  AS month,
            SUM(sii.net_amount * (st.allocated_percentage / 100)) AS achieved_amount
        FROM `tabSales Invoice` AS si
        JOIN `tabSales Invoice Item` AS sii ON si.name = sii.parent
        JOIN `tabSales Team`         AS st  ON si.name = st.parent
        JOIN `tabProduct Categoris`  AS ipc ON ipc.parent = sii.item_code
                                            AND ipc.parenttype = 'Item'
        WHERE si.docstatus = 1
          AND st.sales_person = %(user)s
          AND si.posting_date BETWEEN %(fy_start_date)s AND %(fy_end_date)s
        GROUP BY ipc.product_category, MONTHNAME(si.posting_date)
    """, params, as_dict=True)

    # 7) Build lookup maps once.
    item_map = {
        (r.item_code, r.month): float(r.achieved_amount or 0)
        for r in achieved_by_item
    }
    subcat_map = {
        (r.product_subcategory, r.month): float(r.achieved_amount or 0)
        for r in achieved_by_subcat
    }
    category_map = {
        (r.product_category, r.month): float(r.achieved_amount or 0)
        for r in achieved_by_category
    }

    # 8) Build a nested structure:
    #    Month + Category  ->  subcategories[]  ->  items[]
    #
    # Aggregation rules per category row:
    #   - The "Level" of the category row is the deepest level any of its
    #     target rows used (Item > Subcategory > Category).
    #   - Category Target/Achieved = sum of all its subcategory rows.
    #   - Subcategory Target/Achieved = sum of all its item rows
    #     (or the subcategory's own target/achieved when no items below).
    #
    # We use a dict keyed by (month, category) -> dict keyed by subcategory
    # -> dict keyed by item, so duplicate target rows at the same level are
    # naturally merged.
    LEVEL_RANK = {"Category": 1, "Subcategory": 2, "Item": 3}
    grouped = {}  # (month, category) -> category_node

    for t in targets:
        target_amt = float(t.monthly_target or 0)
        target_qty = float(t.monthly_target_qty or 0)

        # The level this individual target row was set at.
        if t.item_code:
            row_level = "Item"
            row_achieved = item_map.get((t.item_code, t.month), 0.0)
        elif t.product_subcategory:
            row_level = "Subcategory"
            row_achieved = subcat_map.get((t.product_subcategory, t.month), 0.0)
        else:
            row_level = "Category"
            row_achieved = category_map.get((t.product_category, t.month), 0.0)

        cat_key = (t.month, t.product_category)
        cat_node = grouped.get(cat_key)
        if cat_node is None:
            cat_node = {
                "Sales Person": sales_person_name,
                "Month": t.month,
                "Fiscal Year": current_fiscal_year,
                "Level": row_level,
                "Product Category": t.product_category,
                "Category Name": t.category_name,
                "subcategories": {},  # temp dict, converted to list at the end
                "Target Amount": 0.0,
                "Target Qty": 0.0,
                "Achieved Amount": 0.0,
            }
            grouped[cat_key] = cat_node
        else:
            # Track the deepest level seen for this category in this month.
            if LEVEL_RANK[row_level] > LEVEL_RANK[cat_node["Level"]]:
                cat_node["Level"] = row_level

        # Subcategory bucket. Use empty string as the key for "no subcategory"
        # so category-level targets still appear in the structure.
        sub_key = t.product_subcategory or ""
        sub_node = cat_node["subcategories"].get(sub_key)
        if sub_node is None:
            sub_node = {
                "Product Subcategory": t.product_subcategory,
                "Subcategory Name": t.subcategory_name,
                "Target Amount": 0.0,
                "Target Qty": 0.0,
                "Achieved Amount": 0.0,
                "items": {},  # temp dict, converted to list at the end
            }
            cat_node["subcategories"][sub_key] = sub_node

        if row_level == "Item":
            # Item-level target: nest under its subcategory.
            item_key = t.item_code
            item_node = sub_node["items"].get(item_key)
            if item_node is None:
                item_node = {
                    "Item Code": t.item_code,
                    "Item Name": t.item_name,
                    "Target Amount": 0.0,
                    "Target Qty": 0.0,
                    "Achieved Amount": 0.0,
                }
                sub_node["items"][item_key] = item_node
            item_node["Target Amount"] += target_amt
            item_node["Target Qty"] += target_qty
            item_node["Achieved Amount"] += row_achieved
            sub_node["Target Amount"] += target_amt
            sub_node["Target Qty"] += target_qty
            sub_node["Achieved Amount"] += row_achieved
            cat_node["Target Amount"] += target_amt
            cat_node["Target Qty"] += target_qty
            cat_node["Achieved Amount"] += row_achieved
        elif row_level == "Subcategory":
            # Subcategory-level target with no specific item.
            sub_node["Target Amount"] += target_amt
            sub_node["Target Qty"] += target_qty
            sub_node["Achieved Amount"] += row_achieved
            cat_node["Target Amount"] += target_amt
            cat_node["Target Qty"] += target_qty
            cat_node["Achieved Amount"] += row_achieved
        else:
            # Category-level target.
            sub_node["Target Amount"] += target_amt
            sub_node["Target Qty"] += target_qty
            sub_node["Achieved Amount"] += row_achieved
            cat_node["Target Amount"] += target_amt
            cat_node["Target Qty"] += target_qty
            cat_node["Achieved Amount"] += row_achieved

    # 9) Convert the nested dicts to the final list-of-dicts shape and sort.
    month_order = {m: i for i, m in enumerate([
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ])}

    result = []
    for cat_node in grouped.values():
        sub_list = []
        for sub_node in cat_node["subcategories"].values():
            items_list = sorted(
                sub_node["items"].values(),
                key=lambda it: (it["Item Name"] or it["Item Code"] or ""),
            )
            sub_node["items"] = items_list
            sub_list.append(sub_node)

        sub_list.sort(
            key=lambda s: (s["Subcategory Name"] or s["Product Subcategory"] or "")
        )
        cat_node["subcategories"] = sub_list
        cat_node["Variance"] = cat_node["Achieved Amount"] - cat_node["Target Amount"]
        result.append(cat_node)

    result.sort(key=lambda r: (
        r["Product Category"] or "",
        month_order.get(r["Month"], 99),
    ))

    return result

