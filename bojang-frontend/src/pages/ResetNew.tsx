// src/pages/ResetNew.tsx
import { useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import type { AxiosError } from "axios";
import api from "../lib/api";

export default function ResetNew() {
  const { state } = useLocation() as { state?: { reset_token?: string } };
  const nav = useNavigate();
  const token = state?.reset_token || "";
  const [p1, setP1] = useState(""); const [p2, setP2] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false); const [loading, setL] = useState(false);

  const valid = p1.length>=8 && !/\s/.test(p1) && p1===p2 && !!token;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if(!valid) return;
    setErr(null); setL(true);
    try {
      const body = new URLSearchParams({ reset_token: token, new_password: p1 });
      await api.post("/auth/password-reset/confirm", body, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      setOk(true);
      setTimeout(()=> nav("/login", { replace:true }), 1200);
    } catch (ex) {
      const e = ex as AxiosError<{ detail?: string; message?: string }>;
      setErr(e.response?.data?.detail || e.response?.data?.message || e.message || "변경 실패");
    } finally { setL(false); }
  }

  return (
    <div className="max-w-md mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold mb-4">새 비밀번호 설정</h1>
      <form onSubmit={onSubmit} className="space-y-4 bg-white p-6 rounded-2xl shadow">
        <input type="password" className="w-full rounded-lg border px-3 py-2" placeholder="새 비밀번호(8자 이상)" value={p1} onChange={(e)=>setP1(e.target.value)} />
        <input type="password" className="w-full rounded-lg border px-3 py-2" placeholder="새 비밀번호 확인" value={p2} onChange={(e)=>setP2(e.target.value)} />
        {err && <p className="text-sm text-red-600">{err}</p>}
        {ok && <p className="text-sm text-green-700">변경되었습니다. 로그인 화면으로 이동합니다…</p>}
        <button type="submit" disabled={!valid || loading}
          className="w-full rounded-lg bg-blue-600 text-white py-2 font-medium hover:bg-blue-700 disabled:opacity-50">
          {loading ? "변경 중..." : "변경"}
        </button>
      </form>
    </div>
  );
}
