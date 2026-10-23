import frappe
from frappe.utils import flt
from cotton_valley.api.common import check_customer_token, get_customer_from_token


def build_price_ranges(min_price, max_price, segment, precision):
    """
    Build "Below", consecutive range and "Above" filters covering min_price..max_price.
    Values are parsed by products.parse_price_filter: "below-X", "X-Y", "above-X".
    """
    filters = []

    below = round(min_price + segment, precision)
    filters.append({"id": 1, "price": below, "text": "Below", "value": f"below-{below}"})

    current_min = below
    for _ in range(5):
        current_max = round(current_min + segment, precision)
        if current_max >= max_price:
            break
        filters.append({
            "id": len(filters) + 1,
            "minPrice": current_min,
            "maxPrice": current_max,
            "value": f"{current_min}-{current_max}"
        })
        current_min = current_max

    # "Above" starts where the last range ends so buckets don't overlap
    filters.append({"id": len(filters) + 1, "price": current_min, "text": "Above", "value": f"above-{current_min}"})
    return filters


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
        
        # Get min and max case / piece prices from actual Item Price data.
        # Effective price matches what products show: customer price list, falling back to Retail.
        price_expr = "COALESCE(NULLIF(cp.price_list_rate, 0), rp.price_list_rate)"
        case_pack_expr = "CAST(NULLIF(TRIM(i.custom_case_pack), '') AS DECIMAL(18,6))"
        pcs_expr = f"({price_expr}) / CASE WHEN {case_pack_expr} > 0 THEN {case_pack_expr} ELSE 1 END"

        conditions = [f"{price_expr} > 0", "i.company = %s", "i.disabled = 0", "i.hide = 0"]
        values = [price_list, company]

        joins = """
            LEFT JOIN `tabItem Price` cp ON cp.item_code = i.name AND cp.price_list = %s
            LEFT JOIN `tabItem Price` rp ON rp.item_code = i.name AND rp.price_list = 'Retail'
        """

        if category:
            joins += " INNER JOIN `tabProduct Categoris` c ON c.parent = i.name"
            conditions.append("c.product_category = %s")
            values.append(category)

        if sub_category:
            conditions.append("i.custom_sub_category = %s")
            values.append(sub_category)

        price_data = frappe.db.sql(f"""
            SELECT
                MIN({price_expr}) as min_price,
                MAX({price_expr}) as max_price,
                MIN({pcs_expr}) as pcs_min,
                MAX({pcs_expr}) as pcs_max
            FROM `tabItem` i
            {joins}
            WHERE {' AND '.join(conditions)}
        """, tuple(values), as_dict=True)
        price_data = price_data[0] if price_data else {}

        min_price = flt(price_data.get("min_price"))
        max_price = flt(price_data.get("max_price")) or 100

        # Divide the price range into 5 segments, rounded to nearest 5 or 10 for cleaner ranges
        segment = (max_price - min_price) / 5 if max_price > min_price else 20
        if segment > 10:
            segment = round(segment / 10) * 10
        elif segment > 5:
            segment = round(segment / 5) * 5
        else:
            segment = max(1, round(segment))

        filter_price = build_price_ranges(min_price, max_price, segment, 2)

        pcs_min = flt(price_data.get("pcs_min"))
        pcs_max = flt(price_data.get("pcs_max")) or 10

        pcs_segment = (pcs_max - pcs_min) / 5 if pcs_max > pcs_min else 2
        if pcs_segment < 1:
            pcs_segment = max(0.1, round(pcs_segment, 1))
        else:
            pcs_segment = round(pcs_segment)

        filter_pcs_price = build_price_ranges(pcs_min, pcs_max, pcs_segment, 2)

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