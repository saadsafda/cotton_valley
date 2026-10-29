<script setup>
import { computed, ref, watch } from "vue";
import { formatValue } from "../format";

const props = defineProps({
	customers: { type: Array, default: () => [] },
	currency: { type: String, default: null },
	period: { type: String, required: true },
	fromDate: { type: String, default: null },
	loading: { type: Boolean, default: false },
});

const filter = defineModel("filter", { type: String, default: "all" });

const PAGE_SIZE = 25;
const search = ref("");
const sortKey = ref("sales");
const sortDesc = ref(true);
const limit = ref(PAGE_SIZE);

const COLUMNS = [
	{ key: "customer_name", label: "Customer" },
	{ key: "city", label: "Location" },
	{ key: "orders", label: "Orders", numeric: true },
	{ key: "sales", label: "Sales", numeric: true },
	{ key: "last_order", label: "Last order", numeric: true },
];

// "New" mirrors the New Customers card: created in the period (last 7 days for All Time)
const newSince = computed(
	() => props.fromDate || frappe.datetime.add_days(frappe.datetime.get_today(), -7)
);
const isNew = (c) => c.creation && c.creation.slice(0, 10) >= newSince.value;

const FILTERS = computed(() => [
	{ key: "all", label: "All", count: props.customers.length },
	{ key: "active", label: "Active", count: props.customers.filter((c) => c.active).length },
	{ key: "inactive", label: "Inactive", count: props.customers.filter((c) => !c.active).length },
	{ key: "new", label: "New", count: props.customers.filter(isNew).length },
]);

const rows = computed(() => {
	const q = search.value.trim().toLowerCase();
	const list = props.customers.filter((c) => {
		if (filter.value === "active" && !c.active) return false;
		if (filter.value === "inactive" && c.active) return false;
		if (filter.value === "new" && !isNew(c)) return false;
		if (!q) return true;
		return [c.customer_name, c.name, c.city, c.state].some((v) => v && v.toLowerCase().includes(q));
	});

	const dir = sortDesc.value ? -1 : 1;
	return list.sort((a, b) => {
		const x = a[sortKey.value] ?? "";
		const y = b[sortKey.value] ?? "";
		if (x === y) return 0;
		return (x > y ? 1 : -1) * dir;
	});
});

watch([search, filter, () => props.customers], () => (limit.value = PAGE_SIZE));

function sortBy(key) {
	if (sortKey.value === key) {
		sortDesc.value = !sortDesc.value;
	} else {
		sortKey.value = key;
		sortDesc.value = key !== "customer_name" && key !== "city";
	}
}

function openCustomer(name) {
	frappe.set_route("Form", "Customer", name);
}

function userDate(date) {
	return date ? frappe.datetime.str_to_user(date) : "";
}

function daysAgo(date) {
	if (!date) return "Never";
	const days = frappe.datetime.get_day_diff(frappe.datetime.get_today(), date);
	if (days <= 0) return "Today";
	if (days === 1) return "Yesterday";
	return `${days} days ago`;
}
</script>

