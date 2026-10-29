<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import FilterBar from "./components/FilterBar.vue";
import StatCard from "./components/StatCard.vue";
import ChartCard from "./components/ChartCard.vue";
import { getCards, getChart, getOptions } from "./api";
import { ICONS } from "./icons";
import { useDarkMode } from "./theme";

const COMPANY_FIELDS = { "Sales Order": "company", Customer: "register_company", Lead: "company" };

// Same cards, in the same order, as Dashboard V2
const CARDS = [
	{ key: "orders", label: "Orders", icon: ICONS.bag, hint: "All sales orders", periodHint: "Created", gradient: "tw-from-indigo-600 tw-to-violet-600", doctype: "Sales Order" },
	{ key: "processing", label: "Processing", icon: ICONS.spinner, hint: "Status: Processing", periodHint: "Status: Processing", gradient: "tw-from-sky-600 tw-to-blue-700", doctype: "Sales Order", filters: { order_status: "Processing" } },
	{ key: "income", label: "Income", icon: ICONS.dollar, gradient: "tw-from-emerald-600 tw-to-teal-700", doctype: "Sales Order" },
	{ key: "pending", label: "Pending", icon: ICONS.clock, hint: "Status: Pending", periodHint: "Status: Pending", gradient: "tw-from-amber-600 tw-to-orange-700", doctype: "Sales Order", filters: { order_status: "Pending" } },
	{ key: "abandoned_carts", label: "Abandoned Carts", icon: ICONS.cart, hint: "Draft sales orders", periodHint: "Draft orders", gradient: "tw-from-rose-600 tw-to-pink-700", doctype: "Sales Order", filters: { docstatus: 0 } },
	{ key: "customers", label: "Customers", icon: ICONS.users, hint: "All customers", gradient: "tw-from-fuchsia-600 tw-to-purple-700", doctype: "Customer" },
	{ key: "new_customers", label: "New Customers", icon: ICONS.userPlus, hint: "Last 7 days", periodHint: "Joined", gradient: "tw-from-cyan-700 tw-to-teal-800", doctype: "Customer", filters: () => ({ creation: [">=", frappe.datetime.add_days(frappe.datetime.get_today(), -7)] }) },
	{ key: "leads", label: "Leads", icon: ICONS.target, hint: "All leads", periodHint: "Created", gradient: "tw-from-blue-700 tw-to-indigo-800", doctype: "Lead" },
];

// Same charts, order and widths as Dashboard V2
// Charts without `timeseries` come from all-time reports and ignore the period
const CHARTS = [
	{ key: "orders", title: "Orders", subtitle: "Orders created", kind: "column", hue: "blue", full: true, timeseries: true },
	{ key: "order_status", title: "Order Status", subtitle: "Order amount by status", kind: "status-bar" },
	{ key: "order_status_summary", title: "Order Status Summary", subtitle: "Number of orders by status", kind: "donut" },
	{ key: "customers", title: "Customers", subtitle: "New customers", kind: "column", hue: "violet", full: true, timeseries: true },
	{ key: "top_states", title: "Top 5 States", subtitle: "Revenue from submitted orders", kind: "ranking", hue: "blue" },
	{ key: "sales_reps", title: "Excellent Sales Reps", subtitle: "Top 5 by sales amount", kind: "ranking", hue: "violet" },
	{ key: "orders_amount", title: "Orders Amount", subtitle: "Order value", kind: "area", hue: "aqua", full: true, timeseries: true },
	{ key: "abandoned_carts", title: "Abandoned Carts", subtitle: "Top 5 items by value", kind: "ranking", hue: "magenta" },
	{ key: "top_cities", title: "Top 5 Cities", subtitle: "Top 5 by orders · order value shown", kind: "ranking", hue: "orange" },
	{ key: "best_selling", title: "Best Selling", subtitle: "Top 5 by quantity sold · sales value shown", kind: "ranking", hue: "green", full: true },
];

const dark = useDarkMode();
const companies = ref([]);
const periods = ref([]);
const company = ref("");
const period = ref("All Time");
const isAllTime = computed(() => period.value === "All Time");
const updatedAt = ref(null);

