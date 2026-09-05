"""Helpers for resolving the sales representatives attached to a customer.

A Customer keeps its ERP-synced primary rep in `sales_person` (Cotton Valley)
and `udc_sales_person` (UDC). Those two fields are overwritten by the external
ERP sync (see `cotton_valley.api.customer.fetch_customer_data`), so any extra
representatives live in the `custom_additional_sales_team` child table instead.

"Team" throughout this module means: the primary rep for the company plus every
additional rep listed in that child table.
"""

import frappe

PRIMARY_FIELD_BY_COMPANY = {
	"UDC": "udc_sales_person",
}
DEFAULT_PRIMARY_FIELD = "sales_person"


def primary_field(company=None):
	"""Return the Customer fieldname holding the primary rep for `company`."""
	return PRIMARY_FIELD_BY_COMPANY.get(company, DEFAULT_PRIMARY_FIELD)


def get_primary_sales_person(customer, company=None):
	"""The single ERP-owned rep for this customer/company, or None."""
	if not customer:
		return None
	return frappe.db.get_value("Customer", customer, primary_field(company))


def get_customer_sales_team(customer, company=None):
	"""Every Sales Person who may act on `customer`.

	When `company` is given, only that company's primary rep and the additional
	rows tagged with that company are returned. Without a company both primary
	fields and all additional rows are included.
	"""
	if not customer:
		return []

	if company:
		primaries = [primary_field(company)]
	else:
		primaries = [DEFAULT_PRIMARY_FIELD] + list(PRIMARY_FIELD_BY_COMPANY.values())

	row = frappe.db.get_value("Customer", customer, primaries, as_dict=True) or {}

	team = []
	for fieldname in primaries:
		value = row.get(fieldname)
		if value and value not in team:
			team.append(value)

	additional_filters = {"parent": customer, "parenttype": "Customer"}
	if company:
		additional_filters["company"] = company

	for sp in frappe.get_all(
		"Customer Sales Team",
		filters=additional_filters,
		pluck="sales_person",
	):
		if sp and sp not in team:
			team.append(sp)

	return team


def get_customers_for_sales_persons(sales_persons, company=None):
	"""Every Customer that any of `sales_persons` is on the team of."""
	sales_persons = [sp for sp in (sales_persons or []) if sp]
	if not sales_persons:
		return []

	if company:
		primaries = [primary_field(company)]
	else:
		primaries = [DEFAULT_PRIMARY_FIELD] + list(PRIMARY_FIELD_BY_COMPANY.values())

	customers = []
	for fieldname in primaries:
		customers.extend(
			frappe.get_all(
				"Customer",
				filters={fieldname: ["in", sales_persons]},
				pluck="name",
			)
		)

	additional_filters = {
		"parenttype": "Customer",
		"sales_person": ["in", sales_persons],
	}
	if company:
		additional_filters["company"] = company

	customers.extend(
		frappe.get_all(
			"Customer Sales Team",
			filters=additional_filters,
			pluck="parent",
		)
	)

	return list(dict.fromkeys(c for c in customers if c))


def is_in_customer_sales_team(customer, sales_person, company=None):
	"""Whether `sales_person` may act on `customer`."""
	if not customer or not sales_person:
		return False
	return sales_person in get_customer_sales_team(customer, company)


def get_user_sales_persons(user=None):
	"""Every Sales Person the given user may act as.

	Combines the rep linked to their Employee record with any additional reps
	granted through a "Sales Person" User Permission.
	"""
	user = user or frappe.session.user
	if not user or user == "Guest":
		return []

	sales_persons = []

	employee = frappe.db.get_value(
		"Employee", {"user_id": user, "status": "Active"}, "name"
	)
	if employee:
		own = frappe.db.get_value(
			"Sales Person", {"employee": employee, "enabled": 1}, "name"
		)
		if own:
			sales_persons.append(own)

	for sp in frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": "Sales Person"},
		pluck="for_value",
	):
		if sp and sp not in sales_persons:
			sales_persons.append(sp)

	return sales_persons


def get_acting_sales_person(customer, company=None, user=None):
	"""The Sales Person to credit for a transaction on `customer`.

	Prefers the logged-in user's own rep when they are on the customer's team,
	so the person who actually made the sale is the one credited. Falls back to
	the customer's primary rep for web/guest orders with no logged-in rep.
	"""
	team = get_customer_sales_team(customer, company)

	for sp in get_user_sales_persons(user):
		if sp in team:
			return sp

	return get_primary_sales_person(customer, company)
