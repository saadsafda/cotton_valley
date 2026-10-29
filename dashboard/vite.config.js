import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const src = (file) => fileURLToPath(new URL(`./src/${file}`, import.meta.url));

// One ES module per Desk page; Vue + ApexCharts end up in a shared chunk.
// File names are hashed for cache busting; the pages read them from manifest.json.
export default defineConfig({
	plugins: [vue()],
	base: "/assets/cotton_valley/dashboards/",
	build: {
		outDir: fileURLToPath(new URL("../cotton_valley/public/dashboards", import.meta.url)),
		emptyOutDir: true,
		manifest: "manifest.json",
		// ApexCharts is most of the shared chunk; it is loaded only on these pages
		chunkSizeWarningLimit: 800,
		rollupOptions: {
			input: {
				dashboard_v3: src("dashboard_v3.js"),
				sales_rep: src("sales_rep.js"),
			},
			// keep the `mount` export of each entry
			preserveEntrySignatures: "exports-only",
			output: {
				format: "es",
				entryFileNames: "[name].[hash].js",
				chunkFileNames: "shared.[hash].js",
				assetFileNames: "[name].[hash][extname]",
			},
		},
	},
});
