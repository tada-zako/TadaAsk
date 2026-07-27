import vue from "@vitejs/plugin-vue";
import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [
    vue({
      template: {
        compilerOptions: {
          isCustomElement: (tag) => tag === "tada-ask-widget",
        },
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.ts", "tests/**/*.spec.ts"],
    setupFiles: ["./tests/setup.ts"],
    clearMocks: true,
    restoreMocks: true,
    unstubEnvs: true,
    unstubGlobals: true,
    css: false,
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary", "html"],
      reportsDirectory: "./coverage",
      include: [
        "src/shared/api/**/*.ts",
        "src/shared/services/**/*.ts",
        "src/console/lib/**/*.ts",
        "src/console/services/**/*.ts",
        "src/console/stores/**/*.ts",
        "src/console/composables/**/*.ts",
        "src/widget/services/**/*.ts",
        "src/widget/composables/**/*.ts",
      ],
      exclude: [
        "src/shared/api/generated/**",
        "src/**/*.d.ts",
        "src/**/index.ts",
      ],
      // 阈值只约束相对稳定的核心逻辑范围，并为 MVP 阶段的快速迭代保留余量。
      thresholds: {
        statements: 50,
        branches: 40,
        functions: 45,
        lines: 50,
      },
    },
  },
});
