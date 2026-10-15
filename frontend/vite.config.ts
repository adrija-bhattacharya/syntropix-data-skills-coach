/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const API = "http://127.0.0.1:8000";
const ENDPOINTS = [
  "/health",
  "/catalogue",
  "/recommend",
  "/observe",
  "/explain",
  "/resolve",
  "/assess",
  "/schedule",
  "/roadmap",
  "/graph",
  "/discover",
  "/practice/", // trailing slash: /practice itself is the SPA page
  "/library",
  "/certifications",
  "/reschedule",
  "/portfolio/", // trailing slash: /portfolio itself is the SPA page
  "/p/", // public portfolio pages
];

// build output -> web/  (FastAPI serves it from there at /)
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: process.env.VELPO_UI_OUT || "../web",
    emptyOutDir: true,
    chunkSizeWarningLimit: 700, // recharts is ~160 kB gzip - lazy-loaded in its own chunk
    rollupOptions: {
      output: {
        manualChunks: {
          charts: ["recharts"],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: Object.fromEntries(ENDPOINTS.map((p) => [p, API])),
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    restoreMocks: true,
  },
});
