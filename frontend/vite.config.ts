import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In `npm run dev`, proxy API calls to a locally running backend.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": process.env.VITE_API_PROXY ?? "http://localhost:8000",
    },
  },
});
