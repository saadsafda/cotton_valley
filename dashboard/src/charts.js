import { formatValue } from "./format";
import { chrome, seriesColor, statusColor } from "./theme";

function escapeHtml(text) {
	return String(text).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

// Tooltip listing every measure the report returned, not only the plotted one
function tooltipHtml(data, index, currency) {
	const rows = data.datasets
		.map(
			(ds) =>
				`<div class="cv-tooltip-row"><span>${escapeHtml(ds.name)}</span>` +
				`<span>${escapeHtml(formatValue(ds.values[index], ds.fieldtype, currency))}</span></div>`
		)
		.join("");
	return `<div class="cv-tooltip"><div class="cv-tooltip-title">${escapeHtml(
		data.labels[index]
	)}</div>${rows}</div>`;
}

function baseOptions(type, { dark, height }) {
	const c = chrome(dark);
	return {
		chart: {
			type,
			height,
			fontFamily: getComputedStyle(document.body).fontFamily,
			background: "transparent",
			toolbar: { show: false },
			zoom: { enabled: false },
			animations: { enabled: true, speed: 450 },
			parentHeightOffset: 0,
		},
		theme: { mode: dark ? "dark" : "light" },
		grid: {
			borderColor: c.grid,
			strokeDashArray: 0,
			xaxis: { lines: { show: false } },
			yaxis: { lines: { show: true } },
			padding: { left: 4, right: 12 },
		},
		dataLabels: { enabled: false },
		legend: { show: false },
		tooltip: { theme: dark ? "dark" : "light" },
		xaxis: {
			labels: { style: { colors: c.muted, fontSize: "11px" }, hideOverlappingLabels: true },
			axisBorder: { show: true, color: c.baseline },
			axisTicks: { show: false },
		},
		yaxis: { labels: { style: { colors: c.muted, fontSize: "11px" } } },
	};
}

function timeseriesOptions(type, data, { hue, dark, height, currency }) {
	const ds = data.datasets[0];
	const color = seriesColor(hue, dark);
	const options = baseOptions(type, { dark, height });
	const format = (v) => formatValue(v, ds.fieldtype, currency, { compact: true });

	Object.assign(options, {
		series: [{ name: ds.name, data: ds.values }],
		colors: [color],
		xaxis: { ...options.xaxis, categories: data.labels, tooltip: { enabled: false } },
		yaxis: { ...options.yaxis, labels: { ...options.yaxis.labels, formatter: format } },
		tooltip: {
			...options.tooltip,
			y: { formatter: (v) => formatValue(v, ds.fieldtype, currency) },
		},
	});

	if (type === "bar") {
		options.plotOptions = {
			bar: { borderRadius: 4, borderRadiusApplication: "end", columnWidth: "55%" },
		};
	} else {
		options.stroke = { curve: "smooth", width: 2 };
		options.markers = { size: 0, hover: { size: 5 }, strokeColors: chrome(dark).surface, strokeWidth: 2 };
		options.fill = {
			type: "gradient",
			gradient: { shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0.02, stops: [0, 95, 100] },
		};
	}
	return options;
}

function rankingOptions(data, { hue, dark, height, currency, full }) {
	const ds = data.datasets[0];
	const options = baseOptions("bar", { dark, height });

	Object.assign(options, {
		series: [{ name: ds.name, data: ds.values }],
		colors: [seriesColor(hue, dark)],
		plotOptions: {
			bar: { horizontal: true, borderRadius: 4, borderRadiusApplication: "end", barHeight: "58%" },
		},
		grid: {
			...options.grid,
			xaxis: { lines: { show: true } },
			yaxis: { lines: { show: false } },
			// room for the category labels so their first characters aren't clipped
			padding: { ...options.grid.padding, left: 12 },
		},
		xaxis: {
			...options.xaxis,
			categories: data.labels,
			labels: {
				...options.xaxis.labels,
				formatter: (v) => formatValue(v, ds.fieldtype, currency, { compact: true }),
			},
		},
		// full-width cards have room for longer names (e.g. item names)
		yaxis: { labels: { ...options.yaxis.labels, maxWidth: full ? 220 : 140 } },
		tooltip: {
			...options.tooltip,
			custom: ({ dataPointIndex }) => tooltipHtml(data, dataPointIndex, currency),
		},
	});
	return options;
}

function statusBarOptions(data, { dark, height, currency }) {
	const ds = data.datasets[0];
	const options = baseOptions("bar", { dark, height });

	Object.assign(options, {
		series: [{ name: ds.name, data: ds.values }],
		colors: data.labels.map((status) => statusColor(status, dark)),
		plotOptions: {
			bar: { distributed: true, borderRadius: 4, borderRadiusApplication: "end", columnWidth: "45%" },
		},
		xaxis: { ...options.xaxis, categories: data.labels },
		yaxis: {
			labels: {
				...options.yaxis.labels,
				formatter: (v) => formatValue(v, ds.fieldtype, currency, { compact: true }),
			},
		},
		tooltip: {
			...options.tooltip,
			custom: ({ dataPointIndex }) => tooltipHtml(data, dataPointIndex, currency),
		},
	});
	return options;
}

function donutOptions(data, { dark, height, currency }) {
	const ds = data.datasets[0];
	const options = baseOptions("donut", { dark, height });

	Object.assign(options, {
		series: ds.values,
		labels: data.labels,
		colors: data.labels.map((status) => statusColor(status, dark)),
		stroke: { width: 2, colors: [chrome(dark).surface] },
		plotOptions: {
			pie: {
				expandOnClick: false,
				donut: {
					size: "70%",
					labels: {
						show: true,
						value: {
							color: dark ? "#f0efec" : "#0b0b0b",
							fontSize: "22px",
							fontWeight: 600,
							formatter: (v) => formatValue(v, ds.fieldtype, currency),
						},
						total: {
							show: true,
							label: ds.name,
							color: chrome(dark).muted,
							fontSize: "12px",
							formatter: (w) =>
								formatValue(
									w.globals.seriesTotals.reduce((a, b) => a + b, 0),
									ds.fieldtype,
									currency
								),
						},
					},
				},
			},
		},
		tooltip: {
			...options.tooltip,
			custom: ({ seriesIndex }) => tooltipHtml(data, seriesIndex, currency),
		},
	});
	return options;
}

// Achieved (bars) against target (line) on one shared axis
export function buildTargetOptions({ labels, target, achieved, fieldtype, currency, dark, height }) {
	const options = baseOptions("line", { dark, height });
	const format = (v) => formatValue(v, fieldtype, currency, { compact: true });

	return Object.assign(options, {
		series: [
			{ name: "Achieved", type: "column", data: achieved },
			{ name: "Target", type: "line", data: target },
		],
		colors: [seriesColor("blue", dark), seriesColor("orange", dark)],
		stroke: { width: [0, 2], curve: "straight" },
		markers: { size: [0, 4], strokeColors: chrome(dark).surface, strokeWidth: 2, hover: { sizeOffset: 2 } },
		plotOptions: { bar: { borderRadius: 4, borderRadiusApplication: "end", columnWidth: "50%" } },
		legend: {
			show: true,
			position: "top",
			horizontalAlign: "right",
			labels: { colors: chrome(dark).muted },
			markers: { width: 10, height: 10, radius: 10 },
		},
		xaxis: { ...options.xaxis, categories: labels, tooltip: { enabled: false } },
		yaxis: { labels: { ...options.yaxis.labels, formatter: format } },
		tooltip: {
			...options.tooltip,
			shared: true,
			intersect: false,
			y: { formatter: (v) => formatValue(v, fieldtype, currency) },
		},
	});
}

export function buildChartOptions(kind, data, settings) {
	switch (kind) {
		case "column":
			return timeseriesOptions("bar", data, settings);
		case "area":
			return timeseriesOptions("area", data, settings);
		case "ranking":
			return rankingOptions(data, settings);
		case "status-bar":
			return statusBarOptions(data, settings);
		case "donut":
			return donutOptions(data, settings);
	}
}
