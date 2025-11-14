// src/pages/Login.tsx
import { useState } from "react";
import type { AxiosError } from "axios";
import api from "../lib/api";
import { useNavigate } from "react-router-dom";

export default function Login() {
  const nav = useNavigate();
  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [loading, setL] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setErr(null);
    setL(true);
    try {
      // 백엔드가 form/json 둘 다 받을 수 있도록 form-encoded 유지
      const form = new URLSearchParams({ username, password });

      // token | access 어느 쪽이 와도 처리
      const res = await api.post<{ token?: string; access?: string; expires_in?: number }>(
        "/api/auth/login",
        form,
        { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
      );

      const jwt = res.data.access ?? res.data.token;
      if (!jwt) throw new Error("로그인 토큰을 받지 못했습니다.");

      // 저장 + 이후 요청에 Authorization 적용
      localStorage.setItem("token", jwt);
      api.defaults.headers.common["Authorization"] = `Bearer ${jwt}`;

      nav("/", { replace: true });
    } catch (err) {
      const e = err as AxiosError<{ detail?: string; message?: string }>;
      const msg =
        e.response?.data?.message ||
        e.response?.data?.detail ||
        e.message ||
        "로그인 실패";
      setErr(msg);
    } finally {
      setL(false);
    }
  }

  return (
    <div className="max-w-md mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold mb-6">로그인</h1>

      <form onSubmit={onSubmit} className="space-y-4 bg-white p-6 rounded-2xl shadow">
        <div>
          <label className="block text-sm mb-1">아이디</label>
          <input
            className="w-full rounded-lg border px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
            value={username}
            onChange={(e) => setU(e.target.value)}
            autoComplete="username"
            required
          />
        </div>

        <div>
          <label className="block text-sm mb-1">비밀번호</label>
          <input
            type="password"
            className="w-full rounded-lg border px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
            value={password}
            onChange={(e) => setP(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>

        {err && <p className="text-sm text-red-600">{err}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-blue-600 text-white py-2 font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "로그인 중..." : "로그인"}
        </button>
      </form>

      <p className="text-sm text-center text-gray-600 mt-4">
        비밀번호를 잊으셨나요?{" "}
        <a href="#/reset-code/request" className="text-blue-700 font-medium hover:underline">
          재설정
        </a>
      </p>
    </div>
  );
}
