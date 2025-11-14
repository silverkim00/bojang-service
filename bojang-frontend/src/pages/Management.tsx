import { useEffect, useState, FormEvent, FC } from "react";
import api from "../lib/api";
import axios from "axios";

// --- 데이터 타입 정의 ---
interface User { id: number; username: string; email: string; is_active: boolean; date_joined: string; full_name: string; affiliation: string; }
interface ProcessedPDF { id: number; username: string; original_filename: string; file_size: number; processed_at: string; }
interface LoginLog { id: number; ip_address: string; timestamp: string; is_company_ip: boolean; is_suspicious: boolean; }
interface CompanyIP { id: number; ip_address: string; description: string; }
interface UserActivity { user__username: string; count: number; }
interface DashboardStats { total_processed_today: number; user_activity_today: UserActivity[]; }
interface PdfDetails { id: number; original_filename: string; unmapped_items: string[]; excluded_words: string[]; }


// ===================================================================
// I. 팝업(모달) 컴포넌트
// ===================================================================

// --- 1. IP 접속 기록 팝업 ---
const IpLogModal: FC<{ user: User; onClose: () => void; }> = ({ user, onClose }) => {
  const [logs, setLogs] = useState<LoginLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchLogs() {
      try {
        setLoading(true); setError(null);
        const res = await api.get<{ logs: LoginLog[] }>(`/api/management/users/${user.id}/logs`);
        setLogs(res.data.logs);
      } catch (err) {
        let msg = "로그 기록 로딩 실패";
        if (axios.isAxiosError(err)) { msg = err.response?.data?.detail || err.message; }
        setError(msg);
      } finally { setLoading(false); }
    }
    fetchLogs();
  }, [user.id]);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <header className="p-4 border-b flex justify-between items-center">
          <h2 className="text-lg font-bold"><span className="font-normal text-gray-600">사용자:</span> {user.username}</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-800 text-2xl font-bold">&times;</button>
        </header>
        <main className="p-6 overflow-y-auto">
          {loading && <p className="text-center">로딩 중...</p>}
          {error && <p className="text-center text-red-600">{error}</p>}
          {logs && (
            <div className="overflow-x-auto border rounded-lg">
              <table className="w-full text-sm text-left">
                <thead className="bg-gray-50">
                  <tr><th className="px-4 py-2">IP 주소</th><th className="px-4 py-2">접속 시간</th><th className="px-4 py-2 text-center">비고</th></tr>
                </thead>
                <tbody className="divide-y">
                  {logs.length === 0 ? (
                    <tr><td colSpan={3} className="px-6 py-10 text-center text-gray-500">접속 기록이 없습니다.</td></tr>
                  ) : logs.map(log => (
                    <tr key={log.id} className={`hover:bg-gray-50 ${log.is_suspicious ? 'bg-yellow-50' : ''}`}>
                      <td className="px-4 py-2 font-mono">{log.ip_address}</td>
                      <td className="px-4 py-2">{log.timestamp}</td>
                      <td className="px-4 py-2 text-center">
                        {log.is_company_ip && <span className="px-2 py-1 text-xs font-semibold text-blue-800 bg-blue-100 rounded-full">회사IP</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

// --- 2. PDF 상세 로그 팝업 ---
const PdfDetailModal: FC<{ pdf: ProcessedPDF; onClose: () => void; }> = ({ pdf, onClose }) => {
  const [details, setDetails] = useState<PdfDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchDetails() {
      try {
        setLoading(true); setError(null);
        const res = await api.get<PdfDetails>(`/api/management/processed-pdfs/${pdf.id}/details`);
        setDetails(res.data);
      } catch (err) {
        let msg = "상세 로그 로딩 실패";
        if (axios.isAxiosError(err)) { msg = err.response?.data?.detail || err.message; }
        setError(msg);
      } finally { setLoading(false); }
    }
    fetchDetails();
  }, [pdf.id]);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[80vh] flex flex-col">
        <header className="p-4 border-b flex justify-between items-center">
          <h2 className="text-lg font-bold truncate"><span className="font-normal text-gray-600">파일:</span> {pdf.original_filename}</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-800 text-2xl font-bold">&times;</button>
        </header>
        <main className="p-6 overflow-y-auto grid grid-cols-1 md:grid-cols-2 gap-6">
          {loading && <p className="text-center col-span-2">로딩 중...</p>}
          {error && <p className="text-center text-red-600 col-span-2">{error}</p>}
          {details && (
            <>
              <div className="border rounded-lg p-4 bg-gray-50">
                <h3 className="font-semibold mb-2">매핑 실패 항목 ({details.unmapped_items.length}개)</h3>
                <ul className="text-sm text-gray-700 space-y-1 max-h-96 overflow-y-auto">
                  {details.unmapped_items.map((item, i) => <li key={i}>{item}</li>)}
                </ul>
              </div>
              <div className="border rounded-lg p-4 bg-gray-50">
                <h3 className="font-semibold mb-2">제외된 단어 ({details.excluded_words.length}개)</h3>
                <ul className="text-sm text-gray-700 space-y-1 max-h-96 overflow-y-auto">
                  {details.excluded_words.map((word, i) => <li key={i}>{word}</li>)}
                </ul>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
};


// ===================================================================
// II. 탭별 컴포넌트
// ===================================================================

// --- 1. 대시보드 탭 ---
const DashboardTab: FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchStats() {
      try {
        setLoading(true); setError(null);
        const res = await api.get<DashboardStats>("/api/management/dashboard-stats");
        setStats(res.data);
      } catch (err) {
        let msg = "대시보드 정보 로딩 실패";
        if (axios.isAxiosError(err)) msg = err.response?.data?.detail || err.message;
        setError(msg);
      } finally { setLoading(false); }
    }
    fetchStats();
  }, []);

  if (loading) return <div className="p-8 text-center">대시보드 로딩 중...</div>;
  if (error) return <div className="p-8 text-center text-red-600">{error}</div>;

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold mb-3 text-gray-800">오늘의 처리 현황</h3>
        <div className="bg-blue-50 p-6 rounded-lg text-center shadow-sm">
          <p className="text-sm font-medium text-blue-800">오늘 처리된 총 PDF 개수</p>
          <p className="text-4xl font-bold text-blue-600 mt-2">{stats?.total_processed_today ?? 0}</p>
        </div>
      </div>
      <div>
        <h3 className="text-lg font-semibold mb-3 text-gray-800">사용자별 오늘 작업량</h3>
        <div className="overflow-x-auto border rounded-lg">
          <table className="w-full text-sm text-left">
            <thead className="bg-gray-50">
              <tr className="border-b">
                <th className="px-6 py-3 font-medium text-gray-600">사용자</th>
                <th className="px-6 py-3 font-medium text-gray-600 text-right">처리 개수</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {stats?.user_activity_today && stats.user_activity_today.length > 0 ? (
                stats.user_activity_today.map((activity) => (
                  <tr key={activity.user__username} className="hover:bg-gray-50">
                    <td className="px-6 py-4 font-medium text-gray-900">{activity.user__username}</td>
                    <td className="px-6 py-4 text-right font-bold text-gray-700">{activity.count}</td>
                  </tr>
                ))
              ) : (
                <tr><td colSpan={2} className="px-6 py-10 text-center text-gray-500">오늘 처리된 작업이 없습니다.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// --- 2. 회원 관리 탭 ---
const UserManagementTab: FC<{ onViewLogs: (user: User) => void }> = ({ onViewLogs }) => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function toggleUserActivation(userId: number) {
    const originalUsers = [...users];
    setUsers(users.map(u => (u.id === userId ? { ...u, is_active: !u.is_active } : u)));
    try {
      await api.post(`/api/management/users/${userId}/activate`);
    } catch (err) {
      let msg = "상태 변경 실패";
      if (axios.isAxiosError(err)) msg = err.response?.data?.detail || err.message;
      alert(msg);
      setUsers(originalUsers);
    }
  }

  useEffect(() => {
    async function fetchUsers() {
      try {
        setLoading(true); setError(null);
        const res = await api.get<User[]>("/api/management/users");
        setUsers(res.data);
      } catch (err) {
        let msg = "사용자 목록 로딩 실패";
        if (axios.isAxiosError(err)) msg = err.response?.data?.detail || err.message;
        setError(msg);
      } finally { setLoading(false); }
    }
    fetchUsers();
  }, []);

  if (loading) return <div className="p-8 text-center">회원 목록 로딩 중...</div>;
  if (error) return <div className="p-8 text-center text-red-600">{error}</div>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm text-left">
        <thead className="bg-gray-50 border-b">
          <tr>
            <th className="px-6 py-3 whitespace-nowrap">아이디</th>
            <th className="px-6 py-3 whitespace-nowrap">이름</th>
            <th className="px-6 py-3 whitespace-nowrap">소속</th>
            <th className="px-6 py-3 whitespace-nowrap">이메일</th>
            <th className="px-6 py-3 whitespace-nowrap">가입일</th>
            <th className="px-6 py-3 text-center whitespace-nowrap">상태</th>
            <th className="px-6 py-3 text-center whitespace-nowrap">작업</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id} className="border-b hover:bg-gray-50">
              <td className="px-6 py-4 whitespace-nowrap font-medium">{user.username}</td>
              <td className="px-6 py-4 whitespace-nowrap">{user.full_name}</td>
              <td className="px-6 py-4 whitespace-nowrap">{user.affiliation}</td>
              <td className="px-6 py-4 whitespace-nowrap">{user.email}</td>
              <td className="px-6 py-4 whitespace-nowrap">{user.date_joined}</td>
              <td className="px-6 py-4 whitespace-nowrap text-center">
                {user.is_active ? (
                  <span className="px-2 py-1 text-xs font-semibold text-green-800 bg-green-100 rounded-full">활성</span>
                ) : (
                  <span className="px-2 py-1 text-xs font-semibold text-red-800 bg-red-100 rounded-full">승인대기</span>
                )}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-center space-x-2">
                <button
                  onClick={() => toggleUserActivation(user.id)}
                  className={`px-3 py-1 text-xs font-medium text-white rounded-md ${user.is_active ? "bg-red-500 hover:bg-red-600" : "bg-blue-500 hover:bg-blue-600"}`}
                >
                  {user.is_active ? "비활성화" : "승인"}
                </button>
                <button onClick={() => onViewLogs(user)} className="px-3 py-1 text-xs font-medium text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300">
                  접속 기록
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// --- 3. 파일 관리 탭 ---
const FileManagementTab: FC = () => {
  const [pdfs, setPdfs] = useState<ProcessedPDF[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPdf, setSelectedPdf] = useState<ProcessedPDF | null>(null);

  async function deletePdf(pdfId: number) {
    if (!window.confirm("정말로 이 기록을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.")) return;
    try {
      await api.delete(`/api/management/processed-pdfs/${pdfId}`);
      setPdfs(pdfs.filter(pdf => pdf.id !== pdfId));
    } catch (err) {
      let msg = "삭제 실패"; if (axios.isAxiosError(err)) msg = err.response?.data?.detail || err.message;
      alert(msg);
    }
  }

  async function downloadPdf(pdf: ProcessedPDF) {
    try {
      const res = await api.get(`/api/management/processed-pdfs/${pdf.id}/download`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', pdf.original_filename);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      let msg = "다운로드 실패"; if (axios.isAxiosError(err)) msg = err.response?.data?.detail || err.message;
      alert(msg);
    }
  }

  useEffect(() => {
    async function fetchPdfs() {
      try {
        setLoading(true); setError(null);
        const res = await api.get("/api/management/processed-pdfs");
        const data = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
        setPdfs(data);
        console.log("PDFs len=", data.length, data);
      } catch (err) {
        let msg = "파일 목록 로딩 실패";
        if (axios.isAxiosError(err)) msg = err.response?.data?.detail || err.message;
        setError(msg);
      } finally { setLoading(false); }
    }
    fetchPdfs();
  }, []);

  if (loading) return <div className="p-8 text-center">파일 목록 로딩 중...</div>;
  if (error) return <div className="p-8 text-center text-red-600">{error}</div>;

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-6 py-3">파일명</th>
              <th className="px-6 py-3">업로드 사용자</th>
              <th className="px-6 py-3">처리 시간</th>
              <th className="px-6 py-3 text-right">파일 크기</th>
              <th className="px-6 py-3 text-center">작업</th>
            </tr>
          </thead>
          <tbody>
            {pdfs.map((pdf) => (
              <tr key={pdf.id} className="border-b hover:bg-gray-50">
                <td className="px-6 py-4 font-medium">{pdf.original_filename}</td>
                <td className="px-6 py-4">{pdf.username}</td>
                <td className="px-6 py-4">{pdf.processed_at}</td>
                <td className="px-6 py-4 text-right">{(pdf.file_size / 1024).toFixed(1)} KB</td>
                <td className="px-6 py-4 text-center space-x-2">
                  <button onClick={() => setSelectedPdf(pdf)} className="px-3 py-1 text-xs font-medium text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300">상세</button>
                  <button onClick={() => downloadPdf(pdf)} className="px-3 py-1 text-xs font-medium text-white bg-green-600 rounded-md hover:bg-green-700">다운로드</button>
                  <button onClick={() => deletePdf(pdf.id)} className="px-3 py-1 text-xs font-medium text-white bg-red-500 rounded-md hover:bg-red-600">삭제</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selectedPdf && <PdfDetailModal pdf={selectedPdf} onClose={() => setSelectedPdf(null)} />}
    </>
  );
};

// --- 4. 설정 (회사 IP 관리) 탭 ---
const SettingsTab: FC = () => {
  const [ips, setIps] = useState<CompanyIP[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newIp, setNewIp] = useState("");
  const [newDesc, setNewDesc] = useState("");

  async function addIp(e: FormEvent) {
    e.preventDefault();
    try {
      const res = await api.post<CompanyIP>("/api/management/company-ips", { ip_address: newIp, description: newDesc });
      setIps([...ips, res.data]); setNewIp(""); setNewDesc("");
    } catch (err) {
      let msg = "IP 추가 실패"; if (axios.isAxiosError(err)) msg = err.response?.data?.detail || err.message;
      alert(msg);
    }
  }

  async function deleteIp(ipId: number) {
    if (!window.confirm("이 IP를 삭제하시겠습니까?")) return;
    try {
      await api.delete("/api/management/company-ips", { data: { id: ipId } });
      setIps(ips.filter(ip => ip.id !== ipId));
    } catch (err) {
      let msg = "IP 삭제 실패"; if (axios.isAxiosError(err)) msg = err.response?.data?.detail || err.message;
      alert(msg);
    }
  }

  useEffect(() => {
    async function fetchIps() {
      try {
        setLoading(true); setError(null);
        const res = await api.get<CompanyIP[]>("/api/management/company-ips");
        setIps(res.data);
      } catch (err) {
        let msg = "IP 목록 로딩 실패"; if (axios.isAxiosError(err)) msg = err.response?.data?.detail || err.message;
        setError(msg);
      } finally { setLoading(false); }
    }
    fetchIps();
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h3 className="text-lg font-semibold mb-3 text-gray-800">새 회사 IP 등록</h3>
        <form onSubmit={addIp} className="flex items-start gap-4 p-4 border rounded-lg bg-gray-50">
          <input value={newIp} onChange={e => setNewIp(e.target.value)} placeholder="IP 주소 (예: 123.45.67.89)" className="flex-grow rounded-md border-gray-300 shadow-sm" required />
          <input value={newDesc} onChange={e => setNewDesc(e.target.value)} placeholder="설명 (예: 본사, 강남지점)" className="flex-grow rounded-md border-gray-300 shadow-sm" />
          <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">추가</button>
        </form>
      </div>
      <div>
        <h3 className="text-lg font-semibold mb-3 text-gray-800">등록된 회사 IP 목록</h3>
        <div className="overflow-x-auto border rounded-lg">
          <table className="w-full text-sm text-left">
            <thead className="bg-gray-50"><tr><th className="px-6 py-3">IP 주소</th><th className="px-6 py-3">설명</th><th className="px-6 py-3 text-center">작업</th></tr></thead>
            <tbody className="divide-y">
              {loading && <tr><td colSpan={3} className="px-6 py-10 text-center text-gray-500">로딩 중...</td></tr>}
              {error && <tr><td colSpan={3} className="px-6 py-10 text-center text-red-500">{error}</td></tr>}
              {!loading && ips.length === 0 && (<tr><td colSpan={3} className="px-6 py-10 text-center text-gray-500">등록된 회사 IP가 없습니다.</td></tr>)}
              {!loading && ips.map(ip => (
                <tr key={ip.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 font-mono">{ip.ip_address}</td>
                  <td className="px-6 py-4">{ip.description}</td>
                  <td className="px-6 py-4 text-center">
                    <button onClick={() => deleteIp(ip.id)} className="px-3 py-1 text-xs text-red-700 hover:text-white hover:bg-red-600 border border-red-300 rounded-md">삭제</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};


// ===================================================================
// III. 메인 관리자 페이지 컴포넌트
// ===================================================================
type Tab = "dashboard" | "users" | "files" | "settings";

export default function Management() {
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");
  const [viewingUserLogs, setViewingUserLogs] = useState<User | null>(null);

  const tabStyle = "px-4 py-2 font-semibold rounded-t-lg transition-colors duration-200";
  const activeTabStyle = "text-blue-600 border-b-2 border-blue-600";
  const inactiveTabStyle = "text-gray-500 hover:text-gray-700 hover:border-b-2 hover:border-gray-300";

  return (
    <div className="p-4 sm:p-8 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">관리자 페이지</h1>
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex space-x-2 -mb-px">
          <button onClick={() => setActiveTab("dashboard")} className={`${tabStyle} ${activeTab === "dashboard" ? activeTabStyle : inactiveTabStyle}`}>대시보드</button>
          <button onClick={() => setActiveTab("users")} className={`${tabStyle} ${activeTab === "users" ? activeTabStyle : inactiveTabStyle}`}>회원 관리</button>
          <button onClick={() => setActiveTab("files")} className={`${tabStyle} ${activeTab === "files" ? activeTabStyle : inactiveTabStyle}`}>파일 관리</button>
          <button onClick={() => setActiveTab("settings")} className={`${tabStyle} ${activeTab === "settings" ? activeTabStyle : inactiveTabStyle}`}>설정</button>
        </nav>
      </div>
      <div className="bg-white p-6 rounded-lg shadow-md">
        {activeTab === "dashboard" && <DashboardTab />}
        {activeTab === "users" && <UserManagementTab onViewLogs={(user) => setViewingUserLogs(user)} />}
        {activeTab === "files" && <FileManagementTab />}
        {activeTab === "settings" && <SettingsTab />}
      </div>
      {viewingUserLogs && <IpLogModal user={viewingUserLogs} onClose={() => setViewingUserLogs(null)} />}
    </div>
  );
}
