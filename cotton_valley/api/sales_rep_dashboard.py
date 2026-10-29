"""Data API for the Vue "Sales Rep Dashboard" desk page.

A rep only ever sees their own numbers (the Sales Person linked to their
Employee, plus any granted through a "Sales Person" User Permission); managers
can pick any rep. Sales are the submitted Sales Orders credited to the rep
(`custom_customer_sales_representative`), dated by `transaction_date`.
A rep's customers are the ones they are on the sales team of (see
`cotton_valley.api.sales_team`).
"""

import frappe
from frappe import _
from frappe.desk.doctype.dashboard_chart.dashboard_chart import get_result as get_bucketed_result
from frappe.utils import add_days, date_diff, flt, get_first_day, get_last_day, getdate, now_datetime, today
from frappe.utils.data import format_date
from frappe.utils.dateutils import get_period, get_period_beginning

from cotton_valley.api.dashboard_v3 import (
	DEFAULT_PERIOD,
	PERIODS,
	get_currency,
	get_period_start,
	validate_company,
)
from cotton_valley.api.sales_team import get_customers_for_sales_persons, get_user_sales_persons
from cotton_valley.cotton_valley.report.sr_target_report.sr_target_report import (
	PERIOD_TYPES,
	execute as run_target_report,
)

MANAGER_ROLES = {"System Manager", "Sales Manager", "Sales Master Manager"}
REP_FIELD = "custom_customer_sales_representative"
# the SR target report spreads every target day by day for weekly periods
MAX_WEEKLY_TARGET_DAYS = 120


@frappe.whitelist()
def get_options():
	own = get_user_sales_persons()
	can_choose = _is_manager()
	if can_choose:
		sales_persons = frappe.get_all(
			"Sales Person", filters={"enabled": 1, "is_group": 0}, pluck="name", order_by="name asc"
		)
	else:
		sales_persons = own

	if not sales_persons:
		frappe.throw(
			_("Your user is not linked to a Sales Person. Ask an administrator to set it on your Employee record."),
			frappe.PermissionError,
		)

	if own and own[0] in sales_persons:
		default = own[0]
	else:
		# managers without a rep of their own start on the rep with the most orders
		default = frappe.db.sql(
			f"""select {REP_FIELD} from `tabSales Order`
			where docstatus = 1 and {REP_FIELD} in %(reps)s
			group by {REP_FIELD} order by count(*) desc limit 1""",
			{"reps": sales_persons},
		)
		default = default[0][0] if default else sales_persons[0]

	return {
		"sales_persons": sales_persons,
		"default_sales_person": default,
		"can_choose": can_choose,
		"companies": frappe.get_list("Company", pluck="name", order_by="name asc"),
		"periods": list(PERIODS),
		"default_period": DEFAULT_PERIOD,
		"target_period_types": list(PERIOD_TYPES),
		"target_range": _current_fiscal_year_range(),
	}


@frappe.whitelist()
def get_summary(sales_person, company=None, period=None):
	_check_access(sales_person, company)
	from_date = get_period_start(period)

	submitted = _order_totals(sales_person, company, from_date, docstatus=1)
	drafts = _order_totals(sales_person, company, from_date, docstatus=0)

	customers = get_customers_for_sales_persons([sales_person], company)
	active = _customers_with_orders(sales_person, company, from_date, customers)
	# "All Time" keeps Dashboard V2's "new customers in the last 7 days"
	new_since = from_date or add_days(today(), -7)
	new_customers = (
		frappe.db.count("Customer", {"name": ["in", customers], "creation": [">=", new_since]})
		if customers
		else 0
	)

	cards = [
		{"key": "sales", "label": _("Sales"), "value": submitted.amount, "fieldtype": "Currency"},
		{"key": "orders", "label": _("Orders"), "value": submitted.orders, "fieldtype": "Int"},
		{
			"key": "average_order",
			"label": _("Avg. Order Value"),
			"value": submitted.amount / submitted.orders if submitted.orders else 0,
			"fieldtype": "Currency",
		},
		{"key": "open_carts", "label": _("Open Carts"), "value": drafts.orders, "fieldtype": "Int"},
		{"key": "customers", "label": _("My Customers"), "value": len(customers), "fieldtype": "Int", "all_time": True},
		{"key": "active_customers", "label": _("Active Customers"), "value": len(active), "fieldtype": "Int"},
		{
			"key": "inactive_customers",
			"label": _("Inactive Customers"),
			"value": len(customers) - len(active),
			"fieldtype": "Int",
		},
		{"key": "new_customers", "label": _("New Customers"), "value": new_customers, "fieldtype": "Int"},
	]
	return {
		"currency": get_currency(company),
		"from_date": from_date,
		"open_carts_value": drafts.amount,
		"cards": cards,
	}


