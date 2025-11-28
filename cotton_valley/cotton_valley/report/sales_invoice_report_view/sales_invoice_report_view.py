import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}

    # --- Defaults ---
    filters.setdefault('customer', None)
    filters.setdefault('si_number', None)
    filters.setdefault('so_number', None)
    filters.setdefault('account_code', None)
    # ----------------

    columns = get_columns()
    data = get_data(filters)
    
    return columns, data

def get_columns():
    return [
        {
            "label": _("SI Number"),
            "fieldname": "si_number",
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 140
        },
        {
            "label": _("SO Number"),
            "fieldname": "so_number",
            "fieldtype": "Link",
            "options": "Sales Order",
            "width": 140
        },
        {
            "label": _("Customer Name"),
            "fieldname": "customer_name",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Account Code"), 
            "fieldname": "account_code",
            "fieldtype": "Data", # Changed to Data because "Sher-NY" is text, not a standard Account Link
            "width": 140
        },
        {
            "label": _("Qty"),
            "fieldname": "total_qty",
            "fieldtype": "Float",
            "width": 80
        },
        {
            "label": _("Gross Amount"),
            "fieldname": "gross_amount",
            "fieldtype": "Currency",
            "width": 110
        },
        {
            "label": _("Discount"),
            "fieldname": "discount_amount",
            "fieldtype": "Currency",
            "width": 100
        },
        {
            "label": _("Net Amount"),
            "fieldname": "net_amount",
            "fieldtype": "Currency",
            "width": 110
        },
        {
            "label": _("Payment Mode"),
            "fieldname": "payment_mode",
            "fieldtype": "Link",
            "options": "Mode of Payment",
            "width": 120
        },
        {
            "label": _("Sales Rep"),
            "fieldname": "sales_rep",
            "fieldtype": "Link",
            "options": "Sales Person",
            "width": 150
        },
        {
            "label": _("Notes"),
            "fieldname": "notes",
            "fieldtype": "Small Text",
            "width": 200
        }
    ]

def get_data(filters):
    sql_query = """
        SELECT
            si.name AS si_number,
            
            (SELECT GROUP_CONCAT(DISTINCT sales_order SEPARATOR ', ') 
             FROM `tabSales Invoice Item` 
             WHERE parent = si.name) AS so_number,

            si.customer_name AS customer_name,

            /* --- UPDATED: Get Customer Account Number from Sales Order --- */
            (SELECT customer_account_number 
             FROM `tabSales Order` so
             JOIN `tabSales Invoice Item` sii ON sii.sales_order = so.name
             WHERE sii.parent = si.name LIMIT 1) AS account_code,
            /* ------------------------------------------------------------- */

            si.total_qty AS total_qty,
            si.base_total AS gross_amount,
            si.discount_amount AS discount_amount,
            si.grand_total AS net_amount,

            (SELECT mode_of_payment 
             FROM `tabSales Invoice Payment` 
             WHERE parent = si.name LIMIT 1) AS payment_mode,

            (SELECT GROUP_CONCAT(DISTINCT sales_person SEPARATOR ', ')
             FROM `tabSales Team`
             WHERE parent = si.name) AS sales_rep,

            si.remarks AS notes

        FROM
            `tabSales Invoice` si
        WHERE
            si.docstatus = 1
            
            AND (%(customer)s IS NULL OR si.customer = %(customer)s)
            
            AND (%(si_number)s IS NULL OR si.name LIKE CONCAT('%%', %(si_number)s, '%%'))

            /* Updated Filter Logic for Account Code */
            AND (%(account_code)s IS NULL OR EXISTS (
                SELECT 1 FROM `tabSales Order` so
                JOIN `tabSales Invoice Item` sii ON sii.sales_order = so.name
                WHERE sii.parent = si.name 
                AND so.customer_account_number LIKE CONCAT('%%', %(account_code)s, '%%')
            ))
            
            AND (%(so_number)s IS NULL OR EXISTS (
                SELECT 1 FROM `tabSales Invoice Item` item 
                WHERE item.parent = si.name 
                AND item.sales_order LIKE CONCAT('%%', %(so_number)s, '%%')
            ))
            
        ORDER BY
            si.posting_date DESC
    """
    
    return frappe.db.sql(sql_query, filters, as_dict=True)