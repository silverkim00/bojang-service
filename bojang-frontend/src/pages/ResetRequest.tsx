// src/pages/ResetRequest.tsx
import { useState } from "react";
import type { AxiosError } from "axios";
import api from "../lib/api";

export default function ResetRequest() {
  const [loginId, setLoginId] = useState(""); // 아이디 또는 이메일
  const [ok, setOk] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setL] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null); setL(true);
    try {
      const body = new URLSearchParams({ id: loginId.trim() });
      await api.post("/auth/password-reset/request", body, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      setOk(true);
    } catch (ex) {
      const e = ex as AxiosError<{ detail?: string; message?: string }>;
      setErr(e.response?.data?.detail || e.response?.data?.message || e.message || "요청 실패");
    } finally { setL(false); }
  }

  return (
    <div className="max-w-md mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold mb-4">비밀번호 재설정 코드 받기</h1>
      <form onSubmit={onSubmit} className="space-y-4 bg-white p-6 rounded-2xl shadow">
        <input
          className="w-full rounded-lg border px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="아이디 또는 이메일"
          value={loginId}
          onChange={(e) => setLoginId(e.target.value)}
        />
        {err && <p className="text-sm text-red-600">{err}</p>}
        {ok && <p className="text-sm text-green-700">계정이 존재한다면, 인증코드를 이메일로 전송했어요.</p>}
        <button type="submit" disabled={loading || !loginId.trim()}
          className="w-full rounded-lg bg-blue-600 text-white py-2 font-medium hover:bg-blue-700 disabled:opacity-50">
          {loading ? "전송 중..." : "코드 전송"}
        </button>
      </form>
    </div>
  );
}
