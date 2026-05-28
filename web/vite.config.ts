import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { fileURLToPath, URL } from "node:url";

// Served under the GitHub Pages subpath /Quantify-Viability/app/.
export default defineConfig({
  base: "/Quantify-Viability/app/",
  plugins: [svelte()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: { outDir: "../dist/app", emptyOutDir: true },
  test: {
    globals: true,
    environment: "node",
    include: ["tests/**/*.test.ts", "src/**/*.test.ts"],
  },
});
