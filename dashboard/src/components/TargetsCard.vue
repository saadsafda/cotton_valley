<script setup>
import { computed, ref, watch } from "vue";
import ApexChart from "./ApexChart.vue";
import { getRepTargets } from "../api";
import { buildTargetOptions } from "../charts";
import { formatValue } from "../format";
import { seriesColor } from "../theme";

// Has its own filters: they don't follow the page's company/period filters
const props = defineProps({
	salesPerson: { type: String, required: true },
	periodTypes: { type: Array, default: () => ["Weekly", "Monthly", "Quarterly", "Yearly"] },
	defaultRange: { type: Object, required: true },
	dark: { type: Boolean, default: false },
});

const periodType = ref("Monthly");
const fromDate = ref(props.defaultRange.from_date);
const toDate = ref(props.defaultRange.to_date);
const category = ref("");
const subcategory = ref("");
const measure = ref("amount");
const view = ref("chart");

const data = ref(null);
const loading = ref(false);
const error = ref(null);

let request = 0;
async function load() {
	const id = ++request;
	loading.value = true;
	error.value = null;
	try {
		const result = await getRepTargets(
			props.salesPerson,
			periodType.value,
			fromDate.value,
			toDate.value,
			category.value || null,
			subcategory.value || null
		);
		if (id === request) data.value = result;
	} catch (e) {
		if (id === request) error.value = "Could not load targets";
	} finally {
		if (id === request) loading.value = false;
	}
}

// weekly targets are expensive to compute, so weekly starts on the last 12 weeks
watch(periodType, (type) => {
	if (type === "Weekly") {
		toDate.value = frappe.datetime.get_today();
		fromDate.value = frappe.datetime.add_days(toDate.value, -83);
	} else if (type !== "Weekly" && frappe.datetime.get_day_diff(toDate.value, fromDate.value) < 85) {
		fromDate.value = props.defaultRange.from_date;
		toDate.value = props.defaultRange.to_date;
	}
});

// a different rep has different target categories; a new category has other subcategories
watch(() => props.salesPerson, () => (category.value = ""));
watch(category, () => (subcategory.value = ""));
watch([() => props.salesPerson, periodType, fromDate, toDate, category, subcategory], load, { immediate: true });

const fieldtype = computed(() => (measure.value === "amount" ? "Currency" : "Float"));
const currency = computed(() => data.value?.currency);
const pick = (row, kind) => row[`${kind}_${measure.value === "amount" ? "amount" : "qty"}`];
const fmt = (v) => formatValue(v, fieldtype.value, currency.value);
const pct = (achieved, target) => (target ? Math.round((achieved / target) * 100) : 0);

const hasTargets = computed(() => (data.value?.totals?.target_amount || data.value?.totals?.target_qty) > 0);

const summary = computed(() => {
	if (!data.value) return null;
	const target = pick(data.value.totals, "target");
	const achieved = pick(data.value.totals, "achieved");
	return { target, achieved, remaining: Math.max(target - achieved, 0), percent: pct(achieved, target) };
});

const options = computed(() =>
	data.value && hasTargets.value
		? buildTargetOptions({
				labels: data.value.labels,
				target: data.value.periods.map((p) => pick(p, "target")),
				achieved: data.value.periods.map((p) => pick(p, "achieved")),
				fieldtype: fieldtype.value,
				currency: currency.value,
				dark: props.dark,
				height: 300,
			})
		: null
);

// Drill-down list: categories -> subcategories of `category` -> items of `subcategory`
const BREAKDOWN_PAGE = 20;
const breakdownLimit = ref(BREAKDOWN_PAGE);
const level = computed(() => data.value?.breakdown?.level || "category");
const breakdown = computed(() =>
	(data.value?.breakdown?.rows || []).map((row) => {
		const target = pick(row, "target");
		const achieved = pick(row, "achieved");
		return { key: row.key, name: row.label, target, achieved, percent: pct(achieved, target) };
	})
);
watch(data, () => (breakdownLimit.value = BREAKDOWN_PAGE));

const LEVEL_TITLES = { category: "By category", subcategory: "By subcategory", item: "By item" };

function drillInto(row) {
	if (!row.key) return;
	if (level.value === "category") category.value = row.key;
	else if (level.value === "subcategory") subcategory.value = row.key;
}

