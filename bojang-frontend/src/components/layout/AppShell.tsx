import { PropsWithChildren} from "react";
import { Link, useLocation } from "react-router-dom";
import goyang2 from "../../assets/goyang2.svg";

export default function AppShell({ children }: PropsWithChildren) {
  const { pathname } = useLocation();
  const token = localStorage.getItem("token");
  const isActive = (p: string) =>
    pathname === p ? "text-rose-800 font-extrabold" : "text-rose-700 hover:text-rose-800";

  return (
    <div className="min-h-screen bg-rose-50/60 text-gray-900">
      <header className="sticky top-0 z-10 bg-white/80 backdrop-blur border-b">
        <div className="container mx-auto max-w-5xl px-4 md:px-6 h-16 flex items-center justify-between">
        <Link
  to="/"
  className="flex items-center gap-4 md:gap-5 text-rose-700"
  aria-label="홈"
>
  <span className="text-3xl md:text-4xl font-extrabold tracking-tight">
    보장 분석
  </span>
  {/* 장식 아이콘: 기존 h-7/md:h-8 대비 2배 */}
  <img
    src={goyang2}
    alt=""
    aria-hidden
    className="h-14 w-14 md:h-16 md:w-16 select-none"
    draggable={false}
  />
</Link>

          <nav className="flex items-center gap-4 md:gap-6 text-base md:text-lg">
            <Link to="/" className={isActive("/")}>메인</Link>
            {!token && <Link to="/login" className={isActive("/login")}>로그인</Link>}
            {!token && <Link to="/signup" className={isActive("/signup")}>회원가입</Link>}
            {token && (
              <button
                onClick={() => { localStorage.removeItem("token"); location.href = "/login"; }}
                className="rounded-2xl border border-rose-200 px-4 py-1.5 font-medium text-rose-700 hover:bg-rose-50 focus:outline-none focus:ring-4 focus:ring-rose-300"
              >
                로그아웃
              </button>
            )}
          </nav>
        </div>
      </header>

      <main className="container mx-auto max-w-5xl px-4 md:px-6 py-8 md:py-10">
        {children}
      </main>
    </div>
  );
}
