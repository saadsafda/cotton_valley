import frappe
from frappe.utils import today, fmt_money

def execute(filters=None):
    if not filters: filters = {}

    # 1. Set Defaults
    from_date = filters.get("from_date") or today()
    to_date = filters.get("to_date") or today()

    # 2. Define Columns
    columns = [
        {"fieldname": "order_number", "label": "Sales Order", "fieldtype": "Link", "options": "Sales Order", "width": 180},
        {"fieldname": "customer", "label": "Customer#", "fieldtype": "Link", "options": "Customer", "width": 150},
        {"fieldname": "customer_name", "label": "Customer Name", "fieldtype": "Data", "width": 150},
        {"fieldname": "company", "label": "Company", "fieldtype": "Data", "width": 150},
        {"fieldname": "written_by", "label": "Written By", "fieldtype": "Data", "width": 120},
        {"fieldname": "order_status", "label": "Order Status", "fieldtype": "Data", "width": 120}, 
        {"fieldname": "pl", "label": "PL", "fieldtype": "Data", "width": 100},
        {"fieldname": "order_total", "label": "Order Total", "fieldtype": "Currency", "width": 120},
        {"fieldname": "order_case_qty", "label": "Order Case (QTY)", "fieldtype": "Float", "width": 120},
        {"fieldname": "address", "label": "Address", "fieldtype": "Data", "width": 200}
    ]

    # 3. Build Dynamic Conditions
    conditions = ""

    # Filter by Company
    if filters.get("company"):
        conditions += " AND company = %(company)s"
    
    # Filter by Customer
    if filters.get("customer"):
        conditions += " AND customer = %(customer)s"

    # Filter by Specific Order Number
    if filters.get("sales_order"):
        conditions += " AND name = %(sales_order)s"

    # 4. Fetch Data with Dynamic Conditions
    # We inject {conditions} directly into the query string
    query = """
        SELECT
            name as order_number,
            customer,
            customer_name,
            company,
            owner as written_by,
            order_status, 
            selling_price_list as pl,
            grand_total as order_total,
            total_qty as order_case_qty,
            shipping_address_name as address
        FROM
            `tabSales Order`
        WHERE
            transaction_date BETWEEN %(from_date)s AND %(to_date)s
            AND docstatus != 2
            {conditions}
    """.format(conditions=conditions)

    data = frappe.db.sql(query, filters, as_dict=True)

    return columns, data


# --- NEW API FUNCTION TO SEND EMAIL ---
@frappe.whitelist()
def send_report_email(filters, recipient_email):
    if isinstance(filters, str):
        filters = frappe.parse_json(filters)
    
    # 1. Fetch Data (Re-using logic)
    columns, data = execute(filters)

    # 2. Build HTML Table (Matching your Excel style)
    html_content = """
    <h3>Order Update Summary</h3>
    <table border="1" style="border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; font-size: 12px;">
        <thead>
            <tr style="background-color: #FFFF00; font-weight: bold;"> <th style="padding: 5px;">Sales Order</th>
                <th style="padding: 5px;">Customer#</th>
                <th style="padding: 5px;">Customer Name</th>
                <th style="padding: 5px;">Company</th>
                <th style="padding: 5px;">Written By</th>
                <th style="padding: 5px;">Order Status</th>
                <th style="padding: 5px;">PL</th>
                <th style="padding: 5px;">Order Total</th>
                <th style="padding: 5px;">Order Case (QTY)</th>
                <th style="padding: 5px;">Address</th>
            </tr>
        </thead>
        <tbody>
    """

    for row in data:
        html_content += f"""
        <tr>
            <td style="padding: 5px;">{row.order_number or ''}</td>
            <td style="padding: 5px;">{row.customer or ''}</td>
            <td style="padding: 5px;">{row.customer_name or ''}</td>
            <td style="padding: 5px;">{row.company or ''}</td>
            <td style="padding: 5px;">{row.written_by or ''}</td>
            <td style="padding: 5px;">{row.order_status or ''}</td>
            <td style="padding: 5px;">{row.pl or ''}</td>
            <td style="padding: 5px;">{fmt_money(row.order_total) if row.order_total else '0.00'}</td>
            <td style="padding: 5px;">{row.order_case_qty or 0}</td>
            <td style="padding: 5px;">{row.address or ''}</td>
        </tr>
        """

    html_content += "</tbody></table>"

    # 3. Send Email
    frappe.sendmail(
        recipients=[recipient_email],
        subject=f"Order Summary Report ({filters.get('from_date')} to {filters.get('to_date')})",
        message=html_content,
        now=True
    )

    return "Email Sent Successfully"