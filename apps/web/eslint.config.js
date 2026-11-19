import js from "@eslint/js";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

// Layers (architecture 1.1.0 § 14): only socle/composition builds adapters; features and pages
// talk to ports; components are pure (no port, no server state).
const adapters = {
  group: ["**/services/http-api", "**/services/sse-stream", "openapi-fetch"],
  message: "Passer par les ports (useApi/useStream) : seul socle/composition construit les adaptateurs.",
};
const stateful = {
  group: ["**/socle/*", "**/features/*", "**/services/*", "@tanstack/react-query"],
  message: "Un composant ne connaît ni port ni état serveur : recevoir les données en props.",
};

export default tseslint.config(
  {
    ignores: [
      "dist",
      "coverage",
      "playwright-report",
      "test-results",
      "public/mockServiceWorker.js",
      "src/services/openapi.d.ts",
      "src/features/vue3d/engine/**",
    ],
  },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.strictTypeChecked,
      ...tseslint.configs.stylisticTypeChecked,
      jsxA11y.flatConfigs.recommended,
    ],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: {
        project: ["./tsconfig.app.json", "./tsconfig.node.json"],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["error", { allowConstantExport: true }],
      "@typescript-eslint/restrict-template-expressions": ["error", { allowNumber: true }],
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/no-confusing-void-expression": ["error", { ignoreArrowShorthand: true }],
      "@typescript-eslint/no-misused-promises": ["error", { checksVoidReturn: { attributes: false } }],
      "no-console": ["error", { allow: ["warn", "error"] }],
    },
  },
  {
    files: ["src/features/**", "src/pages/**", "src/app/**"],
    ignores: ["**/*.test.{ts,tsx}", "src/features/vue3d/view3d-entry.ts"],
    rules: { "no-restricted-imports": ["error", { patterns: [adapters] }] },
  },
  {
    files: ["src/components/**"],
    ignores: ["**/*.test.{ts,tsx}"],
    rules: { "no-restricted-imports": ["error", { patterns: [adapters, stateful] }] },
  },
  {
    files: ["src/socle/**", "src/app/**"],
    rules: { "react-refresh/only-export-components": "off" },
  },
  {
    files: ["src/**/*.test.{ts,tsx}", "src/test/**", "src/mocks/**", "e2e/**"],
    rules: { "@typescript-eslint/no-non-null-assertion": "off", "react-refresh/only-export-components": "off" },
  },
);
