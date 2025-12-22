import frappe
from frappe.utils import today, fmt_money
from frappe.utils.pdf import get_pdf

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

    # 2. Calculate Summary (Grouping by Company)
    summary_map = {}
    for row in data:
        comp = row.company or "Other"
        if comp not in summary_map:
            summary_map[comp] = {"count": 0, "amount": 0.0}
        
        summary_map[comp]["count"] += 1
        summary_map[comp]["amount"] += (row.order_total or 0.0)

    # 3. Build HTML for PDF
    # Styles for clear PDF formatting
    html_content = """
    <html>
    <head>
       <style>
            body { font-family: Arial, sans-serif; font-size: 11px; }
            h3 { margin-bottom: 5px; margin-top: 15px; }
            /* Global Table Styles */
            table { border-collapse: collapse; border: 1px solid black; }
            th, td { border: 1px solid black; padding: 5px; }
            th { font-weight: bold; text-align: left; }
            
            /* Specific Widths */
            .summary-table { width: 60%; margin-bottom: 20px; }
            .detail-table { width: 100%; }
        </style>
    </head>
    <body>
        <h2>Order Update Summary</h2>
    """

    # --- PART A: SUMMARY TABLE ---
    html_content += """
    <h3>Company Summary</h3>
    <table class="summary-table" border="1" cellspacing="0" cellpadding="5">
        <thead>
            <tr>
                <th>Company Name</th>
                <th>Order (Qty)</th>
                <th>Order Amount</th>
            </tr>
        </thead>
        <tbody>
    """
    
    total_orders = 0
    total_amount = 0.0

    for comp, stats in summary_map.items():
        html_content += f"""
        <tr>
            <td>{comp}</td>
            <td>{stats['count']}</td>
            <td>{fmt_money(stats['amount'])}</td>
        </tr>
        """
        total_orders += stats['count']
        total_amount += stats['amount']

    # Summary Totals Row
    html_content += f"""
        <tr style="background-color: #f0f0f0; font-weight: bold;">
            <td>Total</td>
            <td>{total_orders}</td>
            <td>{fmt_money(total_amount)}</td>
        </tr>
    </tbody></table>
    """

    # --- PART B: DETAILED TABLE ---
    html_content += """
    <h3>Detailed Orders</h3>
    <table class="detail-table" border="1" cellspacing="0" cellpadding="5">
        <thead>
            <tr>
                <th>Sales Order</th>
                <th>Customer#</th>
                <th>Customer Name</th>
                <th>Company</th>
                <th>Written By</th>
                <th>Order Status</th>
                <th>PL</th>
                <th>Order Total</th>
                <th>Case QTY</th>
                <th>Address</th>
            </tr>
        </thead>
        <tbody>
    """

    for row in data:
        html_content += f"""
        <tr>
            <td>{row.order_number or ''}</td>
            <td>{row.customer or ''}</td>
            <td>{row.customer_name or ''}</td>
            <td>{row.company or ''}</td>
            <td>{row.written_by or ''}</td>
            <td>{row.order_status or ''}</td>
            <td>{row.pl or ''}</td>
            <td>{fmt_money(row.order_total) if row.order_total else '0.00'}</td>
            <td>{row.order_case_qty or 0}</td>
            <td>{row.address or ''}</td>
        </tr>
        """

    html_content += "</tbody></table></body></html>"

    # 4. Generate PDF
    pdf_file = get_pdf(html_content)

    # 5. Send Email with Attachment
    frappe.sendmail(
        recipients=[recipient_email],
        subject=f"Order Summary Report ({filters.get('from_date')} to {filters.get('to_date')})",
        message="Please find the attached Order Summary Report (PDF).",
        attachments=[{
            "fname": "Order_Summary.pdf",
            "fcontent": pdf_file
        }],
        now=True
    )

    return "Email Sent Successfully"