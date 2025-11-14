// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: '/static/', // 기존 설정

  // ⬇️ 이 부분을 추가하세요 ⬇️
  server: {
    proxy: {
      // '/api'로 시작하는 모든 요청을
      '/api': {
        target: 'http://localhost:8000', // Django 서버(백엔드) 주소
        changeOrigin: true, // CORS 오류 방지를 위해 호스트 헤더 변경
        secure: false,      // https가 아닌 http에도 허용
      }
    }
  }
});