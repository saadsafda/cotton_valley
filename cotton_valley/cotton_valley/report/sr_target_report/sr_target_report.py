# Copyright (c) 2026, Saad and contributors
# For license information, please see license.txt

import calendar

import frappe
from frappe.utils import add_days, add_months, add_years, flt, get_first_day, get_last_day, getdate


PERIOD_TYPES = ("Weekly", "Monthly", "Quarterly", "Yearly")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.period_type = _normalize_period_type(filters.get("period_type")) or "Monthly"
	filters.from_date = filters.get("from_date")
	filters.to_date = filters.get("to_date")

	_apply_default_dates(filters)
	_validate_dates(filters)

	periods = _get_periods(filters.from_date, filters.to_date, filters.period_type)
	columns = _get_columns()

	target_fields = _get_target_fields()
	item_fields = _get_item_fields()

	target_rows = _get_targets(filters, target_fields)
	actual_map, match_category, match_subcategory = _get_actuals(filters, item_fields, filters.period_type)

	data, report_summary = _build_rows(
		filters,
		periods,
		target_rows,
		actual_map,
		match_category,
		match_subcategory,
		target_fields,
		item_fields,
	)
	return columns, data, None, None, report_summary


def _apply_default_dates(filters):
	if filters.from_date and filters.to_date:
		return

	if not filters.from_date and not filters.to_date:
		today = getdate()
		filters.from_date = get_first_day(today)
		filters.to_date = get_last_day(today)
		return

	if not filters.from_date:
		filters.from_date = get_first_day(filters.to_date)

	if not filters.to_date:
		filters.to_date = get_last_day(filters.from_date)


def _validate_dates(filters):
	if filters.from_date and filters.to_date:
		if getdate(filters.from_date) > getdate(filters.to_date):
			frappe.throw("From Date must be before To Date.")


