import { createApp } from "vue";
import SalesRepDashboard from "./SalesRepDashboard.vue";
import "./style.css";

// Imported by the "sales-rep-dashboard" Desk page (cotton_valley/cotton_valley/page/sales_rep_dashboard)
export function mount(el) {
	return createApp(SalesRepDashboard).mount(el);
}
