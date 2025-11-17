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
    프론트엔드 서비스로 리다이렉트.
    /api/, /admin/은 기존처럼 백엔드가 처리.
    """
    target = getattr(settings, "FRONTEND_URL", "").rstrip("/")
    if not target:
        # FRONTEND_URL 이 없으면 예전처럼 JSON만 응답
        return JsonResponse({"service": "bojang-service", "status": "ok"})

    return HttpResponseRedirect(target + "/")


urlpatterns = [
    # 기본
    path("healthz", healthz),
    path("admin/", admin.site.urls),

    # 인증
    path("api/auth/login", views.LoginView.as_view(), name="auth-login"),
    path("api/auth/signup", views.SignupView.as_view(), name="auth-signup"),
    path("api/auth/groups", views.GroupListView.as_view(), name="auth-groups"),
    path("api/auth/password-reset/request", views.PasswordResetRequestView.as_view()),
    path("api/auth/password-reset/verify", views.PasswordResetVerifyView.as_view()),
    path("api/auth/password-reset/confirm", views.PasswordResetConfirmView.as_view()),

    # 구버전 프론트 호환
    path("api/auth/me", MeView.as_view(), name="auth-me"),

    # 핵심 기능
    path("api/analyze", views.AnalyzeView.as_view(), name="analyze"),

    # 공지사항
    path("api/notice/get", NoticeGetView.as_view(), name="notice-get"),
    path("api/notice/update", NoticeUpdateView.as_view(), name="notice-update"),

    # 관리자 API
    path("api/management/users", management_views.UserListView.as_view(), name="mgmt-user-list"),
    path("api/management/users/<int:user_id>/activate", management_views.UserActivationView.as_view(), name="mgmt-user-activate"),
    path("api/management/users/<int:user_id>/logs", management_views.UserLoginLogView.as_view(), name="mgmt-user-logs"),

    # 대시보드 통계
    path(
        "api/management/dashboard-stats",
        management_views.DashboardStatsView.as_view(),
        name="mgmt-dashboard-stats",
    ),

    path("api/management/processed-pdfs", management_views.ProcessedPDFListView.as_view(), name="mgmt-pdf-list"),
    path("api/management/processed-pdfs/<int:pdf_id>/details", management_views.ProcessedPDFDetailView.as_view(), name="mgmt-pdf-detail"),
    path("api/management/processed-pdfs/<int:pdf_id>/download", management_views.ProcessedPDFDownloadView.as_view(), name="mgmt-pdf-download"),
    path("api/management/processed-pdfs/<int:pdf_id>", management_views.ProcessedPDFDeleteView.as_view(), name="mgmt-pdf-delete"),
    path("api/management/company-ips", management_views.CompanyIPView.as_view(), name="mgmt-company-ips"),

    # 유지보수
    path("api/maintenance/cleanup", MaintenanceCleanupView.as_view(), name="maintenance-cleanup"),

    # 사용자 정보
    path("api/me", MeView.as_view(), name="api-me"),

    # SPA 라우팅: /api, /admin 이 아닌 모든 경로는 프론트로 리다이렉트 (항상 마지막)
    re_path(r"^(?!api/|admin/).*$", spa_fallback),
]