const barColor = computed(() => seriesColor("blue", props.dark));
const controlClass =
	"tw-h-8 tw-rounded-lg tw-border tw-border-solid tw-border-line tw-bg-surface tw-px-2 tw-text-sm tw-text-ink";
const segmentClass = (active, activeBg = "tw-bg-surface") =>
	`tw-cursor-pointer tw-whitespace-nowrap tw-rounded-md tw-border-0 tw-px-2.5 tw-py-1 tw-text-xs tw-font-medium tw-transition ${
		active ? `${activeBg} tw-text-ink tw-shadow-sm` : "tw-bg-transparent tw-text-muted hover:tw-text-ink"
	}`;
</script>

<template>
	<section class="tw-rounded-2xl tw-border tw-border-solid tw-border-line tw-bg-surface tw-p-5 tw-shadow-sm">
		<header class="tw-mb-4 tw-flex tw-flex-wrap tw-items-start tw-justify-between tw-gap-3">
			<div>
				<h3 class="tw-m-0 tw-text-[15px] tw-font-semibold tw-text-ink">Sales Person Targets</h3>
				<p class="tw-m-0 tw-mt-0.5 tw-text-xs tw-text-muted">
					Target vs achieved from the SR target report · own filters
				</p>
			</div>
			<div class="tw-flex tw-shrink-0 tw-rounded-lg tw-bg-control tw-p-0.5" role="group" aria-label="View">
				<button
					v-for="v in ['chart', 'table']"
					:key="v"
					type="button"
					:class="segmentClass(view === v) + ' tw-capitalize'"
					:aria-pressed="view === v"
					@click="view = v"
				>
					{{ v }}
				</button>
			</div>
		</header>

		<!-- filters scoped to this card -->
		<div class="tw-mb-5 tw-flex tw-flex-wrap tw-items-center tw-gap-3 tw-rounded-xl tw-bg-control tw-p-3">
			<label class="tw-m-0 tw-flex tw-items-center tw-gap-2 tw-text-xs tw-font-medium tw-text-muted">
				Period
				<select v-model="periodType" :class="controlClass + ' tw-cursor-pointer'">
					<option v-for="p in periodTypes" :key="p" :value="p">{{ p }}</option>
				</select>
			</label>
			<label class="tw-m-0 tw-flex tw-items-center tw-gap-2 tw-text-xs tw-font-medium tw-text-muted">
				From
				<input v-model="fromDate" type="date" :max="toDate" :class="controlClass" />
			</label>
			<label class="tw-m-0 tw-flex tw-items-center tw-gap-2 tw-text-xs tw-font-medium tw-text-muted">
				To
				<input v-model="toDate" type="date" :min="fromDate" :class="controlClass" />
			</label>
			<label class="tw-m-0 tw-flex tw-items-center tw-gap-2 tw-text-xs tw-font-medium tw-text-muted">
				Category
				<select v-model="category" :class="controlClass + ' tw-max-w-[180px] tw-cursor-pointer'">
					<option value="">All categories</option>
					<option v-for="c in data?.category_options || []" :key="c.value" :value="c.value">{{ c.label }}</option>
				</select>
			</label>
			<div class="tw-ml-auto tw-flex tw-rounded-lg tw-bg-surface tw-p-0.5" role="group" aria-label="Measure">
				<button
					v-for="m in [{ key: 'amount', label: 'Amount' }, { key: 'qty', label: 'Qty' }]"
					:key="m.key"
					type="button"
					:class="segmentClass(measure === m.key, 'tw-bg-control')"
					:aria-pressed="measure === m.key"
					@click="measure = m.key"
				>
					{{ m.label }}
				</button>
			</div>
		</div>

		<div v-if="loading && !data" class="tw-flex tw-flex-col tw-gap-3">
			<div class="tw-grid tw-grid-cols-2 tw-gap-3 md:tw-grid-cols-4">
				<div v-for="i in 4" :key="i" class="cv-skeleton tw-h-[68px] tw-rounded-xl" />
			</div>
			<div class="cv-skeleton tw-h-[300px] tw-rounded-xl" />
		</div>

		<div v-else-if="error" class="tw-flex tw-min-h-[200px] tw-flex-col tw-items-center tw-justify-center tw-gap-3">
			<p class="tw-m-0 tw-text-sm tw-text-muted">{{ error }}</p>
			<button
				type="button"
				class="tw-cursor-pointer tw-rounded-lg tw-border tw-border-solid tw-border-line tw-bg-surface tw-px-3 tw-py-1.5 tw-text-xs tw-font-medium tw-text-ink hover:tw-bg-control"
				@click="load"
			>
				Try again
			</button>
		</div>

		<div
			v-else-if="data && !hasTargets"
			class="tw-flex tw-min-h-[200px] tw-items-center tw-justify-center tw-text-center tw-text-sm tw-text-muted"
		>
			No targets set for {{ salesPerson }} in this range. Targets are set on the Sales Person record.
		</div>

		<div v-else-if="data" class="tw-transition-opacity tw-duration-200" :class="{ 'tw-opacity-50': loading }">
			<div class="tw-mb-5 tw-grid tw-grid-cols-2 tw-gap-3 md:tw-grid-cols-4">
				<div class="tw-rounded-xl tw-bg-control tw-px-4 tw-py-3">
					<div class="tw-text-xs tw-text-muted">Target</div>
					<div class="tw-mt-1 tw-text-lg tw-font-semibold tw-text-ink">{{ fmt(summary.target) }}</div>
				</div>
				<div class="tw-rounded-xl tw-bg-control tw-px-4 tw-py-3">
					<div class="tw-text-xs tw-text-muted">Achieved</div>
					<div class="tw-mt-1 tw-text-lg tw-font-semibold tw-text-ink">{{ fmt(summary.achieved) }}</div>
				</div>
				<div class="tw-rounded-xl tw-bg-control tw-px-4 tw-py-3">
					<div class="tw-text-xs tw-text-muted">Remaining</div>
					<div class="tw-mt-1 tw-text-lg tw-font-semibold tw-text-ink">{{ fmt(summary.remaining) }}</div>
				</div>
				<div class="tw-rounded-xl tw-bg-control tw-px-4 tw-py-3">
					<div class="tw-flex tw-items-baseline tw-justify-between">
						<span class="tw-text-xs tw-text-muted">Achievement</span>
						<span class="tw-text-lg tw-font-semibold tw-text-ink">{{ summary.percent }}%</span>
					</div>
					<div class="tw-mt-2.5 tw-h-1.5 tw-overflow-hidden tw-rounded-full tw-bg-surface" role="progressbar" :aria-valuenow="summary.percent" aria-valuemin="0" aria-valuemax="100">
						<div class="tw-h-full tw-rounded-full" :style="{ width: `${Math.min(summary.percent, 100)}%`, background: barColor }" />
					</div>
				</div>
			</div>

			<template v-if="view === 'chart'">
				<ApexChart :options="options" />

				<div class="tw-mb-3 tw-mt-6 tw-flex tw-flex-wrap tw-items-baseline tw-gap-x-3 tw-gap-y-1">
					<h4 class="tw-m-0 tw-text-[13px] tw-font-semibold tw-text-ink">{{ LEVEL_TITLES[level] }}</h4>
					<nav v-if="category" class="tw-flex tw-flex-wrap tw-items-center tw-gap-1 tw-text-xs tw-text-muted" aria-label="Breadcrumb">
						<button type="button" class="tw-cursor-pointer tw-border-0 tw-bg-transparent tw-p-0 tw-text-xs tw-text-muted hover:tw-text-ink hover:tw-underline" @click="category = ''">
							All categories
						</button>
						<span aria-hidden="true">›</span>
						<button
							v-if="subcategory"
							type="button"
							class="tw-cursor-pointer tw-border-0 tw-bg-transparent tw-p-0 tw-text-xs tw-text-muted hover:tw-text-ink hover:tw-underline"
							@click="subcategory = ''"
						>
							{{ data.breakdown.category_label }}
						</button>
						<span v-else class="tw-font-medium tw-text-ink">{{ data.breakdown.category_label }}</span>
						<template v-if="subcategory">
							<span aria-hidden="true">›</span>
							<span class="tw-font-medium tw-text-ink">{{ data.breakdown.subcategory_label }}</span>
						</template>
					</nav>
					<span v-if="level !== 'item'" class="tw-text-xs tw-text-muted">· click a row to drill down</span>
				</div>
				<ul class="tw-m-0 tw-grid tw-list-none tw-grid-cols-1 tw-gap-x-8 tw-gap-y-1 tw-p-0 md:tw-grid-cols-2">
					<li v-for="row in breakdown.slice(0, breakdownLimit)" :key="row.key || row.name">
						<component
							:is="level === 'item' || !row.key ? 'div' : 'button'"
							:type="level === 'item' || !row.key ? undefined : 'button'"
							class="tw-group tw-block tw-w-full tw-rounded-lg tw-border-0 tw-bg-transparent tw-px-2 tw-py-1.5 tw-text-left"
							:class="level === 'item' || !row.key ? '' : 'tw-cursor-pointer hover:tw-bg-control'"
							:title="level === 'item' || !row.key ? row.name : `Show ${level === 'category' ? 'subcategories' : 'items'} of ${row.name}`"
							@click="drillInto(row)"
						>
							<span class="tw-flex tw-items-baseline tw-justify-between tw-gap-3 tw-text-sm">
								<span class="tw-flex tw-min-w-0 tw-items-center tw-gap-1 tw-font-medium tw-text-ink">
									<span class="tw-truncate">{{ row.name }}</span>
									<span v-if="level !== 'item' && row.key" class="tw-shrink-0 tw-text-muted tw-opacity-0 tw-transition-opacity group-hover:tw-opacity-100" aria-hidden="true">›</span>
								</span>
								<span class="tw-shrink-0 tw-text-xs tw-tabular-nums tw-text-muted">
									{{ fmt(row.achieved) }} / {{ fmt(row.target) }} · <span class="tw-font-semibold tw-text-ink">{{ row.percent }}%</span>
								</span>
							</span>
							<span class="tw-mt-1.5 tw-block tw-h-1.5 tw-overflow-hidden tw-rounded-full tw-bg-control">
								<span class="tw-block tw-h-full tw-rounded-full" :style="{ width: `${Math.min(row.percent, 100)}%`, background: barColor }" />
							</span>
						</component>
					</li>
				</ul>
				<div v-if="breakdown.length > breakdownLimit" class="tw-mt-3 tw-text-center">
					<button
						type="button"
						class="tw-cursor-pointer tw-rounded-lg tw-border tw-border-solid tw-border-line tw-bg-surface tw-px-3 tw-py-1.5 tw-text-xs tw-font-medium tw-text-ink hover:tw-bg-control"
						@click="breakdownLimit += BREAKDOWN_PAGE"
					>
						Show more ({{ breakdown.length - breakdownLimit }} left)
					</button>
				</div>
			</template>

			<div v-else class="tw-overflow-x-auto">
				<table class="tw-w-full tw-min-w-[560px] tw-border-collapse tw-text-sm">
					<thead>
						<tr class="tw-text-left tw-text-xs tw-text-muted">
							<th class="tw-border-0 tw-border-b tw-border-solid tw-border-line tw-py-2 tw-pr-3 tw-font-medium">Period</th>
							<th
								v-for="h in ['Target', 'Achieved', 'Remaining', 'Achievement']"
								:key="h"
								class="tw-border-0 tw-border-b tw-border-solid tw-border-line tw-py-2 tw-pl-3 tw-text-right tw-font-medium"
							>
								{{ h }}
							</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="(label, i) in data.labels" :key="label" class="hover:tw-bg-control">
							<td class="tw-border-0 tw-border-b tw-border-solid tw-border-line tw-py-2 tw-pr-3 tw-text-ink">{{ label }}</td>
							<td class="tw-border-0 tw-border-b tw-border-solid tw-border-line tw-py-2 tw-pl-3 tw-text-right tw-tabular-nums tw-text-ink">
								{{ fmt(pick(data.periods[i], "target")) }}
							</td>
							<td class="tw-border-0 tw-border-b tw-border-solid tw-border-line tw-py-2 tw-pl-3 tw-text-right tw-tabular-nums tw-text-ink">
								{{ fmt(pick(data.periods[i], "achieved")) }}
							</td>
							<td class="tw-border-0 tw-border-b tw-border-solid tw-border-line tw-py-2 tw-pl-3 tw-text-right tw-tabular-nums tw-text-ink">
								{{ fmt(Math.max(pick(data.periods[i], "target") - pick(data.periods[i], "achieved"), 0)) }}
							</td>
							<td class="tw-border-0 tw-border-b tw-border-solid tw-border-line tw-py-2 tw-pl-3 tw-text-right tw-tabular-nums tw-text-ink">
								{{ pct(pick(data.periods[i], "achieved"), pick(data.periods[i], "target")) }}%
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</section>
</template>
