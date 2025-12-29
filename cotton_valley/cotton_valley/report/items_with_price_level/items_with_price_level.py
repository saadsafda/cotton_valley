# Copyright (c) 2025, Saad and contributors
# For license information, please see license.txt


import frappe

def execute(filters=None):
    if not filters: filters = {}
    
    # --- 1. Price Lists Fetch Logic (Modified) ---
    # Agar user ne filter mein Price List select ki hai, to sirf wahi fetch karo.
    # Warna saari enabled lists fetch karo.
    
    pl_filters = {"enabled": 1}
    if filters.get("price_list"):
        pl_filters["name"] = filters.get("price_list")

    price_lists = frappe.get_all("Price List", filters=pl_filters, order_by="name asc")
    
    columns = get_columns(price_lists)
    data = get_data(filters, price_lists)
    
    return columns, data

def get_columns(price_lists):
    columns = [
        {
            "fieldname": "item_code",
            "label": "Item Code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 150
        },
        {
            "fieldname": "item_name",
            "label": "Item Name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "company",  
            "label": "Company",
            "fieldtype": "Data",    
            "width": 150
        }
    ]

    # Dynamic Columns (Jo price lists upar filter hui hain, sirf wo columns banengi)
    for pl in price_lists:
        columns.append({
            "fieldname": frappe.scrub(pl.name),
            "label": pl.name,
            "fieldtype": "Currency",
            "width": 120
        })

    return columns

def get_data(filters, price_lists):
    data = []
    
    # --- SQL Query Logic ---
    conditions = ""
    
    if filters.get("company"):
        conditions += f" AND id.company = '{filters.get('company')}' "
    
    # NOTE: Item Group ka filter yahan se hata diya gaya hai
    
    if filters.get("item_code"):
        conditions += f" AND i.name = '{filters.get('item_code')}' "

    sql = f"""
        SELECT
            i.name as item_code,
            i.item_name,
            GROUP_CONCAT(DISTINCT id.company SEPARATOR ', ') as company_list
        FROM
            `tabItem` i
        LEFT JOIN
            `tabItem Default` id ON i.name = id.parent
        WHERE
            1=1 {conditions}
        GROUP BY
            i.name
        ORDER BY
            i.name ASC
    """
    
    items = frappe.db.sql(sql, as_dict=True)

    # Prices fetch karein
    # Optimization: Agar Price List filter laga hai to sirf ussi ke rates uthao
    price_cond = ""
    if filters.get("price_list"):
        price_cond = f" WHERE price_list = '{filters.get('price_list')}'"

    prices = frappe.db.sql(f"""
        SELECT item_code, price_list, price_list_rate 
        FROM `tabItem Price`
        {price_cond}
    """, as_dict=True)

    # Price Map (Lookup ke liye)
    price_map = {}
    for p in prices:
        if p.item_code not in price_map:
            price_map[p.item_code] = {}
        price_map[p.item_code][p.price_list] = p.price_list_rate

    # Final Loop
    for item in items:
        row = {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "company": item.company_list
        }

        for pl in price_lists:
            field_name = frappe.scrub(pl.name)
            rate = price_map.get(item.item_code, {}).get(pl.name, 0.0)
            row[field_name] = rate

        data.append(row)

    return data