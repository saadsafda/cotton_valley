<script setup>
import { computed, ref } from "vue";
import ApexChart from "./ApexChart.vue";
import { buildChartOptions } from "../charts";
import { formatValue } from "../format";
import { statusColor } from "../theme";

const props = defineProps({
	title: { type: String, required: true },
	subtitle: { type: String, default: "" },
	kind: { type: String, required: true },
	hue: { type: String, default: "blue" },
	full: { type: Boolean, default: false },
	data: { type: Object, default: null },
	loading: { type: Boolean, default: false },
	error: { type: String, default: null },
	dark: { type: Boolean, default: false },
});

defineEmits(["retry"]);

const view = ref("chart");
const height = computed(() => (props.full ? 300 : 280));
const currency = computed(() => props.data?.currency);

const isEmpty = computed(() => {
	const values = props.data?.datasets?.[0]?.values || [];
	return !values.length || values.every((v) => !v);
});

const options = computed(() =>
	props.data && !isEmpty.value
		? buildChartOptions(props.kind, props.data, {
				hue: props.hue,
				dark: props.dark,
				height: height.value,
				full: props.full,
				currency: currency.value,
			})
		: null
);

// Donut legend: identity + value + share, so the chart never relies on color alone
const legend = computed(() => {
	if (props.kind !== "donut" || !props.data) return [];
	const ds = props.data.datasets[0];
	const total = ds.values.reduce((a, b) => a + b, 0) || 1;
	return props.data.labels.map((label, i) => ({
		label,
		color: statusColor(label, props.dark),
		value: formatValue(ds.values[i], ds.fieldtype, currency.value),
		share: Math.round((ds.values[i] / total) * 100),
	}));
});
</script>

<template>
	<section
		class="tw-flex tw-min-w-0 tw-flex-col tw-rounded-2xl tw-border tw-border-solid tw-border-line tw-bg-surface tw-p-5 tw-shadow-sm"
		:class="full ? 'lg:tw-col-span-2' : ''"
	>
		<header class="tw-mb-4 tw-flex tw-items-start tw-justify-between tw-gap-3">
			<div class="tw-min-w-0">
				<h3 class="tw-m-0 tw-text-[15px] tw-font-semibold tw-text-ink">{{ title }}</h3>
				<p v-if="subtitle" class="tw-m-0 tw-mt-0.5 tw-text-xs tw-text-muted">{{ subtitle }}</p>
			</div>
			<div
				v-if="data && !isEmpty"
				class="tw-flex tw-shrink-0 tw-rounded-lg tw-bg-control tw-p-0.5"
				role="group"
				aria-label="View"
			>
				<button
					v-for="v in ['chart', 'table']"
					:key="v"
					type="button"
					class="tw-cursor-pointer tw-rounded-md tw-border-0 tw-px-2.5 tw-py-1 tw-text-xs tw-font-medium tw-capitalize tw-transition"
					:class="view === v ? 'tw-bg-surface tw-text-ink tw-shadow-sm' : 'tw-bg-transparent tw-text-muted hover:tw-text-ink'"
					:aria-pressed="view === v"
					@click="view = v"
				>
					{{ v }}
				</button>
			</div>
		</header>

		<div class="tw-relative tw-flex-1" :style="{ minHeight: `${height}px` }">
			<!-- first load -->
			<div v-if="loading && !data" class="tw-flex tw-h-full tw-flex-col tw-justify-end tw-gap-3 tw-pt-4">
				<div class="tw-flex tw-h-[220px] tw-items-end tw-gap-3">
					<div
						v-for="h in [55, 80, 40, 95, 65, 75, 50]"
						:key="h"
						class="cv-skeleton tw-flex-1 tw-rounded-t-md"
						:style="{ height: `${h}%` }"
					/>
				</div>
				<div class="cv-skeleton tw-h-3 tw-rounded" />
			</div>

			<div
				v-else-if="error"
				class="tw-flex tw-h-full tw-flex-col tw-items-center tw-justify-center tw-gap-3 tw-text-center"
				:style="{ minHeight: `${height}px` }"
			>
				<p class="tw-m-0 tw-text-sm tw-text-muted">{{ error }}</p>
				<button
					type="button"
					class="tw-cursor-pointer tw-rounded-lg tw-border tw-border-solid tw-border-line tw-bg-surface tw-px-3 tw-py-1.5 tw-text-xs tw-font-medium tw-text-ink hover:tw-bg-control"
					@click="$emit('retry')"
				>
					Try again
				</button>
			</div>

			<div
				v-else-if="data && isEmpty"
				class="tw-flex tw-h-full tw-items-center tw-justify-center tw-text-sm tw-text-muted"
				:style="{ minHeight: `${height}px` }"
			>
				No data for this selection
			</div>

			<!-- refetch keeps the previous render, dimmed -->
			<div
				v-else-if="data"
				class="tw-transition-opacity tw-duration-200"
				:class="{ 'tw-opacity-50': loading }"
			>
				<template v-if="view === 'chart'">
					<div v-if="kind === 'donut'" class="tw-flex tw-flex-col tw-items-center tw-gap-4 sm:tw-flex-row">
						<ApexChart :options="options" class="tw-w-full tw-max-w-[280px] tw-shrink-0" />
						<ul class="tw-m-0 tw-flex tw-w-full tw-list-none tw-flex-col tw-gap-2 tw-p-0">
							<li
								v-for="item in legend"
								:key="item.label"
								class="tw-flex tw-items-center tw-gap-3 tw-rounded-lg tw-bg-control tw-px-3 tw-py-2 tw-text-sm"
							>
								<span class="tw-h-2.5 tw-w-2.5 tw-shrink-0 tw-rounded-full" :style="{ background: item.color }" />
								<span class="tw-flex-1 tw-text-ink">{{ item.label }}</span>
								<span class="tw-font-semibold tw-tabular-nums tw-text-ink">{{ item.value }}</span>
								<span class="tw-w-10 tw-text-right tw-text-xs tw-tabular-nums tw-text-muted">{{ item.share }}%</span>
							</li>
						</ul>
					</div>
					<ApexChart v-else :options="options" />
				</template>

				<div v-else class="tw-overflow-auto" :style="{ maxHeight: `${height}px` }">
					<table class="tw-w-full tw-border-collapse tw-text-sm">
						<thead>
							<tr class="tw-text-left tw-text-xs tw-text-muted">
								<th class="tw-sticky tw-top-0 tw-border-0 tw-border-b tw-border-solid tw-border-line tw-bg-surface tw-py-2 tw-pr-3 tw-font-medium">
									{{ data.x_label || "Period" }}
								</th>
								<th
									v-for="ds in data.datasets"
									:key="ds.name"
									class="tw-sticky tw-top-0 tw-border-0 tw-border-b tw-border-solid tw-border-line tw-bg-surface tw-py-2 tw-pl-3 tw-text-right tw-font-medium"
								>
									{{ ds.name }}
								</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="(label, i) in data.labels" :key="i" class="hover:tw-bg-control">
								<td class="tw-border-0 tw-border-b tw-border-solid tw-border-line tw-py-2 tw-pr-3 tw-text-ink">{{ label }}</td>
								<td
									v-for="ds in data.datasets"
									:key="ds.name"
									class="tw-border-0 tw-border-b tw-border-solid tw-border-line tw-py-2 tw-pl-3 tw-text-right tw-tabular-nums tw-text-ink"
								>
									{{ formatValue(ds.values[i], ds.fieldtype, currency) }}
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>
		</div>
	</section>
</template>
