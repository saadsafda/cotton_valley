// Runs inside Desk, so `frappe.xcall` handles the session, CSRF token and server errors.
const API = "cotton_valley.api.dashboard_v3";

export function getOptions() {
	return frappe.xcall(`${API}.get_options`);
}

export function getCards(company, period) {
	return frappe.xcall(`${API}.get_cards`, { company, period });
}

export function getChart(chart, company, period) {
	return frappe.xcall(`${API}.get_chart`, { chart, company, period });
}

const REP_API = "cotton_valley.api.sales_rep_dashboard";

export function getRepOptions() {
	return frappe.xcall(`${REP_API}.get_options`);
}

export function getRepSummary(sales_person, company, period) {
	return frappe.xcall(`${REP_API}.get_summary`, { sales_person, company, period });
}

export function getRepChart(chart, sales_person, company, period) {
	return frappe.xcall(`${REP_API}.get_chart`, { chart, sales_person, company, period });
}

export function getRepCustomers(sales_person, company, period) {
	return frappe.xcall(`${REP_API}.get_customers`, { sales_person, company, period });
}

export function getRepTargets(sales_person, period_type, from_date, to_date, product_category, product_subcategory) {
	return frappe.xcall(`${REP_API}.get_targets`, {
		sales_person,
		period_type,
		from_date,
		to_date,
		product_category,
		product_subcategory,
	});
}
