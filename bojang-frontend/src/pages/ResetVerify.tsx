import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";
import axios from "axios";

export default function ResetVerify() {
  const nav = useNavigate();
  const [username, setUsername] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    
    try {
      // 서버에 아이디와 인증 코드를 함께 전송합니다.
      const res = await api.post<{ reset_token: string }>(
        "/api/auth/password-reset/verify",
        { username, code }
      );

      // 성공 시, 받은 토큰을 다음 페이지에서 사용하기 위해 sessionStorage에 저장합니다.
      sessionStorage.setItem("reset_token", res.data.reset_token);
      
      // 마지막 단계인 새 비밀번호 입력 페이지로 이동합니다.
      nav("/reset-code/new");

    } catch (err) {
      let message = "인증에 실패했습니다.";
      if (axios.isAxiosError(err)) {
        message = err.response?.data?.detail || err.message;
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-md mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold mb-2">인증코드 확인</h1>
      <p className="text-sm text-gray-600 mb-6">
        아이디와 이메일로 전송된 6자리 인증코드를 입력해주세요.
      </p>

      <form
        onSubmit={onSubmit}
        className="space-y-4 bg-white p-6 rounded-2xl shadow"
      >
        <div>
          <label className="block text-sm mb-1">아이디</label>
          <input
            className="w-full rounded-lg border px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="코드를 요청한 아이디"
            required
          />
        </div>

        <div>
          <label className="block text-sm mb-1">인증코드</label>
          <input
            className="w-full rounded-lg border px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="6자리 숫자"
            maxLength={6}
            required
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-blue-600 text-white py-2 font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "확인 중..." : "인증코드 확인"}
        </button>
      </form>
    </div>
  );
}