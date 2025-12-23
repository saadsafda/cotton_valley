import frappe
from frappe.utils import today, fmt_money, now_datetime, format_date, getdate
from frappe.utils.pdf import get_pdf

def execute(filters=None):
    if not filters: filters = {}

    from_date = filters.get("from_date") or today()
    to_date = filters.get("to_date") or today()

    columns = [
        {"fieldname": "order_number", "label": "Sales Order", "fieldtype": "Link", "options": "Sales Order", "width": 180},
        {"fieldname": "customer", "label": "Customer#", "fieldtype": "Link", "options": "Customer", "width": 150},
        {"fieldname": "customer_name", "label": "Customer Name", "fieldtype": "Data", "width": 150},
        {"fieldname": "company", "label": "Company", "fieldtype": "Data", "width": 150},
        {"fieldname": "product_type", "label": "Product Type", "fieldtype": "Data", "width": 120},
        {"fieldname": "from_app", "label": "From App", "fieldtype": "Check", "width": 80}, 
        {"fieldname": "written_by", "label": "Written By", "fieldtype": "Data", "width": 120},
        {"fieldname": "order_status", "label": "Order Status", "fieldtype": "Data", "width": 120}, 
        {"fieldname": "pl", "label": "PL", "fieldtype": "Data", "width": 100},
        {"fieldname": "order_total", "label": "Order Total", "fieldtype": "Currency", "width": 120},
        {"fieldname": "order_case_qty", "label": "Order Case (QTY)", "fieldtype": "Float", "width": 120},
        {"fieldname": "address", "label": "Address", "fieldtype": "Data", "width": 200}
    ]

    conditions = ""
    if filters.get("company"): conditions += " AND company = %(company)s"
    if filters.get("customer"): conditions += " AND customer = %(customer)s"
    if filters.get("sales_order"): conditions += " AND name = %(sales_order)s"

    query = """
        SELECT
            name as order_number,
            customer,
            customer_name,
            company,
            from_app,
            product_type,
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
        ORDER BY company ASC
    """.format(conditions=conditions)

    data = frappe.db.sql(query, filters, as_dict=True)

    return columns, data

