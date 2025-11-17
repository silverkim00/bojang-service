// bojang-frontend/src/lib/api.ts
import axios, {
  AxiosHeaders,
  type InternalAxiosRequestConfig,
  type AxiosInstance,
} from "axios";

// ────────────────────────────────
// [섹션 A] BASE_URL 결정
// ────────────────────────────────

const ENV_BASE_URL = import.meta.env.VITE_BACKEND_URL;
let RAW_BASE_URL = ENV_BASE_URL;

if (!RAW_BASE_URL) {
  const isBrowser = typeof window !== "undefined";
  const isLocalVite =
    isBrowser && window.location.origin.startsWith("http://localhost:5173");

  if (isLocalVite) {
    RAW_BASE_URL = "http://127.0.0.1:8000";
    console.warn(
      "[api] VITE_BACKEND_URL 미설정 → 로컬 개발용 http://127.0.0.1:8000 사용",
    );
  } else {
    console.error(
      "[api] VITE_BACKEND_URL 환경변수가 설정되어 있지 않습니다.",
    );
    throw new Error("VITE_BACKEND_URL 환경변수가 설정되어 있지 않습니다.");
  }
}

// 끝 슬래시 제거
export const BASE_URL = RAW_BASE_URL.replace(/\/+$/, "");

// ────────────────────────────────
// [섹션 B] 토큰 헬퍼
// ────────────────────────────────

function getTokenFromStorage(): string | null {
  // 1) auth(JSON) → token / access
  try {
    const rawAuth = localStorage.getItem("auth");
    if (rawAuth) {
      const parsed = JSON.parse(rawAuth) as {
        token?: string;
        access?: string;
      };
      if (parsed.token && typeof parsed.token === "string") {
        return parsed.token;
      }
      if (parsed.access && typeof parsed.access === "string") {
        return parsed.access;
      }
    }
  } catch {
    // JSON 파싱 실패는 무시하고 fallback
  }

  // 2) token(문자열)
  const rawToken = localStorage.getItem("token");
  return rawToken || null;
}

// ────────────────────────────────
// [섹션 C] Axios 인스턴스
// ────────────────────────────────

const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  withCredentials: false, // JWT는 Authorization 헤더로만 전달
  xsrfCookieName: "csrftoken",
  xsrfHeaderName: "X-CSRFToken",
});

// ────────────────────────────────
// [섹션 D] 요청 인터셉터
// ────────────────────────────────

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getTokenFromStorage();
  if (!token) {
    return config;
  }

  // headers를 AxiosHeaders 형태로 강제 정규화
  let headers: AxiosHeaders;
  if (config.headers instanceof AxiosHeaders) {
    headers = config.headers;
  } else {
    headers = new AxiosHeaders(config.headers || {});
    config.headers = headers;
  }

  // 이미 Authorization 있으면 건드리지 않음
  if (!headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return config;
});

// ────────────────────────────────
// [섹션 E] (옵션) 응답 인터셉터
// ────────────────────────────────
// 필요하면 401 전역 처리용으로 나중에 열면 됨
// api.interceptors.response.use(
//   (res) => res,
//   (err) => {
//     if (err?.response?.status === 401) {
//       try {
//         localStorage.removeItem("auth");
//         localStorage.removeItem("token");
//       } catch {}
//     }
//     return Promise.reject(err);
//   },
// );

export default api;
