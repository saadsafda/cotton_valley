<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import FilterBar from "./components/FilterBar.vue";
import StatCard from "./components/StatCard.vue";
import ChartCard from "./components/ChartCard.vue";
import CustomerTable from "./components/CustomerTable.vue";
import TargetsCard from "./components/TargetsCard.vue";
import { getRepChart, getRepCustomers, getRepOptions, getRepSummary } from "./api";
import { formatValue } from "./format";
import { ICONS } from "./icons";
import { useDarkMode } from "./theme";

// `table` cards filter the customer table instead of opening a list
const CARDS = [
	{ key: "sales", label: "Sales", icon: ICONS.dollar, gradient: "tw-from-emerald-600 tw-to-teal-700", list: { docstatus: 1 } },
	{ key: "orders", label: "Orders", icon: ICONS.bag, periodHint: "Submitted", gradient: "tw-from-indigo-600 tw-to-violet-600", list: { docstatus: 1 } },
	{ key: "average_order", label: "Avg. Order Value", icon: ICONS.receipt, gradient: "tw-from-sky-600 tw-to-blue-700", list: { docstatus: 1 } },
	{ key: "open_carts", label: "Open Carts", icon: ICONS.cart, gradient: "tw-from-rose-600 tw-to-pink-700", list: { docstatus: 0 } },
	{ key: "customers", label: "My Customers", icon: ICONS.users, hint: "Assigned to you", gradient: "tw-from-fuchsia-600 tw-to-purple-700", table: "all" },
	{ key: "active_customers", label: "Active Customers", icon: ICONS.userCheck, periodHint: "Ordered", gradient: "tw-from-cyan-700 tw-to-teal-800", table: "active" },
	{ key: "inactive_customers", label: "Inactive Customers", icon: ICONS.userX, periodHint: "No orders", gradient: "tw-from-amber-600 tw-to-orange-700", table: "inactive" },
	{ key: "new_customers", label: "New Customers", icon: ICONS.userPlus, periodHint: "Joined", gradient: "tw-from-blue-700 tw-to-indigo-800", table: "new" },
];

const CHARTS = [
	{ key: "sales_trend", title: "Sales", subtitle: "Submitted order value", kind: "area", hue: "aqua", full: true },
	{ key: "orders_trend", title: "Orders", subtitle: "Submitted orders", kind: "column", hue: "blue" },
	{ key: "order_status", title: "Order Status", subtitle: "Orders by status, drafts included", kind: "donut" },
	{ key: "top_customers", title: "Top Customers", subtitle: "Top 10 by sales", kind: "ranking", hue: "violet", full: true },
	{ key: "top_items", title: "Top Items", subtitle: "Top 10 by sales", kind: "ranking", hue: "orange", full: true },
];

const dark = useDarkMode();
const options = ref(null);
const optionsError = ref(null);
const salesPerson = ref("");
const company = ref("");
const period = ref("All Time");
const customerFilter = ref("all");
const updatedAt = ref(null);
const tableEl = ref(null);

const summary = reactive({ loading: false, data: null });
const customers = reactive({ loading: false, data: null });
const charts = reactive(Object.fromEntries(CHARTS.map((c) => [c.key, { loading: false, data: null, error: null }])));

// guards against an older, slower response overwriting a newer one
const requests = {};
function track(key) {
	requests[key] = (requests[key] || 0) + 1;
	const id = requests[key];
	return () => requests[key] === id;
}

async function load(key, state, fetch) {
	const isLatest = track(key);
	state.loading = true;
	if ("error" in state) state.error = null;
	try {
		const data = await fetch();
		if (isLatest()) state.data = data;
	} catch (e) {
		if (isLatest() && "error" in state) state.error = "Could not load this chart";
	} finally {
		if (isLatest()) state.loading = false;
	}
}

function loadAll() {
	if (!salesPerson.value) return;
	updatedAt.value = new Date();
	const args = [salesPerson.value, company.value || null, period.value];
	load("summary", summary, () => getRepSummary(...args));
	load("customers", customers, () => getRepCustomers(...args));
	CHARTS.forEach((c) => load(c.key, charts[c.key], () => getRepChart(c.key, ...args)));
}

watch([salesPerson, company, period], loadAll);

const cardValues = computed(() =>
	Object.fromEntries((summary.data?.cards || []).map((c) => [c.key, c]))
);
const isAllTime = computed(() => period.value === "All Time");

