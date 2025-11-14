// src/pages/Dashboard.tsx
// 공지 + 이용안내 통합 카드, 관리자만 공지 수정, A3/A4 분석 버튼
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import api from "../lib/api";
import goyang2 from "../assets/goyang2.svg";
import yogigoyang from "../assets/yogigoyang.svg";
import downgoyang from "../assets/downgoyang.svg";

type DL = { name: string; url: string };
type Notice = { text: string };
type Me = { username: string; is_staff?: boolean; is_superuser?: boolean; role?: string };

function pickFilename(cd: string | undefined, fallback: string): string {
  if (!cd) return fallback;
  const star = cd.match(/filename\*\s*=\s*utf-8''([^;]+)/i);
  if (star) return decodeURIComponent(star[1].replace(/"/g, ""));
  const plain = cd.match(/filename\s*=\s*("?)([^";]+)\1/i);
  if (plain) return decodeURIComponent(plain[2]);
  return fallback;
}

export default function Dashboard() {
  const nav = useNavigate();
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [dls, setDls] = useState<DL[]>([]);
  const [err, setErr] = useState<string | null>(null);

  // 공지/권한
  const [notice, setNotice] = useState<Notice>({ text: "" });
  const [editMode, setEditMode] = useState(false);
  const [me, setMe] = useState<Me | null>(null);
  const [lastSize, setLastSize] = useState<"a3" | "a4">("a4");

  // 로그인/권한 체크
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      nav("/login", { replace: true });
      return;
    }
    (async () => {
      try {
        // 1차: /api/auth/me (권장)
        const r1 = await api.get("/api/auth/me");
        setMe(r1.data as Me);
      } catch {
        try {
          // 2차: /api/me (대체)
          const r2 = await api.get("/api/me");
          setMe(r2.data as Me);
        } catch {
          // 3차: localStorage fallback
          const role = localStorage.getItem("role") || "";
          setMe({ username: "", role, is_staff: role === "admin", is_superuser: role === "admin" });
        }
      }
    })();

    const saved = (localStorage.getItem("last_template_size") || "a4") as "a3" | "a4";
    setLastSize(saved);
  }, [nav]);

  // 공지 로드
  useEffect(() => {
    (async () => {
      try {
        const res = await api.get("/api/notice/get");
        setNotice({ text: res.data.notice || "" });
      } catch (e) {
        console.error("공지 로드 실패:", e);
        setNotice({ text: "공지사항을 불러오지 못했습니다." });
      }
    })();
  }, []);

  const canEdit = useMemo(() => {
    if (!me) return false;
    if (me.is_superuser || me.is_staff) return true;
    const r = (me.role || localStorage.getItem("role") || "").toLowerCase();
    return r === "admin" || r === "manager";
  }, [me]);

  async function updateNotice() {
    try {
      await api.post("/api/notice/update", { text: notice.text });
      setEditMode(false);
      alert("공지사항이 수정되었습니다.");
    } catch (e) {
      console.error("공지 수정 실패:", e);
      alert("공지사항 수정 중 오류가 발생했습니다.");
    }
  }

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    if (!e.target.files) return;
    setFiles(Array.from(e.target.files));
  }

  // 분석(A3/A4) 분기
  async function onAnalyzeWith(templateSize: "a3" | "a4") {
    if (!files.length) return;
    setErr(null);
    setLoading(true);
    setDls([]);

    try {
      const form = new FormData();
      files.forEach((f) => form.append("files", f, f.name));
      form.append("template_size", templateSize);

      const res = await api.post<Blob>(`/api/analyze?template_size=${templateSize}`, form, {
        responseType: "blob",
      });

      const ct = String(res.headers["content-type"] ?? "");
      const cd = res.headers["content-disposition"] as string | undefined;
      const fallback = ct.includes("zip")
        ? `result_${templateSize}.zip`
        : `result_${templateSize}.xlsx`;
      const name = pickFilename(cd, fallback);
      const url = URL.createObjectURL(res.data);
      setDls([{ name, url }]);

      localStorage.setItem("last_template_size", templateSize);
      setLastSize(templateSize);
    } catch (e: unknown) {
      let message = "분석 중 오류가 발생했습니다.";
      if (axios.isAxiosError(e) && e.response) {
        if (e.response.data instanceof Blob) {
          try {
            const errorJson = JSON.parse(await e.response.data.text());
            message = errorJson.message || errorJson.detail || message;
          } catch (p) {
            console.error("에러 파싱 실패:", p);
          }
        } else if (e.response.data) {
         
          message = e.response.data.message || e.response.data.detail || e.message;
        }
      }
      setErr(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-rose-50/60 text-gray-900">
      <main className="container mx-auto max-w-6xl px-3 md:px-6 pt-0 pb-6 space-y-6">
        {/* 공지 + 이용안내 통합 카드 */}
        <section className="bg-white border border-rose-200 rounded-2xl shadow-md px-5 py-4">
          {/* 공지 영역 */}
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg md:text-xl font-bold text-rose-700 flex items-center gap-2">
              📝 공지사항
            </h2>
            {canEdit && !editMode && (
              <button
                onClick={() => setEditMode(true)}
                className="text-sm font-semibold text-blue-600 hover:text-blue-800"
              >
                수정
              </button>
            )}
          </div>

          {editMode ? (
            <div className="space-y-3">
              <textarea
                value={notice.text}
                onChange={(e) => setNotice({ text: e.target.value })}
                className="w-full h-24 rounded-xl border border-rose-200 px-3 py-2 text-sm md:text-base focus:outline-none focus:ring-2 focus:ring-rose-300"
              />
              <div className="flex gap-2">
                <button
                  onClick={updateNotice}
                  className="px-3 py-1.5 rounded-lg bg-rose-600 text-white text-sm font-semibold hover:bg-rose-700"
                >
                  저장
                </button>
                <button
                  onClick={() => setEditMode(false)}
                  className="px-3 py-1.5 rounded-lg bg-gray-200 text-gray-800 text-sm font-semibold hover:bg-gray-300"
                >
                  취소
                </button>
              </div>
            </div>
          ) : (
            <p className="text-gray-700 text-sm md:text-base whitespace-pre-line leading-relaxed">
              {notice.text || "공지사항을 불러오지 못했습니다."}
            </p>
          )}

          {/* 구분선 */}
          <div className="my-4 h-px bg-rose-100" />

          {/* 이용 안내(초기 안내 카드 복원) */}
          <div className="rounded-2xl bg-rose-50/50 p-4 md:p-5 border border-rose-100">
            <h3 className="text-xl md:text-2xl font-extrabold text-blue-700 flex items-center gap-2">
              🚀 PDF 추출 및 분석 요청 순서 (총 2단계)
            </h3>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-4">
              {/* ①-1. 추출 단계 (KB) */}
              <div className="bg-white rounded-2xl border border-rose-100 p-4">
                <h4 className="text-rose-600 font-extrabold text-lg mb-3">①-1. 추출 단계 (KB)</h4>
                <ol className="space-y-3 text-gray-800">
                  <li className="flex gap-3">
                    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-rose-100 text-rose-700 font-bold">
                      1
                    </span>
                    <span>KB고객등록 ▶ 보장분석 클릭</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-rose-100 text-rose-700 font-bold">
                      2
                    </span>
                    <span>출력/발송 클릭 ▶ 상품별 상세담보 체크</span>
                  </li>
                </ol>
              </div>

              {/* ①-2. PDF 저장 단계 */}
              <div className="bg-white rounded-2xl border border-rose-100 p-4">
                <h4 className="text-rose-600 font-extrabold text-lg mb-3">①-2. PDF 저장 단계</h4>
                <ol className="space-y-3 text-gray-800">
                  <li className="flex gap-3">
                    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-rose-100 text-rose-700 font-bold">
                      3
                    </span>
                    <span>PDF저장 클릭 ▶ 찾기 클릭</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-rose-100 text-rose-700 font-bold">
                      4
                    </span>
                    <span>파일 이름 변경/저장 ▶ 확인 클릭</span>
                  </li>
                </ol>
              </div>

              {/* ② 시스템 등록/분석 */}
              <div className="bg-white rounded-2xl border border-rose-100 p-4">
                <h4 className="text-rose-600 font-extrabold text-lg mb-3">② 시스템 등록/분석</h4>
                <ol className="space-y-3 text-gray-800">
                  <li className="flex gap-3">
                    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-rose-100 text-rose-700 font-bold">
                      5
                    </span>
                    <span>좌측 [업로드] 박스에서 파일 선택</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-rose-100 text-rose-700 font-bold">
                      6
                    </span>
                    <span>PDF를 넣고 [분석 시작] 버튼 클릭</span>
                  </li>
                </ol>
              </div>
            </div>

            <p className="text-sm text-gray-600 mt-4">
              📢 분석이 완료되면 우측 <b>[결과 다운로드]</b> 박스에서 XLSX 결과 파일을 즉시 다운로드하실 수
              있습니다.
            </p>
          </div>
        </section>

        {/* 타이틀 */}
        <section className="space-y-2">
          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-rose-700 flex items-center gap-3 md:gap-4">
            <img
              src={goyang2}
              alt=""
              aria-hidden
              className="h-12 w-12 md:h-14 md:w-14 select-none shrink-0"
              draggable={false}
            />
            <span>보장분석 자동화 시스템</span>
          </h1>
        </section>

        {/* 업로드/다운로드 */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* 업로드 카드 */}
          <div className="bg-white rounded-3xl shadow p-5 md:p-7 space-y-5 border border-rose-100">
            <div className="space-y-2">
              <h2 className="text-lg md:text-xl font-bold text-rose-700 flex items-center gap-2">
                <img
                  src={yogigoyang}
                  alt=""
                  aria-hidden
                  className="h-10 w-10 md:h-12 md:w-12 select-none shrink-0"
                  draggable={false}
                />
                <span>PDF 업로드</span>
              </h2>
              <p className="text-base md:text-lg text-gray-700">컴퓨터에서 파일을 선택해주세요.</p>
            </div>

            <div className="space-y-2">
              <label className="block">
                <input
                  type="file"
                  accept="application/pdf"
                  multiple
                  onChange={onPick}
                  className="w-full rounded-xl border-2 border-dashed border-rose-200 bg-rose-50/40 px-4 py-3 text-base md:text-lg placeholder-gray-400 hover:border-rose-300 focus:outline-none focus:ring-4 focus:ring-rose-200"
                />
              </label>
              {files.length > 0 && (
                <p className="inline-flex items-center gap-2 rounded-full bg-rose-100 text-rose-800 px-3 py-1.5 text-base">
                  📎 {files.length}개 선택됨
                </p>
              )}
            </div>

            {/* A3/A4 분석 버튼 */}
            <div className="grid grid-cols-2 gap-3">
              <button
                disabled={loading || !files.length}
                onClick={() => onAnalyzeWith("a3")}
                className={
                  "w-full rounded-xl px-4 py-3 text-base md:text-lg font-bold " +
                  (lastSize === "a3" ? "ring-2 ring-rose-300 " : "") +
                  "bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50"
                }
                title="A3 인쇄용(base_template)"
              >
                A3 인쇄용 분석
              </button>

              <button
                disabled={loading || !files.length}
                onClick={() => onAnalyzeWith("a4")}
                className={
                  "w-full rounded-xl px-4 py-3 text-base md:text-lg font-bold " +
                  (lastSize === "a4" ? "ring-2 ring-rose-300 " : "") +
                  "bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50"
                }
                title="A4 인쇄용(base_template2)"
              >
                A4 인쇄용 분석
              </button>
            </div>

            {err && (
              <div className="rounded-xl border border-red-200 bg-red-50 text-red-800 px-4 py-3 text-base">
                {err}
              </div>
            )}
          </div>

          {/* 다운로드 카드 */}
          <div className="bg-white rounded-3xl shadow p-5 md:p-7 space-y-5 border border-rose-100">
            <h2 className="text-lg md:text-xl font-bold text-rose-700 flex items-center gap-2">
              결과 다운로드
              <img
                src={downgoyang}
                alt=""
                aria-hidden
                className="h-10 w-10 md:h-12 md:w-12 select-none shrink-0"
                draggable={false}
              />
            </h2>

            {dls.length === 0 ? (
              <p className="text-base md:text-lg text-gray-700">
                분석이 끝나면 여기에서 결과를 다운로드할 수 있습니다.
              </p>
            ) : (
              <ul className="space-y-3">
                {dls.map((d, i) => (
                  <li
                    key={i}
                    className="flex items-center justify-between rounded-xl border px-4 py-2 text-base"
                  >
                    <span className="truncate pr-4">{d.name}</span>
                    <a
                      href={d.url}
                      download={d.name}
                      className="rounded-xl bg-rose-600 text-white px-3 py-1.5 font-semibold hover:bg-rose-700"
                    >
                      다운로드
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
