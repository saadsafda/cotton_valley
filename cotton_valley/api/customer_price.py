import frappe
from cotton_valley.api.common import check_customer_token, get_customer_from_token


@frappe.whitelist(allow_guest=True)
def get_price_filters(company=None, category=None, sub_category=None):
    """
    Get price filter ranges for product filtering based on actual product prices.
    Returns two sets of filters: filterPrice (for case prices) and filterPCSPrice (for piece prices).
    Filters by customer's price list if customer is provided.
    
    Args:
        company: Company name (default: "Cotton Valley")
    """
    try:
        # Determine price list based on customer and company
        price_list = "Retail"
        company = "Cotton Valley" if not company or company == "null" else company
        category = category if category and category != "null" else None
        sub_category = sub_category if sub_category and sub_category != "null" else None
        
        if check_customer_token():
            customer = get_customer_from_token()
            
            if company == "Cotton Valley":
                price_list = frappe.get_value("Customer", customer, "price_list_for_cv") or "Retail"
            elif company == "UDC":
                price_list = frappe.get_value("Customer", customer, "price_list_for_udc") or "Retail"
            else:
                price_list = frappe.get_value("Customer", customer, "price_list_for_cv") or "Retail"

            if not price_list:
                price_list = "Retail"
        # else:
        #     return {
        #         "status": "success",
        #         "data": {}
        #     }
        
        # Get min and max prices from actual Item Price data
        # Filter by price list and company
        conditions = ["ip.price_list_rate > 0", "ip.price_list = %s", "i.company = %s", "i.disabled = 0"]
        values = [price_list, company]
        
        # Build joins based on filters
        joins = "INNER JOIN `tabItem` i ON i.name = ip.item_code"
        
        if category:
            joins += " INNER JOIN `tabProduct Categoris` c ON c.parent = i.name"
            conditions.append("c.product_category = %s")
            values.append(category)
        
        if sub_category:
            conditions.append("i.custom_sub_category = %s")
            values.append(sub_category)
        
        price_data = frappe.db.sql(f"""
            SELECT 
                MIN(ip.price_list_rate) as min_price,
                MAX(ip.price_list_rate) as max_price
            FROM `tabItem Price` ip
            {joins}
            WHERE {' AND '.join(conditions)}
        """, tuple(values), as_dict=True)
        
        min_price = (price_data[0].get('min_price') or 0) if price_data else 0
        max_price = (price_data[0].get('max_price') or 100) if price_data else 100
        
        # Calculate dynamic price ranges based on actual data
        # Divide the price range into 5 segments
        price_range = max_price - min_price
        segment = price_range / 5 if price_range > 0 else 20
        
        # Round segments to nearest 5 or 10 for cleaner ranges
        if segment > 10:
            segment = round(segment / 10) * 10
        elif segment > 5:
            segment = round(segment / 5) * 5
        else:
            segment = max(1, round(segment))
        
        # Generate dynamic filter ranges
        filter_price = []
        filter_id = 1
        
        # Below filter
        below_value = round(min_price + segment, 2)
        filter_price.append({
            "id": filter_id,
            "price": below_value,
            "text": "Below",
            "value": str(below_value)
        })
        filter_id += 1
        
        # Range filters
        current_min = below_value
        for i in range(5):
            current_max = round(current_min + segment, 2)
            if current_max < max_price:
                filter_price.append({
                    "id": filter_id,
                    "minPrice": current_min,
                    "maxPrice": current_max,
                    "value": f"{current_min}-{current_max}"
                })
                filter_id += 1
                current_min = current_max
        
        # Above filter
        above_value = round(max_price - segment, 2)
        filter_price.append({
            "id": filter_id,
            "price": above_value,
            "text": "Above",
            "value": str(above_value)
        })
        
        # For PCS (piece) prices - typically lower prices
        # Check if there are items with very low prices (< 20)
        pcs_conditions = ["ip.price_list_rate > 0", "ip.price_list_rate < 20", "ip.price_list = %s", "i.company = %s", "i.disabled = 0"]
        pcs_values = [price_list, company]
        
        # Build joins based on filters
        pcs_joins = "INNER JOIN `tabItem` i ON i.name = ip.item_code"
        
        if category:
            pcs_joins += " INNER JOIN `tabProduct Categoris` c ON c.parent = i.name"
            pcs_conditions.append("c.product_category = %s")
            pcs_values.append(category)
        
        if sub_category:
            pcs_conditions.append("i.custom_sub_category = %s")
            pcs_values.append(sub_category)
        
        pcs_price_data = frappe.db.sql(f"""
            SELECT 
                MIN(ip.price_list_rate) as min_price,
                MAX(ip.price_list_rate) as max_price
            FROM `tabItem Price` ip
            {pcs_joins}
            WHERE {' AND '.join(pcs_conditions)}
        """, tuple(pcs_values), as_dict=True)
        
        pcs_min = (pcs_price_data[0].get('min_price') or 0.5) if pcs_price_data else 0.5
        pcs_max = (pcs_price_data[0].get('max_price') or 10) if pcs_price_data else 10
        
        # Calculate PCS segments
        pcs_range = pcs_max - pcs_min
        pcs_segment = pcs_range / 5 if pcs_range > 0 else 2
        
        # Round to cleaner values
        if pcs_segment < 1:
            pcs_segment = round(pcs_segment, 1)
        else:
            pcs_segment = round(pcs_segment)
        
        # Generate PCS filter ranges
        filter_pcs_price = []
        pcs_id = 1
        
        # Below filter
        pcs_below = round(pcs_min + pcs_segment, 1)
        filter_pcs_price.append({
            "id": pcs_id,
            "price": pcs_below,
            "text": "Below",
            "value": str(pcs_below)
        })
        pcs_id += 1
        
        # Range filters
        pcs_current_min = pcs_below
        for i in range(5):
            pcs_current_max = round(pcs_current_min + pcs_segment, 1)
            if pcs_current_max < pcs_max:
                filter_pcs_price.append({
                    "id": pcs_id,
                    "minPrice": pcs_current_min,
                    "maxPrice": pcs_current_max,
                    "value": f"{pcs_current_min}-{pcs_current_max}"
                })
                pcs_id += 1
                pcs_current_min = pcs_current_max
        
        # Above filter
        pcs_above = round(pcs_max - pcs_segment, 1)
        filter_pcs_price.append({
            "id": pcs_id,
            "price": pcs_above,
            "text": "Above",
            "value": str(pcs_above)
        })
        
        return {
            "status": "success",
            "data": {
                "filterPrice": filter_price,
                "filterPCSPrice": filter_pcs_price,
                "priceRange": {
                    "min": min_price,
                    "max": max_price
                },
                "pcsPriceRange": {
                    "min": pcs_min,
                    "max": pcs_max
                },
                "priceList": price_list  # Include the price list used
            }
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Price Filters Error")
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}