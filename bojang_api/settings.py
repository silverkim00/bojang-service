from pathlib import Path
from datetime import timedelta
import os

# ── 1) 기본
BASE_DIR = Path(__file__).resolve().parent.parent
IS_CLOUD_RUN = bool(
    os.getenv("K_SERVICE")
    or os.getenv("CLOUD_RUN_JOB")   # Cloud Run Job에 자동 세팅됨
    or os.getenv("JOB_NAME")        # (일부 환경에서 세팅)
)

# ── 2) .env (로컬에서만 먼저 로드)
try:
    from dotenv import load_dotenv
    if not IS_CLOUD_RUN:
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)
except ImportError:
    pass

# ── 3) 디버그 플래그 (.env 로드 후 계산)
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"  # 운영 기본 false 권장

# ── 4) 업로드 가드
MAX_FILES_PER_REQ = int(os.getenv("MAX_FILES_PER_REQ", "10"))
MAX_FILE_BYTES    = int(os.getenv("MAX_FILE_BYTES", str(50 * 1024 * 1024)))  # 50MB
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_FILE_BYTES
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_FILES_PER_REQ * MAX_FILE_BYTES
# Cloud Run은 /tmp 만 쓰기 가능
FILE_UPLOAD_TEMP_DIR = "/tmp"

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-default-dev-key")

# ── 5) 유틸
def _env_list(key: str, default: str = "") -> list[str]:
    v = os.getenv(key, default)
    seen, out = set(), []
    for s in (x.strip() for x in v.split(",") if x.strip()):
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out

# ── 6) 호스트/CORS/CSRF
ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", "*")
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

PROD_URL = "https://bojang-service-98909072626.asia-northeast3.run.app"
FRONTEND_URL = os.getenv("FRONTEND_URL", PROD_URL)

CSRF_TRUSTED_ORIGINS = _env_list(
    "CSRF_TRUSTED_ORIGINS",
    f"{PROD_URL},https://storage.googleapis.com",
)

# 기본 CORS: 환경변수 기반 (Cloud Run에서 사용)
CORS_ALLOWED_ORIGINS = _env_list("CORS_ALLOWED_ORIGINS", PROD_URL)
CORS_EXPOSE_HEADERS = ["Content-Disposition"]
CORS_ALLOW_CREDENTIALS = True

# 🔥 로컬 개발 환경(Cloud Run 아님)에서는 무조건 localhost 프론트 허용
if not IS_CLOUD_RUN:
    extra = ["http://localhost:5173", "http://127.0.0.1:5173"]
    CORS_ALLOWED_ORIGINS = sorted(list(set(CORS_ALLOWED_ORIGINS + extra)))

# ── 7) 앱
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

# 운영에서 django-extensions 미설치로 인한 ImportError 방지
if DEBUG:
    INSTALLED_APPS.append("django_extensions")

# ── 8) 미들웨어
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # ← CommonMiddleware 위
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ── 9) URL/템플릿/WSGI
ROOT_URLCONF = "bojang_api.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    # bojang-frontend/dist 를 템플릿/정적 루트로 사용 (프론트 빌드 결과)
    "DIRS": [os.path.join(BASE_DIR, "bojang-frontend", "dist")],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ]
    },
}]
WSGI_APPLICATION = "bojang_api.wsgi.application"

