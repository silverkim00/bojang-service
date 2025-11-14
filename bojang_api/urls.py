# bojang_api/urls.py
from django.contrib import admin
from django.urls import path, re_path
from django.views.generic import TemplateView
from django.http import JsonResponse

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

    # 🔥 구버전 프론트 호환용 (Dashboard에서 1차로 호출함)
    path("api/auth/me", MeView.as_view(), name="auth-me"),

    # 핵심 기능
    path("api/analyze", views.AnalyzeView.as_view(), name="analyze"),

    # 공지사항 API (Dashboard 연동)
    path("api/notice/get", NoticeGetView.as_view(), name="notice-get"),
    path("api/notice/update", NoticeUpdateView.as_view(), name="notice-update"),

    # 관리자 API
    path("api/management/users", management_views.UserListView.as_view(), name="mgmt-user-list"),
    path("api/management/users/<int:user_id>/activate", management_views.UserActivationView.as_view(), name="mgmt-user-activate"),
    path("api/management/users/<int:user_id>/logs", management_views.UserLoginLogView.as_view(), name="mgmt-user-logs"),

    path("api/management/dashboard-stats", management_views.DashboardStatsView.as_view(), name="mgmt-dashboard-stats"),

    path("api/management/processed-pdfs", management_views.ProcessedPDFListView.as_view(), name="mgmt-pdf-list"),
    path("api/management/processed-pdfs/<int:pdf_id>/details", management_views.ProcessedPDFDetailView.as_view(), name="mgmt-pdf-detail"),
    path("api/management/processed-pdfs/<int:pdf_id>/download", management_views.ProcessedPDFDownloadView.as_view(), name="mgmt-pdf-download"),
    path("api/management/processed-pdfs/<int:pdf_id>", management_views.ProcessedPDFDeleteView.as_view(), name="mgmt-pdf-delete"),

    # 회사 IP
    path("api/management/company-ips", management_views.CompanyIPView.as_view(), name="mgmt-company-ips"),

    # 유지보수 (Cloud Scheduler)
    path("api/maintenance/cleanup", MaintenanceCleanupView.as_view(), name="maintenance-cleanup"),

    # 사용자 정보
    path("api/me", MeView.as_view(), name="api-me"),

    # SPA 라우팅 (항상 마지막)
    re_path(r'^(?!api/|admin/).*$', TemplateView.as_view(template_name='index.html')),
]
