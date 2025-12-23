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

    # 2. Data Calculation (Specific Buckets for 1-9 Order)
    # Hum pehle saare variables 0 set kar denge
    stats = {
        "cv_app": {"count": 0, "amount": 0.0},       # 1. Cotton Valley (App)
        "cv_web": {"count": 0, "amount": 0.0},       # 4. Cotton Valley (Website)
        
        "udc_reg_app": {"count": 0, "amount": 0.0},  # 2. Universal DC - REG (App)
        "udc_reg_web": {"count": 0, "amount": 0.0},  # 5. Universal DC - REG (Website)
        
        "udc_cod_app": {"count": 0, "amount": 0.0},  # 3. Universal DC - COD (App)
        "udc_cod_web": {"count": 0, "amount": 0.0},  # 6. Universal DC - COD (Website)
    }

    for row in data:
        amount = row.order_total or 0.0
        
        # Check Company Name
        company_name = (row.company or "").lower()
        if "cotton" in company_name:
            # Logic for Cotton Valley
            if row.from_app:
                stats["cv_app"]["count"] += 1
                stats["cv_app"]["amount"] += amount
            else:
                stats["cv_web"]["count"] += 1
                stats["cv_web"]["amount"] += amount

        elif "universal" in company_name or "udc" in company_name:
            # Logic for Universal DC
            p_type = (row.product_type or "").upper() # REG or COD check karne ke liye
            
            if "REG" in p_type:
                if row.from_app:
                    stats["udc_reg_app"]["count"] += 1
                    stats["udc_reg_app"]["amount"] += amount
                else:
                    stats["udc_reg_web"]["count"] += 1
                    stats["udc_reg_web"]["amount"] += amount
            elif "COD" in p_type:
                if row.from_app:
                    stats["udc_cod_app"]["count"] += 1
                    stats["udc_cod_app"]["amount"] += amount
                else:
                    stats["udc_cod_web"]["count"] += 1
                    stats["udc_cod_web"]["amount"] += amount

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

        <div>
            <strong>Repzio Cotton Valley</strong> &lt;repzio@cottonvalley.net&gt;<br>
            To: Orders &lt;orders@cottonvalley.net&gt;<br>
            <span style="color:#777">{long_date_str}</span>
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
    
    # --- EXACT ROW ORDER 1 to 9 ---

    # 1. Cotton Valley LLC (App)
    html_content += f"""
        <tr>
            <td>Cotton Valley LLC (App)</td>
            <td class="center">{stats['cv_app']['count']}</td>
            <td class="right">{fmt_money(stats['cv_app']['amount'])}</td>
        </tr>
    """

    # 2. Universal DC - REG (App)
    html_content += f"""
        <tr>
            <td>Universal DC - REG (App)</td>
            <td class="center">{stats['udc_reg_app']['count']}</td>
            <td class="right">{fmt_money(stats['udc_reg_app']['amount'])}</td>
        </tr>
    """

    # 3. Universal DC - COD (App)
    html_content += f"""
        <tr>
            <td>Universal DC - COD (App)</td>
            <td class="center">{stats['udc_cod_app']['count']}</td>
            <td class="right">{fmt_money(stats['udc_cod_app']['amount'])}</td>
        </tr>
    """

    # 4. Cotton Valley LLC (Website)
    html_content += f"""
        <tr>
            <td>Cotton Valley LLC (Website)</td>
            <td class="center">{stats['cv_web']['count']}</td>
            <td class="right">{fmt_money(stats['cv_web']['amount'])}</td>
        </tr>
    """

    # 5. Universal DC - REG (Website)
    html_content += f"""
        <tr>
            <td>Universal DC - REG (Website)</td>
            <td class="center">{stats['udc_reg_web']['count']}</td>
            <td class="right">{fmt_money(stats['udc_reg_web']['amount'])}</td>
        </tr>
    """

    # 6. Universal DC - COD (Website)
    html_content += f"""
        <tr>
            <td>Universal DC - COD (Website)</td>
            <td class="center">{stats['udc_cod_web']['count']}</td>
            <td class="right">{fmt_money(stats['udc_cod_web']['amount'])}</td>
        </tr>
    """

    # 7. Total Cotton Valley Order (Row 1 + Row 4)
    total_cv_count = stats['cv_app']['count'] + stats['cv_web']['count']
    total_cv_amt = stats['cv_app']['amount'] + stats['cv_web']['amount']
    html_content += f"""
        <tr class="total-row">
            <td>Total Cotton Valley Orders</td>
            <td class="center">{total_cv_count}</td>
            <td class="right">{fmt_money(total_cv_amt)}</td>
        </tr>
    """

    # 8. Total Universal DC - REG Order (Row 2 + Row 5)
    total_reg_count = stats['udc_reg_app']['count'] + stats['udc_reg_web']['count']
    total_reg_amt = stats['udc_reg_app']['amount'] + stats['udc_reg_web']['amount']
    html_content += f"""
        <tr class="total-row">
            <td>Total Universal DC - REG Order</td>
            <td class="center">{total_reg_count}</td>
            <td class="right">{fmt_money(total_reg_amt)}</td>
        </tr>
    """

    # 9. Total Universal DC - COD Order (Row 3 + Row 6)
    total_cod_count = stats['udc_cod_app']['count'] + stats['udc_cod_web']['count']
    total_cod_amt = stats['udc_cod_app']['amount'] + stats['udc_cod_web']['amount']
    html_content += f"""
        <tr class="total-row">
            <td>Total Universal DC - COD Order</td>
            <td class="center">{total_cod_count}</td>
            <td class="right">{fmt_money(total_cod_amt)}</td>
        </tr>
    """

    html_content += """
            </tbody>
        </table>
        <br>
    """

    # --- DETAIL TABLE (As it was) ---
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
                <th>Product Type</th>
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
            <td>{row.product_type or ''}</td>
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