<template>
	<section class="tw-rounded-2xl tw-border tw-border-solid tw-border-line tw-bg-surface tw-p-5 tw-shadow-sm">
		<header class="tw-mb-4 tw-flex tw-flex-wrap tw-items-end tw-justify-between tw-gap-3">
			<div>
				<h3 class="tw-m-0 tw-text-[15px] tw-font-semibold tw-text-ink">My Customers</h3>
				<p class="tw-m-0 tw-mt-0.5 tw-text-xs tw-text-muted">
					Orders and sales credited to this rep · {{ period }} · active = ordered in the period
				</p>
			</div>
			<div class="tw-flex tw-flex-wrap tw-items-center tw-gap-2">
				<div class="tw-flex tw-rounded-lg tw-bg-control tw-p-0.5" role="group" aria-label="Customer filter">
					<button
						v-for="f in FILTERS"
						:key="f.key"
						type="button"
						class="tw-cursor-pointer tw-whitespace-nowrap tw-rounded-md tw-border-0 tw-px-2.5 tw-py-1 tw-text-xs tw-font-medium tw-transition"
						:class="filter === f.key ? 'tw-bg-surface tw-text-ink tw-shadow-sm' : 'tw-bg-transparent tw-text-muted hover:tw-text-ink'"
						:aria-pressed="filter === f.key"
						@click="filter = f.key"
					>
						{{ f.label }} <span class="tw-tabular-nums tw-opacity-70">{{ f.count }}</span>
					</button>
				</div>
				<input
					v-model="search"
					type="search"
					placeholder="Search customers…"
					class="tw-h-8 tw-w-52 tw-rounded-lg tw-border tw-border-solid tw-border-line tw-bg-surface tw-px-3 tw-text-sm tw-text-ink"
				/>
			</div>
		</header>

		<div class="tw-overflow-x-auto tw-transition-opacity" :class="{ 'tw-opacity-50': loading }">
			<table class="tw-w-full tw-min-w-[640px] tw-border-collapse tw-text-sm">
				<thead>
					<tr class="tw-text-left tw-text-xs tw-text-muted">
						<th
							v-for="col in COLUMNS"
							:key="col.key"
							class="tw-border-0 tw-border-b tw-border-solid tw-border-line tw-py-2 tw-font-medium"
							:class="col.numeric ? 'tw-pl-3 tw-text-right' : 'tw-pr-3'"
							:aria-sort="sortKey === col.key ? (sortDesc ? 'descending' : 'ascending') : 'none'"
						>
							<button
								type="button"
								class="tw-cursor-pointer tw-border-0 tw-bg-transparent tw-p-0 tw-text-xs tw-font-medium tw-text-muted hover:tw-text-ink"
								@click="sortBy(col.key)"
							>
								{{ col.label }}
								<span v-if="sortKey === col.key" aria-hidden="true">{{ sortDesc ? "↓" : "↑" }}</span>
							</button>
						</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="c in rows.slice(0, limit)"
						:key="c.name"
						class="tw-cursor-pointer hover:tw-bg-control"
						@click="openCustomer(c.name)"
					>
						<td class="tw-border-0 tw-border-b tw-border-solid tw-border-line tw-py-2.5 tw-pr-3">
							<div class="tw-flex tw-items-center tw-gap-2">
								<span
									class="tw-h-2 tw-w-2 tw-shrink-0 tw-rounded-full"
									:class="c.active ? 'tw-bg-[#0ca30c]' : 'tw-bg-[#898781]'"
									aria-hidden="true"
								/>
								<span class="tw-truncate tw-font-medium tw-text-ink">{{ c.customer_name || c.name }}</span>
								<span v-if="isNew(c)" class="tw-rounded tw-bg-control tw-px-1.5 tw-text-[11px] tw-text-muted">New</span>
								<span v-if="c.disabled" class="tw-rounded tw-bg-control tw-px-1.5 tw-text-[11px] tw-text-muted">Disabled</span>
							</div>
						</td>
						<td class="tw-border-0 tw-border-b tw-border-solid tw-border-line tw-py-2.5 tw-pr-3 tw-text-muted">
							{{ [c.city, c.state].filter(Boolean).join(", ") || "—" }}
						</td>
						<td class="tw-border-0 tw-border-b tw-border-solid tw-border-line tw-py-2.5 tw-pl-3 tw-text-right tw-tabular-nums tw-text-ink">
							{{ c.orders }}
						</td>
						<td class="tw-border-0 tw-border-b tw-border-solid tw-border-line tw-py-2.5 tw-pl-3 tw-text-right tw-tabular-nums tw-text-ink">
							{{ formatValue(c.sales, "Currency", currency) }}
						</td>
						<td
							class="tw-border-0 tw-border-b tw-border-solid tw-border-line tw-py-2.5 tw-pl-3 tw-text-right tw-tabular-nums tw-text-muted"
							:title="userDate(c.last_order)"
						>
							{{ daysAgo(c.last_order) }}
						</td>
					</tr>
					<tr v-if="!rows.length">
						<td colspan="5" class="tw-py-10 tw-text-center tw-text-sm tw-text-muted">
							{{ loading ? "Loading customers…" : "No customers match" }}
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<div v-if="rows.length > limit" class="tw-mt-4 tw-text-center">
			<button
				type="button"
				class="tw-cursor-pointer tw-rounded-lg tw-border tw-border-solid tw-border-line tw-bg-surface tw-px-3 tw-py-1.5 tw-text-xs tw-font-medium tw-text-ink hover:tw-bg-control"
				@click="limit += PAGE_SIZE"
			>
				Show more ({{ rows.length - limit }} left)
			</button>
		</div>
	</section>
</template>
