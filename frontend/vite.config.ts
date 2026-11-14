/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev` proxies API calls to a locally running backend (docker compose: :8000).
// `npm run dev:fixtures` (mode "fixtures", .env.fixtures) serves src/fixtures instead - no backend needed.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": process.env.VITE_API_PROXY ?? "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    env: { VITE_USE_FIXTURES: "true" },
  },
});
