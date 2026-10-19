import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// 部署前缀（构建期可覆盖）：
//   默认 /admin —— FastAPI 同源挂载
//   子路径隔离部署（如 nginx 网关下 /nswap/admin）：
//     ADMIN_BASE=/nswap/admin npm run build
const adminBase = (process.env.ADMIN_BASE || "/admin").replace(/\/$/, "");

export default defineConfig({
  base: `${adminBase}/`,
  define: { __ADMIN_BASE__: JSON.stringify(adminBase) },
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
