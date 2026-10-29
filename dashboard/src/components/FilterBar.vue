<script setup>
// One filter row that scopes everything below it. Extra controls go in the default slot.
defineProps({
	title: { type: String, required: true },
	subtitle: { type: String, default: "" },
	companies: { type: Array, default: () => [] },
	periods: { type: Array, default: () => [] },
});

const company = defineModel("company", { type: String, default: "" });
const period = defineModel("period", { type: String, required: true });
defineEmits(["refresh"]);
</script>

<template>
	<div class="tw-flex tw-flex-wrap tw-items-end tw-justify-between tw-gap-4">
		<div class="tw-min-w-0">
			<h2 class="tw-m-0 tw-text-xl tw-font-semibold tw-text-ink">{{ title }}</h2>
			<p v-if="subtitle" class="tw-m-0 tw-mt-1 tw-text-xs tw-text-muted">{{ subtitle }}</p>
		</div>

		<div class="tw-flex tw-flex-wrap tw-items-center tw-gap-3">
			<slot />

			<label class="tw-m-0 tw-flex tw-items-center tw-gap-2 tw-text-xs tw-font-medium tw-text-muted">
				Company
				<select
					v-model="company"
					class="tw-h-8 tw-cursor-pointer tw-rounded-lg tw-border tw-border-solid tw-border-line tw-bg-surface tw-px-2 tw-text-sm tw-text-ink"
				>
					<option value="">All companies</option>
					<option v-for="c in companies" :key="c" :value="c">{{ c }}</option>
				</select>
			</label>

			<div class="tw-flex tw-items-center tw-gap-2 tw-text-xs tw-font-medium tw-text-muted">
				<span>Period</span>
				<div class="tw-flex tw-rounded-lg tw-bg-control tw-p-0.5" role="group" aria-label="Period">
					<button
						v-for="p in periods"
						:key="p"
						type="button"
						class="tw-cursor-pointer tw-whitespace-nowrap tw-rounded-md tw-border-0 tw-px-2.5 tw-py-1 tw-text-xs tw-font-medium tw-transition"
						:class="period === p ? 'tw-bg-surface tw-text-ink tw-shadow-sm' : 'tw-bg-transparent tw-text-muted hover:tw-text-ink'"
						:aria-pressed="period === p"
						@click="period = p"
					>
						{{ p.replace("Last ", "") }}
					</button>
				</div>
			</div>

			<button
				type="button"
				class="tw-flex tw-h-8 tw-cursor-pointer tw-items-center tw-gap-1.5 tw-rounded-lg tw-border tw-border-solid tw-border-line tw-bg-surface tw-px-3 tw-text-xs tw-font-medium tw-text-ink hover:tw-bg-control"
				@click="$emit('refresh')"
			>
				<svg class="tw-h-3.5 tw-w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<path d="M21 12a9 9 0 1 1-6.22-8.56" /><path d="M21 3v6h-6" />
				</svg>
				Refresh
			</button>
		</div>
	</div>
</template>
