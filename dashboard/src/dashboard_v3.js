import { createApp } from "vue";
import DashboardV3 from "./DashboardV3.vue";
import "./style.css";

// Imported by the "dashboard-v3" Desk page (cotton_valley/cotton_valley/page/dashboard_v3)
export function mount(el) {
	return createApp(DashboardV3).mount(el);
}
