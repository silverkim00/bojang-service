# -*- coding: utf-8 -*-
"""
bojang_service Django settings
- Oracle Cloud VM / Cloud Run / 로컬 겸용 최적화
"""

from pathlib import Path
from datetime import timedelta
import os

# ============================================================
# [섹션 A] 기본 환경 / .env / 업로드 가드
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent
IS_CLOUD_RUN = bool(
    os.getenv("K_SERVICE")
    or os.getenv("CLOUD_RUN_JOB")
    or os.getenv("JOB_NAME")
)

# .env 로드
try:
    from dotenv import load_dotenv
    if not IS_CLOUD_RUN:
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)
except ImportError:
    pass

# [중요 수정] 무조건 디버그 모드를 켜서 에러 원인을 파악합니다.
DEBUG = True

MAX_FILES_PER_REQ = int(os.getenv("MAX_FILES_PER_REQ", "10"))
MAX_FILE_BYTES    = int(os.getenv("MAX_FILE_BYTES", str(50 * 1024 * 1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_FILE_BYTES
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_FILES_PER_REQ * MAX_FILE_BYTES
FILE_UPLOAD_TEMP_DIR = "/tmp"

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-default-dev-key")

def _env_list(key: str, default: str = "") -> list[str]:
    v = os.getenv(key, default)
    seen, out = set(), []
    for s in (x.strip() for x in v.split(",") if x.strip()):
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out

# ============================================================
# [섹션 B] 호스트 / CSRF / CORS (HTTP 환경 프리패스)
# ============================================================
ALLOWED_HOSTS = ["138.2.5.244", "localhost", "127.0.0.1", "*"]

# HTTP 접속 시 오류를 뿜는 주범이므로 비활성화
# USE_X_FORWARDED_HOST = True
# SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

PROD_URL = "https://bojang-service-98909072626.asia-northeast3.run.app"
ORACLE_IP = "138.2.5.244"

# CSRF 신뢰 목록 (http로 직접 명시)
CSRF_TRUSTED_ORIGINS = [
    f"http://{ORACLE_IP}",
    f"http://{ORACLE_IP}:80",
    f"http://{ORACLE_IP}:8000",
    f"http://localhost:8000",
    PROD_URL,
]

CORS_EXPOSE_HEADERS = ["Content-Disposition"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = True  # 무조건 다 허용

# ============================================================
# [섹션 C] INSTALLED_APPS / MIDDLEWARE
# ============================================================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "storages",
    "bojang_api",
    "records",
    "pdf_xlsx",
]

if DEBUG:
    INSTALLED_APPS.append("django_extensions")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",  # CSRF 검증 로직
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ============================================================
# [섹션 D] URL / 템플릿 / WSGI
# ============================================================
ROOT_URLCONF = "bojang_api.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "bojang-frontend", "dist")] if os.path.exists(os.path.join(BASE_DIR, "bojang-frontend", "dist")) else [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

WSGI_APPLICATION = "bojang_api.wsgi.application"

# ============================================================
# [섹션 E] 데이터베이스
# ============================================================
if os.getenv("DB_NAME"):
    _DB_NAME = os.getenv("DB_NAME")
    _DB_USER = os.getenv("DB_USER")
    _DB_PASS = os.getenv("DB_PASSWORD")
    _DB_HOST = os.getenv("DB_HOST", "db")
    _DB_PORT = os.getenv("DB_PORT", "5432")
    
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _DB_NAME,
            "USER": _DB_USER,
            "PASSWORD": _DB_PASS,
            "HOST": _DB_HOST,
            "PORT": _DB_PORT,
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ============================================================
# [섹션 F] 국제화
# ============================================================
LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

# ============================================================
# [섹션 G] 정적 파일 / WhiteNoise
# ============================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

FE_DIST = os.path.join(BASE_DIR, "bojang-frontend", "dist")
STATICFILES_DIRS = [FE_DIST] if os.path.exists(FE_DIST) else []

WHITENOISE_USE_FINDERS = True
WHITENOISE_MANIFEST_STRICT = False

if IS_CLOUD_RUN:
    STORAGES = {
        "default": {"BACKEND": "storages.backends.gcloud.GoogleCloudStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
else:
    MEDIA_ROOT = BASE_DIR / "media"
    MEDIA_URL = "/media/"
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============================================================
# [섹션 H] DRF / JWT
# ============================================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
}

_access_hours = int(os.getenv("JWT_EXPIRES_HOURS", "12"))
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=_access_hours),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ALGORITHM": "HS256",
    "SIGNING_KEY": os.getenv("JWT_SECRET") or SECRET_KEY,
}

# ============================================================
# [섹션 I] 운영 보안 옵션 (모두 해제)
# ============================================================
# HTTP 접속에서도 로그인 쿠키가 먹히도록 무조건 False 처리
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

# ============================================================
# [섹션 J] 로깅
# ============================================================
LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO")

def _console_only_logging():
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {"console": {"class": "logging.StreamHandler"}},
        "root": {"handlers": ["console"], "level": LOG_LEVEL},
        "loggers": {
            "django": {
                "handlers": ["console"],
                "level": LOG_LEVEL,
                "propagate": False,
            }
        },
    }

LOGGING = _console_only_logging()

# ============================================================
# [섹션 K] 이메일
# ============================================================
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_USE_TLS = False
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", f"보장분석 <{EMAIL_HOST_USER}>")
EMAIL_TIMEOUT = 30