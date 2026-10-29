/** @type {import('tailwindcss').Config} */
export default {
	content: ["./src/**/*.{vue,js}"],
	// Runs inside Frappe Desk: prefix + scope every utility so nothing clashes
	// with Desk's Bootstrap classes (e.g. `.p-4`) or leaks onto other pages.
	prefix: "tw-",
	important: ".cv-dash",
	corePlugins: { preflight: false },
	darkMode: ["selector", '[data-theme="dark"]'],
	theme: {
		extend: {
			// Desk theme variables, so light/dark follow the user's Desk theme
			colors: {
				page: "var(--bg-color)",
				surface: "var(--card-bg)",
				ink: "var(--text-color)",
				muted: "var(--text-muted)",
				line: "var(--border-color)",
				control: "var(--control-bg)",
			},
		},
	},
};