# ── 10) 데이터베이스 (Cloud Run/Job: 시크릿 또는 ENV를 통해 주입)
if os.getenv("DB_NAME"):
    _DB_NAME = os.getenv("DB_NAME")
    _DB_USER = os.getenv("DB_USER")
    _DB_PASS = os.getenv("DB_PASSWORD")
    _DB_HOST = os.getenv("DB_HOST", "")  # '/cloudsql/…' 이거나 '127.0.0.1'
    _DB_PORT = os.getenv("DB_PORT", "5432")
    _DB_INSTANCE = os.getenv("DB_INSTANCE")  # 예: elegant-…:asia-northeast3:bojang

    if _DB_HOST:
        if _DB_HOST.startswith("/cloudsql/"):
            DATABASES = {
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": _DB_NAME,
                    "USER": _DB_USER,
                    "PASSWORD": _DB_PASS,
                    "HOST": _DB_HOST,     # /cloudsql/PROJECT:REGION:INSTANCE
                    "PORT": "5432",
                    "CONN_MAX_AGE": 60,
                }
            }
        else:
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
    elif _DB_INSTANCE:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": _DB_NAME,
                "USER": _DB_USER,
                "PASSWORD": _DB_PASS,
                "HOST": f"/cloudsql/{_DB_INSTANCE}",
                "PORT": "5432",
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
else:
    # 로컬/기본: sqlite
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ── 11) i18n
LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

# ── 12) 정적/스토리지
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Vite 빌드 결과(dist)를 정적 디렉토리로 사용
STATICFILES_DIRS = [os.path.join(BASE_DIR, "bojang-frontend", "dist")]

GS_BUCKET_NAME = "bojang-static-files-elegant-shelter"
GS_DEFAULT_ACL = None

if IS_CLOUD_RUN:
    # 🔥 Cloud Run / 운영: GCS 스토리지 사용
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
else:
    # 🔥 로컬 개발: 로컬 디스크에 저장
    MEDIA_ROOT = BASE_DIR / "media"
    MEDIA_URL = "/media/"
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── 13) DRF/JWT
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication"
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny"
    ],
}
_access_hours = int(os.getenv("JWT_EXPIRES_HOURS", "12"))
_jwt_signing_key = os.getenv("JWT_SECRET") or SECRET_KEY
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=_access_hours),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ALGORITHM": "HS256",
    "SIGNING_KEY": _jwt_signing_key,
}

# ── 14) 운영 보안
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# ── 15) 로깅
LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO")

# 기본은 콘솔만. 파일 로깅은 명시적으로 LOG_TO_FILE=1 일 때만 켬.
USE_FILE_LOG = os.getenv("LOG_TO_FILE", "0") == "1"
# runserver(autoreload) 부모 프로세스에서는 파일 핸들러 금지 (Windows 잠김/Cloud Build 실패 방지)
_RUN_MAIN = os.environ.get("RUN_MAIN") == "true"
_IS_WINDOWS = (os.name == "nt")


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


if IS_CLOUD_RUN:
    # Cloud Run/Jobs → 콘솔만
    LOGGING = _console_only_logging()
else:
    if not USE_FILE_LOG or not _RUN_MAIN or _IS_WINDOWS:
        # 기본(또는 부모 프로세스/윈도우): 콘솔만
        LOGGING = _console_only_logging()
    else:
        # 선택(로컬 자식 프로세스, 비윈도우): 파일 + 콘솔
        LOG_DIR = BASE_DIR / "log_files"
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        LOGGING = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "verbose": {
                    "format": "[%(asctime)s] %(levelname)s - %(name)s - %(message)s"
                },
                "simple": {"format": "[%(asctime)s] %(levelname)s - %(message)s"},
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "simple",
                    "level": LOG_LEVEL,
                },
                "file": {
                    "class": "logging.handlers.TimedRotatingFileHandler",
                    "filename": str(LOG_DIR / "debug.log"),
                    "when": "midnight",
                    "backupCount": 7,
                    "encoding": "utf-8",
                    "level": LOG_LEVEL,
                    "formatter": "verbose",
                    "delay": True,  # 파일 오픈 지연 → 잠김/권한 이슈 완화
                },
            },
            "root": {"handlers": ["console", "file"], "level": LOG_LEVEL},
            "loggers": {
                "django": {
                    "handlers": ["console", "file"],
                    "level": LOG_LEVEL,
                    "propagate": False,
                }
            },
        }

# ── 16) 이메일
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_USE_TLS = False
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    f"보장분석 <{EMAIL_HOST_USER}>",
)
EMAIL_TIMEOUT = 30