function cardHint(card) {
	if (card.key === "open_carts") {
		const value = formatValue(summary.data?.open_carts_value, "Currency", summary.data?.currency, { compact: true });
		return isAllTime.value ? `${value} in draft orders` : `${value} · ${period.value}`;
	}
	if (card.key === "average_order") return isAllTime.value ? "All submitted orders" : period.value;
	if (card.hint) return card.hint;
	if (isAllTime.value) return card.key === "new_customers" ? "Last 7 days" : "All time";
	return `${card.periodHint} · ${period.value}`;
}

function openCard(card) {
	if (card.table) {
		customerFilter.value = card.table;
		tableEl.value?.$el.scrollIntoView({ behavior: "smooth", block: "start" });
		return;
	}
	const filters = { custom_customer_sales_representative: salesPerson.value, ...card.list };
	if (company.value) filters.company = company.value;
	if (summary.data?.from_date) filters.transaction_date = [">=", summary.data.from_date];
	frappe.set_route("List", "Sales Order", filters);
}

const subtitle = computed(() => {
	const time = updatedAt.value?.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
	return [company.value || "All companies", period.value, time && `Updated ${time}`]
		.filter(Boolean)
		.join(" · ");
});

onMounted(async () => {
	try {
		options.value = await getRepOptions();
		salesPerson.value = options.value.default_sales_person;
	} catch (e) {
		optionsError.value = "Your user is not linked to a Sales Person. Ask an administrator to set it on your Employee record.";
	}
});
</script>

<template>
	<div class="tw-mx-auto tw-flex tw-max-w-[1400px] tw-flex-col tw-gap-6 tw-py-4">
		<div
			v-if="optionsError"
			class="tw-rounded-2xl tw-border tw-border-solid tw-border-line tw-bg-surface tw-px-6 tw-py-16 tw-text-center tw-text-sm tw-text-muted"
		>
			{{ optionsError }}
		</div>

		<template v-else-if="options">
			<FilterBar
				v-model:company="company"
				v-model:period="period"
				:title="salesPerson"
				:subtitle="subtitle"
				:companies="options.companies"
				:periods="options.periods"
				@refresh="loadAll"
			>
				<label
					v-if="options.can_choose"
					class="tw-m-0 tw-flex tw-items-center tw-gap-2 tw-text-xs tw-font-medium tw-text-muted"
				>
					Sales rep
					<select
						v-model="salesPerson"
						class="tw-h-8 tw-max-w-[200px] tw-cursor-pointer tw-rounded-lg tw-border tw-border-solid tw-border-line tw-bg-surface tw-px-2 tw-text-sm tw-text-ink"
					>
						<option v-for="sp in options.sales_persons" :key="sp" :value="sp">{{ sp }}</option>
					</select>
				</label>
			</FilterBar>

			<div class="tw-grid tw-grid-cols-1 tw-gap-4 sm:tw-grid-cols-2 xl:tw-grid-cols-4">
				<StatCard
					v-for="card in CARDS"
					:key="card.key"
					:label="cardValues[card.key]?.label || card.label"
					:value="cardValues[card.key]?.value ?? null"
					:fieldtype="cardValues[card.key]?.fieldtype"
					:currency="summary.data?.currency"
					:hint="cardHint(card)"
					:icon="card.icon"
					:gradient="card.gradient"
					:loading="summary.loading"
					:action-label="card.table ? `Show ${card.label}` : `Open ${card.label} list`"
					@open="openCard(card)"
				/>
			</div>

			<div class="tw-grid tw-grid-cols-1 tw-gap-4 lg:tw-grid-cols-2">
				<ChartCard
					v-for="chart in CHARTS"
					:key="chart.key"
					:title="chart.title"
					:subtitle="`${chart.subtitle} · ${period}`"
					:kind="chart.kind"
					:hue="chart.hue"
					:full="chart.full"
					:data="charts[chart.key].data"
					:loading="charts[chart.key].loading"
					:error="charts[chart.key].error"
					:dark="dark"
					@retry="loadAll"
				/>
			</div>

			<TargetsCard
				:sales-person="salesPerson"
				:period-types="options.target_period_types"
				:default-range="options.target_range"
				:dark="dark"
			/>

			<CustomerTable
				ref="tableEl"
				v-model:filter="customerFilter"
				class="tw-scroll-mt-20"
				:customers="customers.data?.customers || []"
				:currency="customers.data?.currency"
				:period="period"
				:from-date="summary.data?.from_date"
				:loading="customers.loading"
			/>
		</template>
	</div>
</template>