def _get_columns():
	return [
		{"fieldname": "sales_person", "label": "Sales Person", "fieldtype": "Link", "options": "Sales Person", "width": 160},
		{"fieldname": "product_category", "label": "Product Category", "fieldtype": "Link", "options": "Product Category", "width": 140},
		{"fieldname": "product_subcategory", "label": "Product Subcategory", "fieldtype": "Link", "options": "Product Subcategory", "width": 150},
		{"fieldname": "item_code", "label": "Product / Item Code", "fieldtype": "Data", "options": "Item", "width": 140},
		{"fieldname": "item_name", "label": "Product / Item Name", "fieldtype": "Data", "width": 180},
		{"fieldname": "period", "label": "Period", "fieldtype": "Data", "width": 110},
		{"fieldname": "target_qty", "label": "Target Qty", "fieldtype": "Float", "width": 110},
		{"fieldname": "achieved_qty", "label": "Achieved Qty", "fieldtype": "Float", "width": 120},
		{"fieldname": "remaining_qty", "label": "Remaining Qty", "fieldtype": "Float", "width": 120},
		{"fieldname": "qty_achievement", "label": "Qty Achievement %", "fieldtype": "Percent", "width": 130},
		{"fieldname": "target_amount", "label": "Target Amount", "fieldtype": "Currency", "width": 120},
		{"fieldname": "achieved_amount", "label": "Achieved Amount", "fieldtype": "Currency", "width": 130},
		{"fieldname": "remaining_amount", "label": "Remaining Amount", "fieldtype": "Currency", "width": 130},
		{"fieldname": "amount_achievement", "label": "Amount Achievement %", "fieldtype": "Percent", "width": 140},
		{"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 110},
	]


def _get_target_fields():
	meta = frappe.get_meta("Target Detail")
	return {
		"doctype": meta.name,
		"table": "`tabTarget Detail`",
		"product_category": _resolve_field(meta, ["product_category", "item_group"], "Product Category"),
		"product_subcategory": _resolve_field(meta, ["product_subcategory", "item_sub_group"], "Product Subcategory"),
		"item_code": _resolve_field(meta, ["item_code", "item"], "Item"),
		"item_name": _resolve_field(meta, ["item_name"], "Item Name"),
		"target_qty": _resolve_field(meta, ["target_qty"], "Target Qty"),
		"target_amount": _resolve_field(meta, ["target_amount"], "Target Amount"),
		"target_distribution": _resolve_field(meta, ["target_distribution", "distribution_id"], "Target Distribution"),
	}


def _get_item_fields():
	meta = frappe.get_meta("Item")
	return {
		"product_category": _resolve_field(meta, ["product_category"], "Product Category"),
		"product_subcategory": _resolve_field(meta, ["product_subcategory"], "Product Subcategory"),
		"item_name": _resolve_field(meta, ["item_name"], "Item Name"),
	}


def _resolve_field(meta, candidates, label):
	for fieldname in candidates:
		if meta.get_field(fieldname):
			return fieldname

	for field in meta.fields:
		if field.label == label:
			return field.fieldname

	return None


def _get_targets(filters, target_fields):
	if not target_fields.get("target_qty") or not target_fields.get("target_amount"):
		frappe.throw("Target Detail must have Target Qty and Target Amount fields.")

	conditions = ["td.parenttype = 'Sales Person'"]
	values = {}

	if filters.get("sales_person"):
		conditions.append("td.parent = %(sales_person)s")
		values["sales_person"] = filters.sales_person

	if filters.get("product_category") and target_fields.get("product_category"):
		conditions.append(f"td.{target_fields['product_category']} = %(product_category)s")
		values["product_category"] = filters.product_category

	if filters.get("product_subcategory") and target_fields.get("product_subcategory"):
		conditions.append(f"td.{target_fields['product_subcategory']} = %(product_subcategory)s")
		values["product_subcategory"] = filters.product_subcategory

	if filters.get("item_code") and target_fields.get("item_code"):
		conditions.append(f"td.{target_fields['item_code']} = %(item_code)s")
		values["item_code"] = filters.item_code

	join_sales_person = ""
	if filters.get("company"):
		join_sales_person = "LEFT JOIN `tabSales Person` sp ON sp.name = td.parent"
		conditions.append("sp.company = %(company)s")
		values["company"] = filters.company

	fields = [
		"td.parent AS sales_person",
		f"td.{target_fields['product_category']} AS product_category" if target_fields.get("product_category") else "NULL AS product_category",
		f"td.{target_fields['product_subcategory']} AS product_subcategory" if target_fields.get("product_subcategory") else "NULL AS product_subcategory",
		f"td.{target_fields['item_code']} AS item_code" if target_fields.get("item_code") else "NULL AS item_code",
		f"td.{target_fields['item_name']} AS item_name" if target_fields.get("item_name") else "NULL AS item_name",
		f"td.{target_fields['target_qty']} AS target_qty",
		f"td.{target_fields['target_amount']} AS target_amount",
		f"td.{target_fields['target_distribution']} AS target_distribution" if target_fields.get("target_distribution") else "NULL AS target_distribution",
	]

	query = f"""
		SELECT {", ".join(fields)}
		FROM {target_fields['table']} td
		{join_sales_person}
		WHERE {" AND ".join(conditions)}
	"""

	return frappe.db.sql(query, values, as_dict=True)


def _get_actuals(filters, item_fields, period_type):
	period_expr = _get_period_sql(period_type, "si.posting_date")
	match_category = bool(item_fields.get("product_category"))
	match_subcategory = bool(item_fields.get("product_subcategory"))

	conditions = [
		"si.docstatus IN (0, 1)",
		"si.posting_date BETWEEN %(from_date)s AND %(to_date)s",
	]
	values = {"from_date": filters.from_date, "to_date": filters.to_date}

	if filters.get("company"):
		conditions.append("si.company = %(company)s")
		values["company"] = filters.company

	if filters.get("sales_person"):
		conditions.append("st.sales_person = %(sales_person)s")
		values["sales_person"] = filters.sales_person

	if filters.get("item_code"):
		conditions.append("sii.item_code = %(item_code)s")
		values["item_code"] = filters.item_code

	if filters.get("product_category") and item_fields.get("product_category"):
		conditions.append(f"it.{item_fields['product_category']} = %(product_category)s")
		values["product_category"] = filters.product_category

	if filters.get("product_subcategory") and item_fields.get("product_subcategory"):
		conditions.append(f"it.{item_fields['product_subcategory']} = %(product_subcategory)s")
		values["product_subcategory"] = filters.product_subcategory

	qty_expr = "sii.qty * (IFNULL(st.allocated_percentage, 100) / 100)"
	amount_expr = "sii.base_net_amount * (IFNULL(st.allocated_percentage, 100) / 100)"

	fields = [
		"st.sales_person AS sales_person",
		"sii.item_code AS item_code",
		"it.item_name AS item_name",
		f"it.{item_fields['product_category']} AS product_category" if item_fields.get("product_category") else "NULL AS product_category",
		f"it.{item_fields['product_subcategory']} AS product_subcategory" if item_fields.get("product_subcategory") else "NULL AS product_subcategory",
		f"{period_expr} AS period",
		f"SUM({qty_expr}) AS achieved_qty",
		f"SUM({amount_expr}) AS achieved_amount",
	]

	query = f"""
		SELECT {", ".join(fields)}
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		INNER JOIN `tabSales Team` st ON st.parent = si.name
		LEFT JOIN `tabItem` it ON it.name = sii.item_code
		WHERE {" AND ".join(conditions)}
		GROUP BY st.sales_person, sii.item_code, period, product_category, product_subcategory
	"""

	rows = frappe.db.sql(query, values, as_dict=True)
	actual_map = {}
	for row in rows:
		key = _row_key(row, match_category, match_subcategory)
		actual_map[key] = {
			"achieved_qty": flt(row.achieved_qty),
			"achieved_amount": flt(row.achieved_amount),
			"item_name": row.item_name,
		}

	return actual_map, match_category, match_subcategory


def _build_rows(filters, periods, target_rows, actual_map, match_category, match_subcategory, target_fields, item_fields):
	data = []

	period_count = len(periods) or 1
	distribution_cache = {}

	for target in target_rows:
		base_target_qty = flt(target.target_qty)
		base_target_amount = flt(target.target_amount)
		distribution_id = target.target_distribution
		distribution_map = _get_distribution_map(distribution_id, distribution_cache)

		for period in periods:
			per_period_qty = _get_period_target(
				base_target_qty,
				period,
				filters.period_type,
				distribution_map,
				period_count,
			)
			per_period_amount = _get_period_target(
				base_target_amount,
				period,
				filters.period_type,
				distribution_map,
				period_count,
			)
			key = _row_key(
				{
					"sales_person": target.sales_person,
					"product_category": target.product_category if match_category else None,
					"product_subcategory": target.product_subcategory if match_subcategory else None,
					"item_code": target.item_code,
					"period": period["label"],
				},
				match_category,
				match_subcategory,
			)
			actual = actual_map.get(key, {})
			achieved_qty = flt(actual.get("achieved_qty"))
			achieved_amount = flt(actual.get("achieved_amount"))
			item_name = target.item_name or actual.get("item_name")

			remaining_qty = per_period_qty - achieved_qty
			remaining_amount = per_period_amount - achieved_amount
			qty_achievement = (achieved_qty / per_period_qty * 100) if per_period_qty else 0
			amount_achievement = (achieved_amount / per_period_amount * 100) if per_period_amount else 0

			status = _get_status(achieved_qty, per_period_qty)
			indicator = _get_indicator(amount_achievement or qty_achievement)

			row = {
				"sales_person": target.sales_person,
				"product_category": target.product_category,
				"product_subcategory": target.product_subcategory,
				"item_code": target.item_code,
				"item_name": item_name,
				"period": period["label"],
				"target_qty": per_period_qty,
				"achieved_qty": achieved_qty,
				"remaining_qty": remaining_qty,
				"qty_achievement": qty_achievement,
				"target_amount": per_period_amount,
				"achieved_amount": achieved_amount,
				"remaining_amount": remaining_amount,
				"amount_achievement": amount_achievement,
				"status": status,
				"indicator": indicator,
			}
			data.append(row)

	data.sort(key=lambda d: (
		d.get("sales_person") or "",
		d.get("product_category") or "",
		d.get("product_subcategory") or "",
		d.get("item_code") or "",
		d.get("period") or "",
	))

	report_summary = _build_summary_from_data(data)
	return data, report_summary


def _build_summary_from_data(rows):
	total_target_qty = 0.0
	total_achieved_qty = 0.0
	total_target_amount = 0.0
	total_achieved_amount = 0.0

	for row in rows:
		total_target_qty += flt(row.get("target_qty"))
		total_achieved_qty += flt(row.get("achieved_qty"))
		total_target_amount += flt(row.get("target_amount"))
		total_achieved_amount += flt(row.get("achieved_amount"))

	total_remaining_qty = total_target_qty - total_achieved_qty
	qty_percent = (total_achieved_qty / total_target_qty * 100) if total_target_qty else 0
	amount_percent = (total_achieved_amount / total_target_amount * 100) if total_target_amount else 0

	return [
		{"label": "Total Target Qty", "value": flt(total_target_qty, 2)},
		{"label": "Total Achieved Qty", "value": flt(total_achieved_qty, 2)},
		{"label": "", "value": ""},
		{"label": "Overall Qty Achievement %", "value": flt(qty_percent, 2), "indicator": _summary_indicator(qty_percent)},
		{"label": "Total Target Amount", "value": flt(total_target_amount, 2), "datatype": "Currency"},
		{"label": "Total Remaining Qty", "value": flt(total_remaining_qty, 2)},
		{"label": "Total Achieved Amount", "value": flt(total_achieved_amount, 2), "datatype": "Currency"},
		{"label": "", "value": ""},
		{"label": "Overall Amount Achievement %", "value": flt(amount_percent, 2), "indicator": _summary_indicator(amount_percent)},
		{"label": "", "value": ""},
	]


def _get_distribution_map(distribution_id, cache):
	if not distribution_id:
		return None

	if distribution_id in cache:
		return cache[distribution_id]

	rows = frappe.get_all(
		"Monthly Distribution Percentage",
		filters={"parent": distribution_id},
		fields=["month", "percentage_allocation"],
	)

	distribution_map = {row.month: flt(row.percentage_allocation) for row in rows}
	cache[distribution_id] = distribution_map
	return distribution_map


def _get_period_target(base_target, period, period_type, distribution_map, period_count):
	if not distribution_map:
		return base_target / period_count if period_count else base_target

	if period_type == "Yearly":
		return base_target

	if period_type == "Monthly":
		month_name = period["start"].strftime("%B")
		return base_target * (distribution_map.get(month_name, 0) / 100)

	if period_type == "Quarterly":
		month_start = period["start"].month
		month_names = [
			calendar.month_name[month_start],
			calendar.month_name[month_start + 1],
			calendar.month_name[month_start + 2],
		]
		quarter_percent = sum(distribution_map.get(name, 0) for name in month_names)
		return base_target * (quarter_percent / 100)

	if period_type == "Weekly":
		return _get_week_target(base_target, period, distribution_map)

	return base_target / period_count if period_count else base_target


def _get_week_target(base_target, period, distribution_map):
	start_date = period["start"]
	end_exclusive = period["end_exclusive"]
	current = start_date
	weekly_target = 0.0

	while current < end_exclusive:
		month_name = current.strftime("%B")
		percent = distribution_map.get(month_name, 0)
		month_total = base_target * (percent / 100)
		days_in_month = calendar.monthrange(current.year, current.month)[1]
		weekly_target += month_total / days_in_month
		current = add_days(current, 1)

	return weekly_target


def _get_periods(from_date, to_date, period_type):
	start = getdate(from_date)
	end = getdate(to_date)
	periods = []

	if period_type == "Weekly":
		current = start
		current = add_days(current, -current.weekday())
		while current <= end:
			label = _format_period_label(current, period_type)
			periods.append({"label": label, "start": current, "end_exclusive": add_days(current, 7)})
			current = add_days(current, 7)
		return periods

	if period_type == "Monthly":
		current = start.replace(day=1)
		while current <= end:
			label = _format_period_label(current, period_type)
			periods.append({"label": label, "start": current, "end_exclusive": add_months(current, 1)})
			current = add_months(current, 1)
		return periods

	if period_type == "Quarterly":
		quarter_start_month = ((start.month - 1) // 3) * 3 + 1
		current = start.replace(month=quarter_start_month, day=1)
		while current <= end:
			label = _format_period_label(current, period_type)
			periods.append({"label": label, "start": current, "end_exclusive": add_months(current, 3)})
			current = add_months(current, 3)
		return periods

	if period_type == "Yearly":
		current = start.replace(month=1, day=1)
		while current <= end:
			label = _format_period_label(current, period_type)
			periods.append({"label": label, "start": current, "end_exclusive": add_years(current, 1)})
			current = add_years(current, 1)
		return periods

	return periods


def _get_period_sql(period_type, date_field):
	if period_type == "Weekly":
		return (
			"CONCAT("
			"YEARWEEK({0}, 1) DIV 100,"
			"'-W',"
			"LPAD(YEARWEEK({0}, 1) MOD 100, 2, '0')"
			")"
		).format(date_field)

	if period_type == "Monthly":
		return f"DATE_FORMAT({date_field}, '%%Y-%%m')"

	if period_type == "Quarterly":
		return f"CONCAT(YEAR({date_field}), '-Q', QUARTER({date_field}))"

	if period_type == "Yearly":
		return f"CAST(YEAR({date_field}) AS CHAR)"

	return f"DATE_FORMAT({date_field}, '%%Y-%%m')"


def _format_period_label(date_value, period_type):
	date_value = getdate(date_value)
	if period_type == "Weekly":
		year, week, _ = date_value.isocalendar()
		return f"{year}-W{week:02d}"

	if period_type == "Monthly":
		return date_value.strftime("%Y-%m")

	if period_type == "Quarterly":
		quarter = ((date_value.month - 1) // 3) + 1
		return f"{date_value.year}-Q{quarter}"

	if period_type == "Yearly":
		return str(date_value.year)

	return date_value.strftime("%Y-%m")


def _normalize_period_type(period_type):
	if not period_type:
		return None

	value = str(period_type).strip().lower()
	if value.startswith("week"):
		return "Weekly"
	if value.startswith("month"):
		return "Monthly"
	if value.startswith("quart"):
		return "Quarterly"
	if value.startswith("year"):
		return "Yearly"

	return None


def _row_key(row, match_category=True, match_subcategory=True):
	return (
		row.get("sales_person"),
		row.get("product_category") if match_category else None,
		row.get("product_subcategory") if match_subcategory else None,
		row.get("item_code"),
		row.get("period"),
	)


def _get_status(achieved_qty, target_qty):
	if achieved_qty == 0:
		return "Not Started"
	if achieved_qty < target_qty:
		return "In Progress"
	return "Achieved"


def _get_indicator(achievement_percent):
	if achievement_percent < 50:
		return ["Below 50%", "red"]
	if achievement_percent < 100:
		return ["50% - 99%", "orange"]
	return ["100%+", "green"]


def _summary_indicator(achievement_percent):
	if achievement_percent < 50:
		return "Red"
	if achievement_percent < 100:
		return "Orange"
	return "Green"
