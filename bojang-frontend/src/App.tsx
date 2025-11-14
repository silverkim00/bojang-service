// src/App.tsx

import React, { PropsWithChildren, useEffect } from "react";
import {
  HashRouter,
  Routes,
  Route,
  Navigate,
  Link,
  useLocation,
  useNavigate,
} from "react-router-dom";

import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Dashboard from "./pages/Dashboard";
import ResetRequest from "./pages/ResetRequest";
import ResetVerify from "./pages/ResetVerify";
import ResetNew from "./pages/ResetNew";

// --- ✨ 1. 새로 만든 Management 페이지를 import 합니다. ---
import Management from "./pages/Management";
import newlogo from "./assets/newlogo.svg";
import goyang from "./assets/goyang.svg";


// --- 사용자님의 Guard 컴포넌트 (변경 없음) ---
function Guard({ children }: { children: JSX.Element }) {
  const token = localStorage.getItem("token");
  return token ? children : <Navigate to="/login" replace />;
}

// --- 사용자님의 Shell 컴포넌트 (관리자 메뉴 링크만 추가) ---
function Shell({ children }: PropsWithChildren) {
  const { pathname } = useLocation();
  const nav = useNavigate();
  const token = localStorage.getItem("token");

  const isActive = (path: string) =>
    pathname === path
      ? "text-rose-800 font-extrabold"
      : "text-rose-700 hover:text-rose-800";

  const onLogout = () => {
    localStorage.removeItem("token");
    nav("/login", { replace: true });
  };

  useEffect(() => {
    const onPageShow = () => {
      const t = localStorage.getItem("token");
      const publicPaths = new Set(["/login", "/signup", "/reset-code/request", "/reset-code/verify", "/reset-code/new"]);
      if (!t && !publicPaths.has(pathname)) {
        nav("/login", { replace: true });
      }
    };
    window.addEventListener("pageshow", onPageShow);
    return () => window.removeEventListener("pageshow", onPageShow);
  }, [pathname, nav]);

  return (
    <div className="min-h-screen bg-rose-50/60 text-gray-900">
      <header className="sticky top-0 z-10 bg-white/85 backdrop-blur border-b">
        <div className="mx-auto max-w-5xl h-20 md:h-24 px-4 md:px-6 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-4 md:gap-5 text-rose-700" aria-label="홈">
            <img src={newlogo} alt="인카웰스사업단" className="h-20 w-20 md:h-24 md:w-24 object-contain" draggable={false}/>
            <span className="text-3xl md:text-4xl font-extrabold tracking-tight text-blue-700">
              인카 웰스사업단
            </span>
            <img src={goyang} alt="" aria-hidden className="h-14 w-14 md:h-16 md:w-16 select-none shrink-0" draggable={false}/>
          </Link>
          <nav className="flex items-center gap-4 md:gap-6 text-lg md:text-xl">
            <Link to="/" className={isActive("/")}>메인</Link>
            
            {/* --- ✨ 2. 로그인 상태에 따라 메뉴를 보여주는 로직 수정 --- */}
            {token ? (
              <>
                {/* 관리자 페이지 링크 */}
                <Link to="/management" className={isActive("/management")}>회원관리</Link>
                {/* 로그아웃 버튼 */}
                <button
                  onClick={onLogout}
                  className="rounded-2xl border border-rose-200 px-4 py-2 font-medium text-rose-700 hover:bg-rose-50 focus:outline-none focus:ring-4 focus:ring-rose-300"
                >
                  로그아웃
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className={isActive("/login")}>로그인</Link>
                <Link to="/signup" className={isActive("/signup")}>회원가입</Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 md:px-6 py-8 md:py-10">{children}</main>
    </div>
  );
}

// --- 사용자님의 App 컴포넌트 (관리자 페이지 라우트만 추가) ---
export default function App() {
  return (
    <HashRouter>
      <Shell>
        <Routes>
          {/* 공개 페이지 */}
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />

          {/* 비밀번호 재설정 3단계 */}
          <Route path="/reset-code/request" element={<ResetRequest />} />
          <Route path="/reset-code/verify"   element={<ResetVerify />} />
          <Route path="/reset-code/new"      element={<ResetNew />} />

          {/* 보호 페이지 */}
          <Route path="/" element={<Guard><Dashboard /></Guard>} />
          
          {/* --- ✨ 3. /management 경로에 대한 라우트를 추가합니다. --- */}
          <Route path="/management" element={<Guard><Management /></Guard>} />

          {/* 마지막에 와일드카드 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Shell>
    </HashRouter>
  );
}