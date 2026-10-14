import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// base=/admin/：生产由 FastAPI 挂载到 /admin 前缀下
export default defineConfig({
  base: "/admin/",
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5173,
    proxy: {
      // 本地开发：转发到本地后端（同源 cookie，无 CORS）
      "/api": { target: "http://127.0.0.1:8001", changeOrigin: true },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
