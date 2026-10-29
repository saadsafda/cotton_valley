"""Data API for the Vue "Dashboard V3" desk page.

Rebuilds the metrics of the standard "Dashboard V2" (Dashboard doctype) so the
new page shows the same numbers. Cards reuse Frappe's number-card query, time
series charts reuse Frappe's dashboard-chart query and report charts run the
same script reports through `frappe.desk.query_report.run`, so permissions
behave exactly like they do on Dashboard V2.
"""

import frappe
from frappe import _
from frappe.desk.doctype.dashboard_chart.dashboard_chart import get_chart_config
from frappe.desk.doctype.number_card.number_card import get_result
from frappe.desk.query_report import run as run_report
from frappe.utils import add_days, flt, getdate, now_datetime, today
from frappe.utils.dateutils import get_from_date_from_timespan, get_period_beginning

# Field holding the company on each doctype (used by the company filter)
COMPANY_FIELDS = {
	"Sales Order": "company",
	"Customer": "register_company",
	"Lead": "company",
}

# Same definitions as the Number Cards on Dashboard V2. With a period other than
# "All Time", cards only count documents created in that period, except
# `all_time` cards (the customer base would otherwise equal "New Customers").
CARDS = [
	{"key": "orders", "label": "Orders", "doctype": "Sales Order", "function": "Count"},
	{
		"key": "processing",
		"label": "Processing",
		"doctype": "Sales Order",
		"function": "Count",
		"filters": [["Sales Order", "order_status", "=", "Processing"]],
	},
	{
		"key": "income",
		"label": "Income",
		"doctype": "Sales Order",
		"function": "Sum",
		"field": "base_grand_total",
		"fieldtype": "Currency",
	},
	{
		"key": "pending",
		"label": "Pending",
		"doctype": "Sales Order",
		"function": "Count",
		"filters": [["Sales Order", "order_status", "=", "Pending"]],
	},
	{
		"key": "abandoned_carts",
		"label": "Abandoned Carts",
		"doctype": "Sales Order",
		"function": "Count",
		"filters": [["Sales Order", "docstatus", "=", 0]],
	},
	{"key": "customers", "label": "Customers", "doctype": "Customer", "function": "Count", "all_time": True},
	{
		# Follows the period; for "All Time" it keeps Dashboard V2's
		# "New Customers Last 7 Days" query report definition
		"key": "new_customers",
		"label": "New Customers",
		"doctype": "Customer",
		"function": "Count",
		"all_time_filters": lambda: [["Customer", "creation", ">=", add_days(today(), -7)]],
	},
	{"key": "leads", "label": "Leads", "doctype": "Lead", "function": "Count"},
]

# Time series charts, queried like a "Count"/"Sum" Dashboard Chart on `creation`.
# NOTE: on Dashboard V2 all three of these are a count of Sales Orders; here
# "customers" and "orders_amount" plot what their titles say.
TIMESERIES_CHARTS = {
	"orders": {"doctype": "Sales Order", "chart_type": "Count", "label": "Orders"},
	"customers": {"doctype": "Customer", "chart_type": "Count", "label": "New Customers"},
	"orders_amount": {
		"doctype": "Sales Order",
		"chart_type": "Sum",
		"value_based_on": "base_grand_total",
		"label": "Order Amount",
		"fieldtype": "Currency",
	},
}

# Report charts: `x` is the label column, the first `y` is plotted and the rest
# are returned for tooltips and the table view.
REPORT_CHARTS = {
	"order_status": {
		"report": "Order Status Master",
		"x": "order_status",
		"y": ["grand_total"],
		# The report returns one row per order; sum them per status
		"group_by_x": True,
	},
	"order_status_summary": {
		"report": "Order Status Summary Report",
		"x": "order_status",
		"y": ["total_orders", "total_value"],
	},
	"top_states": {"report": "Top Selling States", "x": "state", "y": ["total_revenue", "total_orders"]},
	"sales_reps": {
		"report": "Sales Person-wise Summary",
		"x": "sales_person",
		"y": ["total_amount", "total_orders", "total_quantity"],
	},
	"abandoned_carts": {
		"report": "Abandoned Carts Report",
		"x": "item_code",
		"y": ["total_abandoned_value", "total_abandoned_quantity"],
	},
	"top_cities": {
		"report": "Top Shipping Cities",
		"x": "city",
		"y": ["total_order_value", "total_orders"],
	},
	"best_selling": {
		"report": "Best Selling Products",
		"x": "item_code",
		"y": ["total_sales_value", "total_quantity_sold"],
	},
}

# period -> (timespan, time interval) understood by Frappe's chart helpers
PERIODS = {
	"Last Week": ("Last Week", "Daily"),
	"Last Month": ("Last Month", "Daily"),
	"Last Quarter": ("Last Quarter", "Weekly"),
	"Last Year": ("Last Year", "Monthly"),
	# no date filter: cards show the same totals as Dashboard V2
	"All Time": (None, "Monthly"),
}
DEFAULT_PERIOD = "All Time"


