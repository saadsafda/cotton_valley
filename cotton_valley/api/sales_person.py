import frappe
import json

@frappe.whitelist()
def get_months(doc):
    """
    Initialize sales target months for a Sales Person document.
    """
    doc = json.loads(doc)
    month_list = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    idx = 1
    for m in month_list:
        mnth = doc.append("sales_target")
        mnth.month = m
        mnth.target_amount = 10000.0 / 12
        mnth.idx = idx
        idx += 1