import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The console only talks to the back-office (same origin in production, proxied in dev).
const backoffice = process.env.HX_BACKOFFICE_URL ?? "http://127.0.0.1:8080";
const proxy = { "/v1": { target: backoffice, changeOrigin: false } };

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true, proxy },
  preview: { port: 4173, strictPort: true, proxy },
  build: {
    target: "es2022",
    sourcemap: true,
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, "index.html"),
        view3d: resolve(import.meta.dirname, "view3d.html"),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
    restoreMocks: true,
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/services/openapi.d.ts",
        "src/mocks/**",
        "src/test/**",
        "src/main.tsx",
        "src/features/vue3d/view3d-entry.ts",
        "src/features/vue3d/engine/**",
      ],
    },
  },
});