@frappe.whitelist()
def get_chart(chart, sales_person, company=None, period=None):
	_check_access(sales_person, company)
	if chart == "sales_trend":
		data = _get_trend(sales_person, company, period, "Sum", _("Sales"), "Currency")
	elif chart == "orders_trend":
		data = _get_trend(sales_person, company, period, "Count", _("Orders"), "Int")
	elif chart == "order_status":
		data = _get_order_status(sales_person, company, get_period_start(period))
	elif chart == "top_customers":
		data = _get_top_customers(sales_person, company, get_period_start(period))
	elif chart == "top_items":
		data = _get_top_items(sales_person, company, get_period_start(period))
	else:
		frappe.throw(_("Unknown chart {0}").format(chart))

	data["currency"] = get_currency(company)
	return data


@frappe.whitelist()
def get_targets(
	sales_person,
	period_type="Monthly",
	from_date=None,
	to_date=None,
	product_category=None,
	product_subcategory=None,
):
	"""Target vs achieved for the rep, from the "SR target report" (own filters, not the page's).

	The breakdown drills down with the filters: categories, then the subcategories
	of `product_category`, then the items of `product_subcategory`.

	Achievements follow that report: Sales Invoices (draft + submitted) credited
	through the invoice's Sales Team, net amount.
	"""
	_check_access(sales_person, None)
	if period_type not in PERIOD_TYPES:
		frappe.throw(_("Invalid period type {0}").format(period_type))

	default_range = _current_fiscal_year_range()
	from_date = getdate(from_date or default_range["from_date"])
	to_date = getdate(to_date or default_range["to_date"])
	if from_date > to_date:
		frappe.throw(_("From Date must be before To Date"))
	if period_type == "Weekly" and date_diff(to_date, from_date) > MAX_WEEKLY_TARGET_DAYS:
		frappe.throw(_("Weekly targets can cover at most {0} days; pick a shorter range").format(MAX_WEEKLY_TARGET_DAYS))

	filters = {
		"sales_person": sales_person,
		"period_type": period_type,
		"from_date": from_date,
		"to_date": to_date,
		"product_category": product_category,
		"product_subcategory": product_subcategory if product_category else None,
	}
	rows = run_target_report(filters)[1]

	if filters["product_subcategory"]:
		level, group_field = "item", "item_code"
	elif product_category:
		level, group_field = "subcategory", "product_subcategory"
	else:
		level, group_field = "category", "product_category"

	measures = ("target_amount", "achieved_amount", "target_qty", "achieved_qty")
	by_period, by_group, item_names = {}, {}, {}
	for row in rows:
		if level == "item":
			item_names.setdefault(row.get("item_code"), row.get("item_name"))
		for group, key in ((by_period, row["period"]), (by_group, row.get(group_field))):
			totals = group.setdefault(key, dict.fromkeys(measures, 0.0))
			for measure in measures:
				totals[measure] += flt(row.get(measure))

	totals = {measure: sum(p[measure] for p in by_period.values()) for measure in measures}

	category_titles = _titles("Product Category")
	if level == "category":
		labels = category_titles
	elif level == "subcategory":
		labels = _titles("Product Subcategory", list(by_group))
	else:
		labels = {
			code: f"{code} · {name}" if name and name != code else code for code, name in item_names.items()
		}
	breakdown = [
		{"key": key, "label": labels.get(key) or key or _("Not Set"), **values}
		for key, values in by_group.items()
	]
	breakdown.sort(key=lambda row: row["target_amount"], reverse=True)

	# categories this rep has targets in, for the category filter
	category_options = frappe.get_all(
		"Target Detail",
		filters={"parenttype": "Sales Person", "parent": sales_person},
		pluck="product_category",
		distinct=True,
	)

	periods = sorted(by_period)
	return {
		"currency": get_currency(None),
		"labels": [_format_target_period(p, period_type) for p in periods],
		"periods": [by_period[p] for p in periods],
		"totals": totals,
		"breakdown": {
			"level": level,
			"category_label": category_titles.get(product_category) if product_category else None,
			"subcategory_label": (
				_titles("Product Subcategory", [product_subcategory]).get(product_subcategory)
				if filters["product_subcategory"]
				else None
			),
			"rows": breakdown,
		},
		"category_options": sorted(
			({"value": c, "label": category_titles.get(c) or c} for c in category_options if c),
			key=lambda c: c["label"],
		),
	}


