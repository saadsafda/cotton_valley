// Copyright (c) 2026, Saad and contributors
// For license information, please see license.txt

frappe.ui.form.on("Website Search Log", {
	refresh(frm) {
		// Make all fields read-only in the form view
		frm.disable_save();

		// Add a quick link to the analytics report
		if (frappe.user_roles.includes("System Manager") || frappe.user_roles.includes("Website Manager") || frappe.user_roles.includes("Sales Manager")) {
			frm.add_custom_button(__("View Analytics Report"), function () {
				frappe.set_route("query-report", "Website Search Analytics");
			});
		}
	},
});
