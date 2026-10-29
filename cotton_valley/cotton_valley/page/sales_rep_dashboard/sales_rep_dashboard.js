// Per-rep sales and customers. The app lives in apps/cotton_valley/dashboard and is
// built into public/dashboards (`bench build --app cotton_valley` or `yarn build`).
frappe.pages["sales-rep-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Sales Rep Dashboard"),
		single_column: true,
	});

	const $root = $('<div class="cv-dash"><div></div></div>').appendTo(page.main);

	import_dashboard_entry("src/sales_rep.js")
		.then(({ mount }) => mount($root.children()[0]))
		.catch((error) => {
			console.error(error);
			$root.html(`<div class="text-muted text-center" style="padding: 60px 15px;">
				${__("Dashboard assets are not built. Run {0} and reload.", [
					"<code>bench build --app cotton_valley</code>",
				])}
			</div>`);
		});
};

// Asset names are hashed, so read them from the Vite manifest (always revalidated).
// Same loader as the dashboard-v3 page.
async function import_dashboard_entry(src) {
	const base = "/assets/cotton_valley/dashboards/";
	const response = await fetch(`${base}manifest.json`, { cache: "no-cache" });
	if (!response.ok) throw new Error(`Dashboard manifest: HTTP ${response.status}`);
	const manifest = await response.json();

	const stylesheets = new Set();
	const collect = (key) => {
		const chunk = manifest[key];
		(chunk.css || []).forEach((file) => stylesheets.add(file));
		(chunk.imports || []).forEach(collect);
	};
	collect(src);

	stylesheets.forEach((file) => {
		if (!document.querySelector(`link[href="${base + file}"]`)) {
			$("<link>", { rel: "stylesheet", href: base + file }).appendTo("head");
		}
	});

	return import(base + manifest[src].file);
}