@frappe.whitelist()
def get_customers(sales_person, company=None, period=None):
	"""Every customer of the rep with their sales in the period and last order date."""
	_check_access(sales_person, company)
	customers = get_customers_for_sales_persons([sales_person], company)
	if not customers:
		return {"currency": get_currency(company), "customers": []}

	from_date = get_period_start(period)
	values = {"sales_person": sales_person, "customers": customers, "company": company, "from_date": from_date}
	company_condition = "and so.company = %(company)s" if company else ""
	period_amount = "so.transaction_date >= %(from_date)s" if from_date else "1=1"

	stats = frappe.db.sql(
		f"""
		select
			so.customer,
			sum(if({period_amount}, so.base_grand_total, 0)) as sales,
			sum(if({period_amount}, 1, 0)) as orders,
			max(so.transaction_date) as last_order
		from `tabSales Order` so
		where so.docstatus = 1
			and so.{REP_FIELD} = %(sales_person)s
			and so.customer in %(customers)s
			{company_condition}
		group by so.customer
		""",
		values,
		as_dict=True,
	)
	stats = {row.customer: row for row in stats}

	rows = frappe.db.sql(
		"""
		select c.name, c.customer_name, c.disabled, c.creation, addr.city, addr.state
		from `tabCustomer` c
		left join `tabAddress` addr on addr.name = c.customer_primary_address
		where c.name in %(customers)s
		""",
		{"customers": customers},
		as_dict=True,
	)
	for row in rows:
		stat = stats.get(row.name) or {}
		row.sales = flt(stat.get("sales"))
		row.orders = int(stat.get("orders") or 0)
		row.last_order = stat.get("last_order")
		row.active = row.orders > 0

	rows.sort(key=lambda row: (row.sales, row.last_order or getdate("1900-01-01")), reverse=True)
	return {"currency": get_currency(company), "customers": rows}


def _current_fiscal_year_range():
	try:
		from erpnext.accounts.utils import get_fiscal_year

		_, start, end = get_fiscal_year(today())
	except Exception:
		start, end = get_first_day(today()).replace(month=1), get_last_day(today()).replace(month=12, day=31)
	return {"from_date": str(start), "to_date": str(end)}


def _titles(doctype, names=None):
	"""name -> title for Product Category / Product Subcategory."""
	filters = {"name": ["in", [n for n in names if n]]} if names is not None else None
	if names is not None and not filters["name"][1]:
		return {}
	return dict(frappe.get_all(doctype, filters=filters, fields=["name", "title"], as_list=True))


def _format_target_period(period, period_type):
	"""SR target report labels ("2026-03", "2026-Q1") in a friendlier form."""
	if period_type == "Monthly":
		return getdate(f"{period}-01").strftime("%b %Y")
	if period_type == "Quarterly":
		year, quarter = period.split("-")
		return f"{quarter} {year}"
	return period


def _is_manager():
	return bool(MANAGER_ROLES & set(frappe.get_roles()))


def _check_access(sales_person, company):
	validate_company(company)
	if _is_manager():
		if not frappe.db.exists("Sales Person", sales_person):
			frappe.throw(_("Sales Person {0} not found").format(sales_person))
	elif sales_person not in get_user_sales_persons():
		frappe.throw(_("You can only view your own sales"), frappe.PermissionError)


def _order_conditions(sales_person, company, from_date, docstatus):
	conditions = [f"so.{REP_FIELD} = %(sales_person)s", "so.docstatus = %(docstatus)s"]
	if company:
		conditions.append("so.company = %(company)s")
	if from_date:
		conditions.append("so.transaction_date >= %(from_date)s")
	values = {"sales_person": sales_person, "docstatus": docstatus, "company": company, "from_date": from_date}
	return " and ".join(conditions), values


def _order_totals(sales_person, company, from_date, docstatus):
	conditions, values = _order_conditions(sales_person, company, from_date, docstatus)
	row = frappe.db.sql(
		f"""
		select count(*) as orders, coalesce(sum(so.base_grand_total), 0) as amount
		from `tabSales Order` so where {conditions}
		""",
		values,
		as_dict=True,
	)[0]
	return frappe._dict(orders=int(row.orders), amount=flt(row.amount))


def _customers_with_orders(sales_person, company, from_date, customers):
	if not customers:
		return []
	conditions, values = _order_conditions(sales_person, company, from_date, docstatus=1)
	values["customers"] = customers
	return frappe.db.sql_list(
		f"""
		select distinct so.customer from `tabSales Order` so
		where {conditions} and so.customer in %(customers)s
		""",
		values,
	)


