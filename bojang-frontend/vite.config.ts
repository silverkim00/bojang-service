// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Cloud Run 프론트: 정적 사이트 루트(/)에서 서빙
// 로컬 개발: http://localhost:5173, /api 는 Django(8000)로 프록시
export default defineConfig(() => ({
  plugins: [react()],

  // ✅ 예전 '/static/' 대신 루트 기준으로 변경
  //    → Cloud Run Nginx에서 /usr/share/nginx/html 를 루트로 쓰고 있으니까 이게 정답
  base: "/",

  server: {
    port: 5173,
    proxy: {
      // 로컬에서만 사용됨. Cloud Run 배포 시에는 영향 없음.
      "/api": {
        target: "http://localhost:8000", // 로컬 Django 서버
        changeOrigin: true,
        secure: false,
      },
    },
  },

  build: {
    outDir: "dist",
  },
}));
