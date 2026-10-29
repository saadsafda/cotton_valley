export function formatValue(value, fieldtype, currency, { compact = false } = {}) {
	value = Number(value) || 0;

	if (fieldtype === "Currency") {
		// Desk's formatter follows the system number format settings
		if (!compact && window.format_currency) {
			return window.format_currency(value, currency);
		}
		return new Intl.NumberFormat(undefined, {
			style: "currency",
			currency: currency || "USD",
			notation: compact ? "compact" : "standard",
			maximumFractionDigits: compact ? 1 : 2,
		}).format(value);
	}

	return new Intl.NumberFormat(undefined, {
		notation: compact ? "compact" : "standard",
		maximumFractionDigits: fieldtype === "Int" ? 0 : compact ? 1 : 2,
	}).format(value);
}