const cards = reactive({ loading: false, data: null });
const charts = reactive(Object.fromEntries(CHARTS.map((c) => [c.key, { loading: false, data: null, error: null }])));

// guards against an older, slower response overwriting a newer one
const requests = {};
function track(key) {
	requests[key] = (requests[key] || 0) + 1;
	const id = requests[key];
	return () => requests[key] === id;
}

async function loadCards() {
	const isLatest = track("cards");
	cards.loading = true;
	try {
		const data = await getCards(company.value || null, period.value);
		if (isLatest()) cards.data = data;
	} finally {
		if (isLatest()) cards.loading = false;
	}
}

async function loadChart(key) {
	const isLatest = track(key);
	const state = charts[key];
	state.loading = true;
	state.error = null;
	try {
		const data = await getChart(key, company.value || null, period.value);
		if (isLatest()) state.data = data;
	} catch (e) {
		if (isLatest()) state.error = "Could not load this chart";
	} finally {
		if (isLatest()) state.loading = false;
	}
}

function loadAll() {
	updatedAt.value = new Date();
	loadCards().catch(() => {});
	CHARTS.forEach((c) => loadChart(c.key));
}

watch(company, loadAll);
watch(period, () => {
	loadCards().catch(() => {});
	CHARTS.filter((c) => c.timeseries).forEach((c) => loadChart(c.key));
});

const cardValues = computed(() =>
	Object.fromEntries((cards.data?.cards || []).map((c) => [c.key, c]))
);

function cardHint(card) {
	if (isAllTime.value || cardValues.value[card.key]?.all_time) return card.hint;
	return `${card.periodHint} · ${period.value}`;
}

// Opens the list with the same filters (period included) that produced the number
function openList(card) {
	const fromDate = cards.data?.from_date;
	const filters =
		typeof card.filters === "function" ? (fromDate ? {} : card.filters()) : { ...card.filters };
	if (fromDate && !cardValues.value[card.key]?.all_time) filters.creation = [">=", fromDate];
	if (company.value) filters[COMPANY_FIELDS[card.doctype]] = company.value;
	frappe.set_route("List", card.doctype, filters);
}

const subtitle = computed(() => {
	const time = updatedAt.value?.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
	return `${company.value || "All companies"} · ${period.value}${time ? ` · Updated ${time}` : ""}`;
});

onMounted(async () => {
	loadAll();
	const options = await getOptions();
	companies.value = options.companies;
	periods.value = options.periods;
});
</script>

<template>
	<div class="tw-mx-auto tw-flex tw-max-w-[1400px] tw-flex-col tw-gap-6 tw-py-4">
		<FilterBar
			v-model:company="company"
			v-model:period="period"
			title="Sales Overview"
			:subtitle="subtitle"
			:companies="companies"
			:periods="periods"
			@refresh="loadAll"
		/>

		<div class="tw-grid tw-grid-cols-1 tw-gap-4 sm:tw-grid-cols-2 xl:tw-grid-cols-4">
			<StatCard
				v-for="card in CARDS"
				:key="card.key"
				:label="cardValues[card.key]?.label || card.label"
				:value="cardValues[card.key]?.value ?? null"
				:fieldtype="cardValues[card.key]?.fieldtype"
				:currency="cards.data?.currency"
				:hint="cardHint(card)"
				:icon="card.icon"
				:gradient="card.gradient"
				:loading="cards.loading"
				@open="openList(card)"
			/>
		</div>

		<div class="tw-grid tw-grid-cols-1 tw-gap-4 lg:tw-grid-cols-2">
			<ChartCard
				v-for="chart in CHARTS"
				:key="chart.key"
				:title="chart.title"
				:subtitle="`${chart.subtitle} · ${chart.timeseries ? period : 'All time'}`"
				:kind="chart.kind"
				:hue="chart.hue"
				:full="chart.full"
				:data="charts[chart.key].data"
				:loading="charts[chart.key].loading"
				:error="charts[chart.key].error"
				:dark="dark"
				@retry="loadChart(chart.key)"
			/>
		</div>
	</div>
</template>