@frappe.whitelist()
def send_report_email(filters, recipient_email):
    if isinstance(filters, str):
        filters = frappe.parse_json(filters)
    
    columns, data = execute(filters)

    # 1. Dates Setup
    current_time_str = now_datetime().strftime("%d/%m/%Y, %H:%M")
    report_date_obj = getdate(filters.get('from_date'))
    report_date_str = report_date_obj.strftime("%m/%d/%Y")
    long_date_str = report_date_obj.strftime("%a, %b %d, %Y at 6:30 PM")

    # 2. Data Calculation
    summary_data = {}
    company_list = [] 

    for row in data:
        comp = row.company or "Other"
        
        if comp == "UDC":
            comp = "Universal DC"

        if row.from_app:
            display_source = "App"
        else:
            display_source = "Website"

        p_type = row.product_type 

        if comp not in summary_data:
            summary_data[comp] = {
                "App": {"count": 0, "amount": 0.0}, 
                "Website": {"count": 0, "amount": 0.0},
                "Total": {"count": 0, "amount": 0.0},
                "ProductTypesBreakdown": {}, 
                "ProductTypesTotal": {}      
            }
            company_list.append(comp)

        amount = row.order_total or 0.0
        
        # A. Add to App/Website Bucket
        summary_data[comp][display_source]["count"] += 1
        summary_data[comp][display_source]["amount"] += amount
        
        # B. Add to Product Type Buckets
        if p_type:
            # 1. Breakdown (App/Web separate)
            pt_key = (p_type, display_source)
            if pt_key not in summary_data[comp]["ProductTypesBreakdown"]:
                summary_data[comp]["ProductTypesBreakdown"][pt_key] = {"count": 0, "amount": 0.0}
            summary_data[comp]["ProductTypesBreakdown"][pt_key]["count"] += 1
            summary_data[comp]["ProductTypesBreakdown"][pt_key]["amount"] += amount

            # 2. Product Total (Combined App + Web)
            if p_type not in summary_data[comp]["ProductTypesTotal"]:
                summary_data[comp]["ProductTypesTotal"][p_type] = {"count": 0, "amount": 0.0}
            summary_data[comp]["ProductTypesTotal"][p_type]["count"] += 1
            summary_data[comp]["ProductTypesTotal"][p_type]["amount"] += amount

        # C. Add to Grand Total
        summary_data[comp]["Total"]["count"] += 1
        summary_data[comp]["Total"]["amount"] += amount

    # Sort companies alphabetically
    company_list = sorted(list(set(company_list)))

    # 3. HTML Construction
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Calibri, Arial, sans-serif; font-size: 12px; color: #000; }}
            
            /* Summary Table Styles */
            .summary-table {{ border-collapse: collapse; width: 60%; margin-bottom: 20px; font-size: 11px; }}
            .summary-table th {{ 
                background-color: #FFFF00; 
                border: 1px solid #000; 
                padding: 5px; 
                text-align: left; 
                font-weight: bold;
            }}
            .summary-table td {{ border: 1px solid #000; padding: 5px; }}
            .total-row {{ background-color: #D9D9D9; font-weight: bold; }}

            /* Detail Table Styles */
            .detail-table {{ border-collapse: collapse; width: 100%; font-size: 10px; }}
            .detail-table th {{ background-color: #FFFF00; border: 1px solid #000; padding: 4px; }}
            .detail-table td {{ border: 1px solid #000; padding: 4px; }}
            
            .title-row {{ background-color: #F8CBAD; font-weight: bold; text-align: center; }}
            .right {{ text-align: right; }}
            .center {{ text-align: center; }}
            .bold {{ font-weight: bold; }}
            .logo-text {{ font-family: 'Brush Script MT', cursive; font-size: 24px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <table style="border: none; width: 100%; margin-bottom: 5px;">
            <tr>
                <td style="border: none; width: 20%;">{current_time_str}</td>
                <td style="border: none; text-align: center; font-weight: bold;">Cotton Valley LLC Mail - Order Import Summary</td>
                <td style="border: none; width: 20%;"></td>
            </tr>
        </table>

        <div style="border-bottom: 1px solid #ccc; padding-bottom: 10px; margin-bottom: 15px;">
             <span class="logo-text">Cotton Valley</span> 
        </div>

       
        <br>

        <table class="summary-table">
            <thead>
                <tr>
                    <th>Company Name</th>
                    <th>Order</th>
                    <th>Order Amount</th>
                </tr>
            </thead>
            <tbody>
    """
    
    # --- SECTION 1: ALL APP ROWS (Summary + Breakdown) ---
    for comp in company_list:
        stats = summary_data[comp]
        
        # 1. Main App Summary Row
        if stats["App"]["count"] > 0:
            html_content += f"""
            <tr>
                <td>{comp} (App)</td>
                <td class="center">{stats["App"]["count"]}</td>
                <td class="right">{fmt_money(stats["App"]["amount"])}</td>
            </tr>
            """
            
            # 2. Detailed Breakdown for App (e.g. Regular - App)
            p_breakdown = summary_data[comp]["ProductTypesBreakdown"]
            # Filter only App keys
            app_keys = [k for k in p_breakdown.keys() if k[1] == "App"]
            
            for (p_name, p_source) in sorted(app_keys):
                p_stats = p_breakdown[(p_name, p_source)]
                html_content += f"""
                <tr>
                    <td>{comp} - {p_name} ({p_source})</td>
                    <td class="center">{p_stats["count"]}</td>
                    <td class="right">{fmt_money(p_stats["amount"])}</td>
                </tr>
                """

    # --- SECTION 2: ALL WEBSITE ROWS (Summary + Breakdown) ---
    for comp in company_list:
        stats = summary_data[comp]
        
        # 1. Main Website Summary Row
        if stats["Website"]["count"] > 0:
            html_content += f"""
            <tr>
                <td>{comp} (Website)</td>
                <td class="center">{stats["Website"]["count"]}</td>
                <td class="right">{fmt_money(stats["Website"]["amount"])}</td>
            </tr>
            """
            
            # 2. Detailed Breakdown for Website (e.g. Regular - Website)
            p_breakdown = summary_data[comp]["ProductTypesBreakdown"]
            # Filter only Website keys
            web_keys = [k for k in p_breakdown.keys() if k[1] == "Website"]
            
            for (p_name, p_source) in sorted(web_keys):
                p_stats = p_breakdown[(p_name, p_source)]
                html_content += f"""
                <tr>
                    <td>{comp} - {p_name} ({p_source})</td>
                    <td class="center">{p_stats["count"]}</td>
                    <td class="right">{fmt_money(p_stats["amount"])}</td>
                </tr>
                """

    # --- SECTION 3: ALL TOTALS (Product Combined + Grand Total) ---
    for comp in company_list:
        # 1. Combined Product Totals (e.g. Total Regular)
        p_totals = summary_data[comp]["ProductTypesTotal"]
        for p_name in sorted(p_totals.keys()):
            p_stats = p_totals[p_name]
            if p_stats["count"] > 0:
                html_content += f"""
                <tr class="total-row">
                    <td>Total {comp} - {p_name} Order</td>
                    <td class="center">{p_stats["count"]}</td>
                    <td class="right">{fmt_money(p_stats["amount"])}</td>
                </tr>
                """
        
        # 2. Grand Total
        stats = summary_data[comp]
        html_content += f"""
        <tr class="total-row">
            <td>Total {comp} Order</td>
            <td class="center">{stats['Total']['count']}</td>
            <td class="right">{fmt_money(stats['Total']['amount'])}</td>
        </tr>
        """

    html_content += """
            </tbody>
        </table>
        <br>
    """

    # --- DETAIL TABLE ---
    html_content += f"""
    <table class="detail-table">
        <thead>
            <tr>
                <td colspan="11" class="title-row">
                    Cotton Valley LLC Order Update Summary: {report_date_str}
                </td>
            </tr>
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
            <td class="right">{fmt_money(row.order_total) if row.order_total else '0.00'}</td>
            <td class="center">{row.order_case_qty or 0}</td>
            <td>{row.address or ''}</td>
        </tr>
        """

    html_content += "</tbody></table></body></html>"

    pdf_file = get_pdf(html_content)

    frappe.sendmail(
        recipients=[recipient_email],
        subject=f"Repzio Order Import Summary : {report_date_str}",
        message="Please find the attached Order Summary Report.",
        attachments=[{
            "fname": f"Order_Summary_{report_date_str}.pdf",
            "fcontent": pdf_file
        }],
        now=True
    )

    return "Email Sent Successfully"