@frappe.whitelist()
def get_options():
	return {
		"companies": frappe.get_list("Company", pluck="name", order_by="name asc"),
		"periods": list(PERIODS),
		"default_period": DEFAULT_PERIOD,
	}


@frappe.whitelist()
def get_cards(company=None, period=None):
	validate_company(company)
	from_date = get_period_start(period)
	cards = []
	for card in CARDS:
		filters = card.get("all_time_filters") if not from_date else None
		filters = filters() if callable(filters) else list(card.get("filters") or [])
		if from_date and not card.get("all_time"):
			filters.append([card["doctype"], "creation", ">=", from_date])
		if company:
			filters.append([card["doctype"], COMPANY_FIELDS[card["doctype"]], "=", company])

		doc = frappe._dict(
			function=card["function"],
			aggregate_function_based_on=card.get("field"),
			document_type=card["doctype"],
		)
		cards.append(
			{
				"key": card["key"],
				"label": _(card["label"]),
				"value": get_result(doc, filters),
				"fieldtype": card.get("fieldtype", "Int"),
				"all_time": bool(card.get("all_time")),
			}
		)

	return {"currency": get_currency(company), "from_date": from_date, "cards": cards}


@frappe.whitelist()
def get_chart(chart, company=None, period=None):
	validate_company(company)
	if chart in TIMESERIES_CHARTS:
		data = _get_timeseries_chart(TIMESERIES_CHARTS[chart], company, period)
	elif chart in REPORT_CHARTS:
		data = _get_report_chart(REPORT_CHARTS[chart], company)
	else:
		frappe.throw(_("Unknown chart {0}").format(chart))

	data["currency"] = get_currency(company)
	return data


def get_period_start(period):
	"""Start of the period, computed like Frappe's dashboard charts (None for "All Time")."""
	timespan, time_interval = PERIODS.get(period) or PERIODS[DEFAULT_PERIOD]
	if not timespan:
		return None
	return get_period_beginning(get_from_date_from_timespan(now_datetime(), timespan), time_interval)


def _get_timeseries_chart(config, company, period):
	timespan, time_interval = PERIODS.get(period) or PERIODS[DEFAULT_PERIOD]

	doctype = config["doctype"]
	# don't include cancelled documents (same as Dashboard Chart)
	filters = [[doctype, "docstatus", "<", 2, False]]
	if company:
		filters.append([doctype, COMPANY_FIELDS[doctype], "=", company, False])

	from_date = None
	if not timespan:
		# "All Time" starts at the first document instead of Frappe's 50 years back
		first = frappe.get_list(doctype, filters=filters, fields=["min(creation) as first"])[0].first
		from_date = get_period_beginning(getdate(first or now_datetime()), time_interval)

	chart = frappe._dict(
		name=config["label"],
		document_type=doctype,
		based_on="creation",
		chart_type=config["chart_type"],
		value_based_on=config.get("value_based_on"),
	)
	data = get_chart_config(chart, list(filters), timespan, time_interval, from_date, None)
	data["datasets"][0]["name"] = _(config["label"])
	data["datasets"][0]["fieldtype"] = config.get("fieldtype", "Int")
	return data


def _get_report_chart(config, company):
	result = run_report(
		config["report"],
		filters={"company": company} if company else {},
		ignore_prepared_report=True,
	)
	columns = {col["fieldname"]: col for col in result["columns"] if isinstance(col, dict)}
	rows = [row for row in result["result"] if isinstance(row, dict)]

	x, y_fields = config["x"], config["y"]
	if config.get("group_by_x"):
		rows = _group_rows(rows, x, y_fields)
	# some reports rank by another measure; keep the same rows, ordered by the plotted one
	rows = sorted(rows, key=lambda row: flt(row.get(y_fields[0])), reverse=True)

	labels = [row.get(x) or _("Not Set") for row in rows]
	# reports group by company too, so the same label can repeat across companies
	if len(set(labels)) < len(labels):
		labels = [f"{label} ({row.get('company')})" if row.get("company") else label for label, row in zip(labels, rows)]

	return {
		"x_label": _(columns.get(x, {}).get("label") or x),
		"labels": labels,
		"datasets": [
			{
				"name": _(columns.get(field, {}).get("label") or field),
				"fieldtype": columns.get(field, {}).get("fieldtype") or "Float",
				"values": [flt(row.get(field)) for row in rows],
			}
			for field in y_fields
		],
	}


def _group_rows(rows, x, y_fields):
	grouped = {}
	for row in rows:
		group = grouped.setdefault(row.get(x), {x: row.get(x), **{field: 0 for field in y_fields}})
		for field in y_fields:
			group[field] += flt(row.get(field))
	return list(grouped.values())


def validate_company(company):
	if company and not frappe.db.exists("Company", company):
		frappe.throw(_("Company {0} not found").format(company))


def get_currency(company):
	if company:
		return frappe.get_cached_value("Company", company, "default_currency")
	return frappe.db.get_default("currency")
