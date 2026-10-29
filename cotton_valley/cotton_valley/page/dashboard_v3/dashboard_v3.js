// Vue rebuild of "Dashboard V2". The app lives in apps/cotton_valley/dashboard and is
// built into public/dashboards (`bench build --app cotton_valley` or `yarn build`).
frappe.pages["dashboard-v3"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Dashboard V3"),
		single_column: true,
	});

	page.add_menu_item(__("Open Dashboard V2"), () =>
		frappe.set_route("dashboard-view", "Dashboard V2")
	);

	const $root = $('<div class="cv-dash"><div></div></div>').appendTo(page.main);

	import_dashboard_entry("src/dashboard_v3.js")
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
// Same loader as the sales-rep-dashboard page.
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
