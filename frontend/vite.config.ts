import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The browser only ever talks to the Vite server; requests under /api are
// forwarded to the FastAPI service, so no cross-origin setup is needed.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.API_URL ?? "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  build: { chunkSizeWarningLimit: 6000 },
});
