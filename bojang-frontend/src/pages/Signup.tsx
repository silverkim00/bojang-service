// src/pages/Signup.tsx
import { useEffect, useMemo, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import type { AxiosError } from "axios";
import api from "../lib/api";

type Group = { id: number; name: string };

// --- ✨ any를 대체할 정확한 에러 타입 정의 ---
type ApiErrorResponse = {
  // 필드별 에러 (e.g., {"username": ["이미 사용 중인 아이디입니다."]})
  [key: string]: string[];
} | {
  // 일반 에러 (e.g., {"detail": "서버 오류"})
  detail?: string;
};

const USERNAME_RE = /^[A-Za-z][A-Za-z0-9]{3,19}$/;

export default function Signup() {
  const nav = useNavigate();

  const [username, setU] = useState("");
  const [fullName, setN] = useState("");
  const [password, setP] = useState("");
  const [birthRaw, setB] = useState(""); // 숫자만 8자리
  const [groups, setGroups] = useState<Group[]>([]);
  const [groupId, setG] = useState<string>(""); // 필수 선택
  const [email, setE] = useState("");
  const [loading, setL] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get<Group[]>("/api/auth/groups");
        // 데이터가 배열인 경우에만 상태를 업데이트하여 .map() 오류를 방지합니다.
        if (Array.isArray(r.data)) {
          setGroups(r.data);
        } else {
          setGroups([]);
        }
      } catch {
        setGroups([]);
      }
    })();
  }, []);

  const onBirthChange = (v: string) => {
    const digits = v.replace(/\D/g, "").slice(0, 8);
    setB(digits);
  };

  const onUsernameChange = (v: string) => {
    const clean = v.replace(/[^A-Za-z0-9]/g, "");
    setU(clean);
  };

  const birthPlaceholder = useMemo(() => "예: 19900512", []);
  const validUsername = useMemo(() => USERNAME_RE.test(username.trim()), [username]);
  const validFullName = fullName.trim().length >= 1;
  const validPassword = password.length >= 8 && !/\s/.test(password);
  const validBirth = birthRaw.length === 8;
  const validGroup = groupId !== "";
  const validEmail = useMemo(() => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()), [email]);

  const canSubmit =
    validUsername &&
    validFullName &&
    validPassword &&
    validBirth &&
    validGroup &&
    validEmail &&
    !loading;

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!canSubmit) return;
    setErr(null);
    setL(true);
    try {
      const body = {
        username: username.trim(),
        password,
        full_name: fullName.trim(),
        birthdate: birthRaw,
        email: email.trim(),
        group_id: groupId,
      };

      await api.post("/api/auth/signup", body);

      nav("/login", {
        replace: true,
        state: { msg: "가입 신청이 완료되었습니다. 관리자 승인 후 로그인 가능합니다." },
      });
    } catch (e) {
      // --- ✨ any 대신 정의된 에러 타입 사용 ---
      const ax = e as AxiosError<ApiErrorResponse>;
      
      let errorDetail = "회원가입 실패";
      if (ax.response?.data) {
          const responseData = ax.response.data;
          if (typeof responseData === 'object' && responseData !== null) {
              if ('detail' in responseData && typeof responseData.detail === 'string') {
                  errorDetail = responseData.detail;
              } else {
                  const firstErrorKey = Object.keys(responseData)[0];
                  // responseData가 필드 에러 객체임을 타입스크립트에게 알려줌
                  const fieldErrors = responseData as { [key: string]: string[] };
                  const firstErrorMessage = fieldErrors[firstErrorKey][0];
                  errorDetail = firstErrorMessage;
              }
          }
      }
      setErr(errorDetail);

    } finally {
      setL(false);
    }
  }

  return (
    <div className="min-h-screen bg-rose-50/60 text-gray-900">
      <main className="container mx-auto max-w-5xl px-4 md:px-6 py-10">
        <div className="min-h-[60vh] grid place-items-center">
          <form
            onSubmit={onSubmit}
            className="w-full max-w-md bg-white rounded-3xl shadow p-8 md:p-10 border border-rose-100 space-y-6"
          >
            <div className="space-y-1">
              <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight">회원가입</h1>
              <p className="text-base md:text-lg text-gray-600">필수 항목을 입력해주세요.</p>
            </div>

            <div className="space-y-5">
              <div>
                <label className="block text-base md:text-lg font-medium mb-2">아이디</label>
                <input
                  value={username}
                  onChange={(e) => onUsernameChange(e.target.value)}
                  autoComplete="username"
                  inputMode="text"
                  autoCapitalize="off"
                  spellCheck={false}
                  className="w-full rounded-2xl border border-rose-200 px-4 py-3 text-lg md:text-xl outline-none focus:ring-4 focus:ring-rose-300"
                  placeholder="영문 시작, 영문/숫자 4~20자"
                  aria-invalid={!validUsername && username.length > 0}
                  pattern="[A-Za-z][A-Za-z0-9]{3,19}"
                  title="영문으로 시작하고 영문/숫자 4~20자"
                />
                {!validUsername && username.length > 0 && (
                  <p className="text-sm text-red-600 mt-1">
                    영문으로 시작하고 영문/숫자만 사용한 4~20자여야 합니다.
                  </p>
                )}
              </div>

              <div>
                <label className="block text-base md:text-lg font-medium mb-2">이름</label>
                <input
                  value={fullName}
                  onChange={(e) => setN(e.target.value)}
                  className="w-full rounded-2xl border border-rose-200 px-4 py-3 text-lg md:text-xl outline-none focus:ring-4 focus:ring-rose-300"
                />
              </div>

              <div>
                <label className="block text-base md:text-lg font-medium mb-2">이메일</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setE(e.target.value)}
                  autoComplete="email"
                  className="w-full rounded-2xl border border-rose-200 px-4 py-3 text-lg md:text-xl outline-none focus:ring-4 focus:ring-rose-300"
                  placeholder="you@example.com"
                  aria-invalid={!validEmail && email.length > 0}
                />
                {!validEmail && email.length > 0 && (
                  <p className="text-sm text-red-600 mt-1">유효한 이메일을 입력하세요.</p>
                )}
              </div>

              <div>
                <label className="block text-base md:text-lg font-medium mb-2">비밀번호</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setP(e.target.value)}
                  autoComplete="new-password"
                  className="w-full rounded-2xl border border-rose-200 px-4 py-3 text-lg md:text-xl outline-none focus:ring-4 focus:ring-rose-300"
                  placeholder="8자 이상, 공백 금지"
                  aria-invalid={!validPassword && password.length > 0}
                />
                {!validPassword && password.length > 0 && (
                  <p className="text-sm text-red-600 mt-1">8자 이상, 공백 없이 입력하세요.</p>
                )}
              </div>

              <div>
                <label className="block text-base md:text-lg font-medium mb-2">
                  생년월일(숫자 8자리)
                </label>
                <input
                  inputMode="numeric"
                  pattern="\d*"
                  value={birthRaw}
                  onChange={(e) => onBirthChange(e.target.value)}
                  className="w-full rounded-2xl border border-rose-200 px-4 py-3 text-lg md:text-xl outline-none focus:ring-4 focus:ring-rose-300"
                  placeholder={birthPlaceholder}
                />
                <p className="text-xs text-gray-500 mt-1">예: 19500815</p>
              </div>

              <div>
                <label className="block text-base md:text-lg font-medium mb-2">소속(지점)</label>
                <select
                  value={groupId}
                  onChange={(e) => setG(e.target.value)}
                  className="w-full rounded-2xl border border-rose-200 px-4 py-3 text-lg md:text-xl outline-none focus:ring-4 focus:ring-rose-300 bg-white"
                  aria-invalid={!validGroup}
                  required
                >
                  <option value="" disabled>
                    소속(지점)을 선택하세요
                  </option>
                  {groups.map((g) => (
                    <option key={g.id} value={String(g.id)}>
                      {g.name}
                    </option>
                  ))}
                </select>
                {!validGroup && (
                  <p className="text-sm text-red-600 mt-1">소속(지점) 선택은 필수입니다.</p>
                )}
              </div>

              {err && (
                <div className="rounded-2xl border border-red-200 bg-red-50 text-red-800 px-4 py-3 text-base md:text-lg">
                  {err}
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={!canSubmit}
              className="w-full rounded-2xl px-6 py-4 text-lg md:text-xl font-bold bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-4 focus:ring-rose-300"
            >
              {loading ? "가입 중..." : "가입 완료"}
            </button>

            <div className="text-center text-sm md:text-base text-gray-600">
              이미 계정이 있나요?{" "}
              <Link to="/login" className="font-semibold text-rose-700 hover:underline">
                로그인
              </Link>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}