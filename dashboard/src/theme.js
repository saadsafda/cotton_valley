import { onBeforeUnmount, ref } from "vue";

// Categorical palette, validated (CVD + contrast) against Desk's light and dark card surfaces.
// Dark values are the same hues stepped for the dark surface.
const SERIES = {
	blue: ["#2a78d6", "#3987e5"],
	orange: ["#eb6834", "#d95926"],
	aqua: ["#1baf7a", "#199e70"],
	magenta: ["#e87ba4", "#d55181"],
	green: ["#008300", "#008300"],
	violet: ["#6250d6", "#9085e9"],
};

// Order statuses keep the same color on every chart
const STATUS_HUES = { Processing: "blue", Pending: "orange", Shipped: "aqua" };

const CHROME = {
	light: { muted: "#898781", grid: "#e1e0d9", baseline: "#c3c2b7", surface: "#ffffff" },
	dark: { muted: "#898781", grid: "#2c2c2a", baseline: "#383835", surface: "#1c1c1c" },
};

export function seriesColor(hue, dark) {
	return SERIES[hue][dark ? 1 : 0];
}

export function statusColor(status, dark) {
	return seriesColor(STATUS_HUES[status] || "violet", dark);
}

export function chrome(dark) {
	return CHROME[dark ? "dark" : "light"];
}

function isDarkTheme() {
	return document.documentElement.getAttribute("data-theme") === "dark";
}

// Tracks Desk's theme switcher (it sets data-theme on <html>)
export function useDarkMode() {
	const dark = ref(isDarkTheme());
	const observer = new MutationObserver(() => (dark.value = isDarkTheme()));
	observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
	onBeforeUnmount(() => observer.disconnect());
	return dark;
}
