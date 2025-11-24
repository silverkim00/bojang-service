# bojang_api/urls.py
from django.contrib import admin
from django.urls import path, re_path
from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings

from . import views
from . import management_views
from .views import (
    MaintenanceCleanupView,
    MeView,
    NoticeGetView,
    NoticeUpdateView,
)


def healthz(_):
    return JsonResponse({"status": "ok"})


def spa_fallback(request):
    """
    /, /foo 같은 비-API 경로로 들어온 브라우저를
    프론트엔드 서비스로 보내되,
    FRONTEND_URL 이 없거나 현재 서비스 도메인과 같으면
    리다이렉트 대신 JSON 200만 반환해서 무한 루프를 막는다.
    """
    target = getattr(settings, "FRONTEND_URL", "").rstrip("/")
    if not target:
        # FRONTEND_URL 미설정 → API 서비스임을 알리는 JSON만 반환
        return JsonResponse({"service": "bojang-service", "status": "ok"})

    # 현재 요청이 들어온 루트 URL (scheme + host)
    req_root = f"{request.scheme}://{request.get_host()}"

    # FRONTEND_URL 이 자기 자신(bojang-service)와 같으면
    # 여기서 다시 redirect 하면 무한 루프 발생하므로 JSON만 반환
    if target == req_root:
        return JsonResponse({"service": "bojang-service", "status": "ok"})

    # 그 외에는 정상적으로 프론트엔드 서비스로 302 리다이렉트
    return HttpResponseRedirect(target + "/")


urlpatterns = [
    # 기본 헬스체크
    path("healthz", healthz),

    # 관리자
    path("admin/", admin.site.urls),

    # 인증
    path("api/auth/login", views.LoginView.as_view(), name="auth-login"),
    path("api/auth/signup", views.SignupView.as_view(), name="auth-signup"),
    path("api/auth/groups", views.GroupListView.as_view(), name="auth-groups"),
    path(
        "api/auth/password-reset/request",
        views.PasswordResetRequestView.as_view(),
    ),
    path(
        "api/auth/password-reset/verify",
        views.PasswordResetVerifyView.as_view(),
    ),
    path(
        "api/auth/password-reset/confirm",
        views.PasswordResetConfirmView.as_view(),
    ),

    # 구버전 프론트 호환
    path("api/auth/me", MeView.as_view(), name="auth-me"),

    # 핵심 분석 기능
    path("api/analyze", views.AnalyzeView.as_view(), name="analyze"),

    # 공지사항
    path("api/notice/get", NoticeGetView.as_view(), name="notice-get"),
    path("api/notice/update", NoticeUpdateView.as_view(), name="notice-update"),

    # 관리자용 API
    path(
        "api/management/users",
        management_views.UserListView.as_view(),
        name="mgmt-user-list",
    ),
    path(
        "api/management/users/<int:user_id>/activate",
        management_views.UserActivationView.as_view(),
        name="mgmt-user-activate",
    ),
    path(
        "api/management/users/<int:user_id>/logs",
        management_views.UserLoginLogView.as_view(),
        name="mgmt-user-logs",
    ),

    # 대시보드 통계
    path(
        "api/management/dashboard-stats",
        management_views.DashboardStatsView.as_view(),
        name="mgmt-dashboard-stats",
    ),

    # 처리된 PDF 관리
    path(
        "api/management/processed-pdfs",
        management_views.ProcessedPDFListView.as_view(),
        name="mgmt-pdf-list",
    ),
    path(
        "api/management/processed-pdfs/<int:pdf_id>/details",
        management_views.ProcessedPDFDetailView.as_view(),
        name="mgmt-pdf-detail",
    ),
    path(
        "api/management/processed-pdfs/<int:pdf_id>/download",
        management_views.ProcessedPDFDownloadView.as_view(),
        name="mgmt-pdf-download",
    ),
    path(
        "api/management/processed-pdfs/<int:pdf_id>",
        management_views.ProcessedPDFDeleteView.as_view(),
        name="mgmt-pdf-delete",
    ),
    path(
        "api/management/company-ips",
        management_views.CompanyIPView.as_view(),
        name="mgmt-company-ips",
    ),

    # 유지보수
    path(
        "api/maintenance/cleanup",
        MaintenanceCleanupView.as_view(),
        name="maintenance-cleanup",
    ),

    # 사용자 정보 (신규 경로)
    path("api/me", MeView.as_view(), name="api-me"),

    # SPA 라우팅: /api/, /admin/ 이 아닌 모든 경로는 마지막에 여기로 빠짐
    # (반드시 urlpatterns 마지막에 유지)
    re_path(r"^(?!api/|admin/).*$", spa_fallback),
]
