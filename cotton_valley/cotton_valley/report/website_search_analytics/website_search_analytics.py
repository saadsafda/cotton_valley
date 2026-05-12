# Copyright (c) 2026, Saad and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, add_days, nowdate


def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns(filters)
    data = get_data(filters)
    chart = get_chart(filters)
    report_summary = get_report_summary(filters)

    return columns, data, None, chart, report_summary


def get_columns(filters):
    """Define report columns."""
    return [
        {
            "label": "Company",
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 140,
        },
        {
            "label": "Normalized Query",
            "fieldname": "normalized_query",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": "Search Query (Original)",
            "fieldname": "search_query",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": "User Type",
            "fieldname": "user_type",
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "label": "User",
            "fieldname": "user",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": "Guest Session ID",
            "fieldname": "guest_session_id",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": "Total Searches",
            "fieldname": "total_searches",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": "First Searched On",
            "fieldname": "first_searched_on",
            "fieldtype": "Datetime",
            "width": 170,
        },
        {
            "label": "Last Searched On",
            "fieldname": "last_searched_on",
            "fieldtype": "Datetime",
            "width": 170,
        },
        {
            "label": "Page URL",
            "fieldname": "page_url",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": "Avg Results Count",
            "fieldname": "avg_results_count",
            "fieldtype": "Float",
            "precision": 1,
            "width": 140,
        },
        {
            "label": "Zero Result Searches",
            "fieldname": "zero_result_searches",
            "fieldtype": "Int",
            "width": 150,
        },
    ]


def get_data(filters):
    """Fetch and aggregate search log data."""
    conditions = build_conditions(filters)
    having_clause = build_having(filters)

    query = f"""
        SELECT
            IFNULL(company, '') AS company,
            normalized_query,
            search_query,
            user_type,
            IFNULL(user, '') AS user,
            IFNULL(guest_session_id, '') AS guest_session_id,
            COUNT(*) AS total_searches,
            MIN(searched_on) AS first_searched_on,
            MAX(searched_on) AS last_searched_on,
            IFNULL(page_url, '') AS page_url,
            ROUND(AVG(IFNULL(results_count, 0)), 1) AS avg_results_count,
            SUM(CASE WHEN IFNULL(results_count, 0) = 0 THEN 1 ELSE 0 END) AS zero_result_searches
        FROM
            `tabWebsite Search Log`
        WHERE
            {conditions}
        GROUP BY
            IFNULL(company, ''),
            normalized_query,
            user_type,
            IFNULL(user, ''),
            IFNULL(guest_session_id, ''),
            IFNULL(page_url, '')
        {having_clause}
        ORDER BY
            total_searches DESC
    """

    data = frappe.db.sql(query, filters, as_dict=True)
    return data


def build_conditions(filters):
    """Build SQL WHERE conditions from filters."""
    conditions = "1=1"

    if filters.get("from_date"):
        conditions += " AND DATE(searched_on) >= %(from_date)s"

    if filters.get("to_date"):
        conditions += " AND DATE(searched_on) <= %(to_date)s"

    if filters.get("user_type") and filters.get("user_type") != "All":
        conditions += " AND user_type = %(user_type)s"

    if filters.get("user"):
        conditions += " AND user = %(user)s"

    if filters.get("search_query"):
        conditions += " AND normalized_query LIKE CONCAT('%%', %(search_query)s, '%%')"

    if filters.get("page_url"):
        conditions += " AND page_url LIKE CONCAT('%%', %(page_url)s, '%%')"

    if filters.get("company"):
        conditions += " AND company = %(company)s"

    return conditions


def build_having(filters):
    """Build HAVING clause separately from WHERE."""
    if filters.get("min_search_count"):
        return "HAVING total_searches >= %(min_search_count)s"
    return ""


def get_chart(filters):
    """Generate chart data for the report."""
    conditions = build_conditions(filters)

    # ── Top 20 Searched Keywords ──────────────────────────────────────
    top_keywords = frappe.db.sql(f"""
        SELECT
            normalized_query AS label,
            COUNT(*) AS value
        FROM
            `tabWebsite Search Log`
        WHERE
            {conditions}
        GROUP BY
            normalized_query
        ORDER BY
            value DESC
        LIMIT 20
    """, filters, as_dict=True)

    chart = None
    if top_keywords:
        chart = {
            "data": {
                "labels": [row.get("label", "") for row in top_keywords],
                "datasets": [
                    {
                        "name": "Search Count",
                        "values": [row.get("value", 0) for row in top_keywords],
                    }
                ],
            },
            "type": "bar",
            "colors": ["#E8533F"],
            "barOptions": {"spaceRatio": 0.4},
        }

    return chart


def get_report_summary(filters):
    """Generate summary statistics for the report."""
    conditions = build_conditions(filters)

    summary_data = frappe.db.sql(f"""
        SELECT
            COUNT(*) AS total_searches,
            COUNT(DISTINCT normalized_query) AS unique_queries,
            SUM(CASE WHEN user_type = 'Guest' THEN 1 ELSE 0 END) AS guest_searches,
            SUM(CASE WHEN user_type = 'Logged In' THEN 1 ELSE 0 END) AS logged_in_searches,
            SUM(CASE WHEN IFNULL(results_count, 0) = 0 THEN 1 ELSE 0 END) AS zero_result_searches
        FROM
            `tabWebsite Search Log`
        WHERE
            {conditions}
    """, filters, as_dict=True)

    if not summary_data:
        return []

    s = summary_data[0]

    return [
        {
            "value": s.get("total_searches", 0),
            "indicator": "Blue",
            "label": "Total Searches",
            "datatype": "Int",
        },
        {
            "value": s.get("unique_queries", 0),
            "indicator": "Green",
            "label": "Unique Queries",
            "datatype": "Int",
        },
        {
            "value": s.get("guest_searches", 0),
            "indicator": "Orange",
            "label": "Guest Searches",
            "datatype": "Int",
        },
        {
            "value": s.get("logged_in_searches", 0),
            "indicator": "Blue",
            "label": "Logged In Searches",
            "datatype": "Int",
        },
        {
            "value": s.get("zero_result_searches", 0),
            "indicator": "Red",
            "label": "Zero Result Searches",
            "datatype": "Int",
        },
    ]
