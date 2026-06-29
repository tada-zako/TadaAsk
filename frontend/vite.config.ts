import tailwindcss from "@tailwindcss/vite";
import vue from "@vitejs/plugin-vue";
import path from "node:path";
import { defineConfig } from "vite";
import VueDevTools from "vite-plugin-vue-devtools";

// https://vite.dev/config/
export default defineConfig({
  plugins: [VueDevTools(), vue(), tailwindcss()],
  resolve: {
    tsconfigPaths: true,
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
