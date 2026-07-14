import tailwindcss from "@tailwindcss/vite";
import vue from "@vitejs/plugin-vue";
import path from "node:path";
import { defineConfig } from "vite";

/**
 * Visitor Widget 独立构建：Vue 与运行时依赖全部打入 ESM bundle，
 * 宿主站点只需要加载一个入口脚本即可注册 Web Component。
 */
export default defineConfig({
  base: "./",
  plugins: [
    vue({
      template: {
        compilerOptions: {
          isCustomElement: (tag) => tag === "tada-ask-widget",
        },
      },
    }),
    tailwindcss(),
  ],
  resolve: {
    tsconfigPaths: true,
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "dist/widget",
    emptyOutDir: true, // build 时清空旧资源
    rolldownOptions: {
      input: path.resolve(__dirname, "src/widget/main.ts"),
      output: {
        format: "es",
        // 打包后的入口文件
        entryFileNames: "tada-ask-widget.js",
        // 后续可能的其它 JS 文件（目前不存在）
        chunkFileNames: "assets/[name]-[hash].js",
        // KaTeX 字体资源文件路径配置
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
});
