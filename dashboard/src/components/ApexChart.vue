<script setup>
import ApexCharts from "apexcharts";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({ options: { type: Object, required: true } });

const el = ref(null);
let chart = null;

onMounted(() => {
	chart = new ApexCharts(el.value, props.options);
	chart.render();
});

watch(
	() => props.options,
	(options) => chart && chart.updateOptions(options, true, true)
);

onBeforeUnmount(() => {
	chart && chart.destroy();
	chart = null;
});
</script>

<template>
	<div ref="el" />
</template>
