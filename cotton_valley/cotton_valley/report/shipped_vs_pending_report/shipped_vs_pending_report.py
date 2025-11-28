# Copyright (c) 2024, Cotton Valley and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate

def execute(filters=None):
    if not filters:
        filters = {}
        
    # Default to current year if not provided
    if not filters.get("year_filter"):
        filters["year_filter"] = getdate().year

    # 1. Map full month names to numbers and short names for columns
    month_map = {
        "January":   {"num": 1,  "abbr": "Jan"},
        "February":  {"num": 2,  "abbr": "Feb"},
        "March":     {"num": 3,  "abbr": "Mar"},
        "April":     {"num": 4,  "abbr": "Apr"},
        "May":       {"num": 5,  "abbr": "May"},
        "June":      {"num": 6,  "abbr": "Jun"},
        "July":      {"num": 7,  "abbr": "Jul"},
        "August":    {"num": 8,  "abbr": "Aug"},
        "September": {"num": 9,  "abbr": "Sep"},
        "October":   {"num": 10, "abbr": "Oct"},
        "November":  {"num": 11, "abbr": "Nov"},
        "December":  {"num": 12, "abbr": "Dec"}
    }

    # 2. Process the month filter if it exists
    selected_month_data = None
    if filters.get("month_filter"):
        selected_month_data = month_map.get(filters.get("month_filter"))

    # Pass the selected month logic to columns and data
    columns = get_columns(selected_month_data)
    data = get_data(filters, selected_month_data)
    
    return columns, data

def get_columns(selected_month_data):
    columns = [
        {
            "fieldname": "sales_person",
            "label": _("Sales Person"),
            "fieldtype": "Link",
            "options": "Sales Person",
            "width": 150
        }
    ]
    
    # 3. Dynamic Columns: 
    # If a specific month is selected, only show that month. 
    # Otherwise, show all 12 months.
    
    all_months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun", 
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ]
    
    # If a filter is applied, we only want that one month in the columns
    months_to_render = [selected_month_data["abbr"]] if selected_month_data else all_months
    
    for month in months_to_render:
        # Shipped Column
        columns.append({
            "fieldname": f"{month.lower()}_ship",
            "label": _(f"{month} (Shipped)"),
            "fieldtype": "Currency",
            "width": 200
        })
        # Pending Column
        columns.append({
            "fieldname": f"{month.lower()}_pend",
            "label": _(f"{month} (Pending & Processing)"),
            "fieldtype": "Currency",
            "width": 250
        })

    return columns

# ... imports
def get_data(filters, selected_month_data):
    # 1. FETCH FISCAL YEAR DATES
    if filters.get("year_filter"):
        fy_dates = frappe.db.get_value("Fiscal Year", filters.get("year_filter"), ["year_start_date", "year_end_date"], as_dict=True)
        if fy_dates:
            filters["start_date"] = fy_dates.year_start_date
            filters["end_date"] = fy_dates.year_end_date
    
    if "start_date" not in filters:
        filters["start_date"] = "{}-01-01".format(getdate().year)
        filters["end_date"] = "{}-12-31".format(getdate().year)

    # 2. FILTER LOGIC
    month_condition = ""
    if selected_month_data:
        month_num = selected_month_data["num"]
        month_condition = "AND MONTH(so.transaction_date) = {}".format(month_num)

	# --- NEW: Sales Person Filter Logic ---
    sales_person_condition = ""
    if filters.get("sales_person"):
        # We use %(sales_person)s because it automatically pulls the value from the filters dict
        sales_person_condition = "AND so.custom_customer_sales_representative = %(sales_person)s"
    # --------------------------------------

    # 3. BUILD COLUMNS AND TOTALS PREP
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    month_case_statements = ""
    
    for idx, month in enumerate(months, 1):
        key = month.lower()
        month_case_statements += """
            SUM(CASE WHEN MONTH(so.transaction_date) = {idx} AND so.order_status = 'Shipped' THEN so.base_grand_total ELSE 0 END) AS {key}_ship,
            SUM(CASE WHEN MONTH(so.transaction_date) = {idx} AND so.order_status IN ('Pending', 'Processing') THEN so.base_grand_total ELSE 0 END) AS {key}_pend,
        """.format(idx=idx, key=key)

    # 4. QUERY
    query = """
        SELECT
            so.custom_customer_sales_representative AS sales_person,
            {month_case_statements}
            0 as _ignore
        FROM
            `tabSales Order` so
        WHERE
            so.docstatus = 1
            AND so.custom_customer_sales_representative IS NOT NULL
            AND so.custom_customer_sales_representative != ''
            AND so.transaction_date BETWEEN %(start_date)s AND %(end_date)s
            {month_condition} 
			{sales_person_condition}
        GROUP BY
            so.custom_customer_sales_representative
        ORDER BY
            so.custom_customer_sales_representative ASC
    """.format(month_case_statements=month_case_statements, month_condition=month_condition, sales_person_condition=sales_person_condition)
    
    data = frappe.db.sql(query, filters, as_dict=True)
    
    if not data:
        return []

    # 5. CALCULATE TOTAL ROW
    total_row = {
        "sales_person": "Total" # Bold HTML tag for the label
    }

    # Initialize totals
    for month in months:
        m_key = month.lower()
        total_row[f"{m_key}_ship"] = 0.0
        total_row[f"{m_key}_pend"] = 0.0

    # Sum up
    for row in data:
        for month in months:
            m_key = month.lower()
            total_row[f"{m_key}_ship"] += row.get(f"{m_key}_ship") or 0.0
            total_row[f"{m_key}_pend"] += row.get(f"{m_key}_pend") or 0.0

    data.append(total_row)
    
    return data