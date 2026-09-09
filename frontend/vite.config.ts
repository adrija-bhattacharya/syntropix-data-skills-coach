import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// build output -> velpo/web  (FastAPI serves it from there at /)
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: process.env.VELPO_UI_OUT || "../velpo/web",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      ["/health", "/catalogue", "/recommend", "/observe", "/explain"].map((p) => [
        p,
        "http://127.0.0.1:8000",
      ]),
    ),
  },
});