def _get_trend(sales_person, company, period, chart_type, label, fieldtype):
	"""Bucketed like a Frappe Dashboard Chart on `transaction_date`."""
	timespan, time_interval = PERIODS.get(period) or PERIODS[DEFAULT_PERIOD]
	conditions, values = _order_conditions(sales_person, company, None, docstatus=1)

	if timespan:
		from_date = get_period_start(period)
	else:
		# "All Time" starts at the rep's first order
		first = frappe.db.sql(
			f"select min(so.transaction_date) from `tabSales Order` so where {conditions}", values
		)[0][0]
		from_date = get_period_beginning(getdate(first or now_datetime()), time_interval)

	values["from_date"] = from_date
	data = frappe.db.sql(
		f"""
		select so.transaction_date, sum(so.base_grand_total), count(*)
		from `tabSales Order` so
		where {conditions} and so.transaction_date >= %(from_date)s
		group by so.transaction_date
		order by so.transaction_date
		""",
		values,
	)
	result = get_bucketed_result(data, time_interval, from_date, now_datetime(), chart_type)

	return {
		"labels": [
			format_date(get_period(r[0], time_interval), parse_day_first=True)
			if time_interval in ("Daily", "Weekly")
			else get_period(r[0], time_interval)
			for r in result
		],
		"datasets": [{"name": label, "fieldtype": fieldtype, "values": [r[1] for r in result]}],
	}


def _get_order_status(sales_person, company, from_date):
	conditions, values = _order_conditions(sales_person, company, from_date, docstatus=1)
	# include drafts too: the order status lives on the order from creation
	conditions = conditions.replace("so.docstatus = %(docstatus)s", "so.docstatus < 2")
	rows = frappe.db.sql(
		f"""
		select so.order_status, count(*) as orders, sum(so.base_grand_total) as amount
		from `tabSales Order` so
		where {conditions} and ifnull(so.order_status, '') != ''
		group by so.order_status
		order by orders desc
		""",
		values,
		as_dict=True,
	)
	return {
		"x_label": _("Status"),
		"labels": [row.order_status for row in rows],
		"datasets": [
			{"name": _("Orders"), "fieldtype": "Int", "values": [row.orders for row in rows]},
			{"name": _("Amount"), "fieldtype": "Currency", "values": [flt(row.amount) for row in rows]},
		],
	}


def _get_top_customers(sales_person, company, from_date):
	conditions, values = _order_conditions(sales_person, company, from_date, docstatus=1)
	rows = frappe.db.sql(
		f"""
		select so.customer, max(so.customer_name) as customer_name,
			sum(so.base_grand_total) as sales, count(*) as orders
		from `tabSales Order` so
		where {conditions}
		group by so.customer
		order by sales desc
		limit 10
		""",
		values,
		as_dict=True,
	)
	return {
		"x_label": _("Customer"),
		"labels": [row.customer_name or row.customer for row in rows],
		"datasets": [
			{"name": _("Sales"), "fieldtype": "Currency", "values": [flt(row.sales) for row in rows]},
			{"name": _("Orders"), "fieldtype": "Int", "values": [row.orders for row in rows]},
		],
	}


def _get_top_items(sales_person, company, from_date):
	conditions, values = _order_conditions(sales_person, company, from_date, docstatus=1)
	rows = frappe.db.sql(
		f"""
		select soi.item_code, max(soi.item_name) as item_name,
			sum(soi.base_amount) as sales, sum(soi.stock_qty) as qty,
			count(distinct so.name) as orders
		from `tabSales Order Item` soi
		join `tabSales Order` so on so.name = soi.parent
		where {conditions}
		group by soi.item_code
		order by sales desc
		limit 10
		""",
		values,
		as_dict=True,
	)
	return {
		"x_label": _("Item"),
		# code first so it stays visible when a long name is truncated on the axis
		"labels": [
			f"{row.item_code} · {row.item_name}"
			if row.item_name and row.item_name != row.item_code
			else row.item_code
			for row in rows
		],
		"datasets": [
			{"name": _("Sales"), "fieldtype": "Currency", "values": [flt(row.sales) for row in rows]},
			{"name": _("Quantity"), "fieldtype": "Float", "values": [flt(row.qty) for row in rows]},
			{"name": _("Orders"), "fieldtype": "Int", "values": [row.orders for row in rows]},
		],
	}
