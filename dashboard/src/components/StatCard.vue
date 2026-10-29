<script setup>
import { computed } from "vue";
import { formatValue } from "../format";

const props = defineProps({
	label: { type: String, required: true },
	value: { type: Number, default: null },
	fieldtype: { type: String, default: "Int" },
	currency: { type: String, default: null },
	hint: { type: String, default: "" },
	icon: { type: String, required: true },
	gradient: { type: String, required: true },
	loading: { type: Boolean, default: false },
	actionLabel: { type: String, default: "" },
});

defineEmits(["open"]);

const display = computed(() =>
	formatValue(props.value, props.fieldtype, props.currency, {
		compact: props.fieldtype === "Currency",
	})
);

// Currency is shown compact, so the exact amount goes in the hint line
const hintText = computed(() =>
	props.fieldtype === "Currency" ? formatValue(props.value, props.fieldtype, props.currency) : props.hint
);
</script>

<template>
	<button
		type="button"
		class="tw-group tw-relative tw-w-full tw-cursor-pointer tw-overflow-hidden tw-rounded-2xl tw-border-0 tw-bg-gradient-to-br tw-p-5 tw-text-left tw-text-white tw-shadow-sm tw-transition tw-duration-200 hover:-tw-translate-y-0.5 hover:tw-shadow-lg focus-visible:tw-outline focus-visible:tw-outline-2 focus-visible:tw-outline-offset-2 focus-visible:tw-outline-white motion-reduce:tw-transition-none"
		:class="gradient"
		:title="actionLabel || `Open ${label} list`"
		@click="$emit('open')"
	>
		<span
			class="tw-pointer-events-none tw-absolute -tw-right-8 -tw-top-8 tw-h-28 tw-w-28 tw-rounded-full tw-bg-white/10 tw-transition-transform tw-duration-300 group-hover:tw-scale-110"
		/>
		<span
			class="tw-pointer-events-none tw-absolute -tw-bottom-10 tw-right-10 tw-h-20 tw-w-20 tw-rounded-full tw-bg-white/10"
		/>

		<span class="tw-relative tw-flex tw-items-start tw-justify-between tw-gap-3">
			<span class="tw-text-[13px] tw-font-medium tw-text-white/90">{{ label }}</span>
			<span class="tw-grid tw-h-9 tw-w-9 tw-shrink-0 tw-place-items-center tw-rounded-xl tw-bg-white/20">
				<svg
					class="tw-h-[18px] tw-w-[18px]"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
					aria-hidden="true"
					v-html="icon"
				/>
			</span>
		</span>

		<template v-if="loading && value === null">
			<span class="cv-skeleton tw-relative tw-mt-3 tw-block tw-h-8 tw-w-24 tw-rounded-md !tw-bg-white/20" />
			<span class="cv-skeleton tw-relative tw-mt-2 tw-block tw-h-3 tw-w-32 tw-rounded !tw-bg-white/20" />
		</template>
		<template v-else>
			<span
				class="tw-relative tw-mt-3 tw-block tw-text-[28px] tw-font-semibold tw-leading-tight tw-tracking-tight tw-transition-opacity"
				:class="{ 'tw-opacity-60': loading }"
			>
				{{ display }}
			</span>
			<span class="tw-relative tw-mt-1 tw-block tw-truncate tw-text-xs tw-text-white/80">{{ hintText }}</span>
		</template>
	</button>
</template>
