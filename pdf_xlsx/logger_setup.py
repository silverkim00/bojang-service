# pdf_xlsx/logger_setup.py
from __future__ import annotations
import os
import sys
import logging
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

# ─────────────────────────────────────────────────────────────────────
# Django DEBUG 감지 (비Django 환경에서도 안전)
# ─────────────────────────────────────────────────────────────────────
try:
    from django.conf import settings as django_settings  # type: ignore
    DEBUG = bool(getattr(django_settings, "DEBUG", False))
    BASE_DIR = getattr(django_settings, "BASE_DIR", None)
except Exception:
    DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
    BASE_DIR = None

# ─────────────────────────────────────────────────────────────────────
# 환경변수 스위치
# - APP_TRACE: "1"이면 TRACE 출력 허용, 기본 "0"(차단)
# - APP_LOG_LEVEL: 로거 레벨(기본 INFO). LOG_LEVEL도 지원(우선순위 낮음)
# - CLOUD_RUN/K_SERVICE: Cloud Run 감지
# ─────────────────────────────────────────────────────────────────────
APP_TRACE = os.getenv("APP_TRACE", "0")
APP_LOG_LEVEL = (os.getenv("APP_LOG_LEVEL") or os.getenv("LOG_LEVEL") or "INFO").upper()
ON_CLOUD_RUN = os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN") == "1"

# 과거 호환(FINE_LOGS) — 쓰진 않지만 유지
FINE_LOGS = os.getenv("FINE_LOGS")
if FINE_LOGS is None:
    # 기본: Cloud Run에서는 끔, 로컬은 켬
    FINE_LOGS = "0" if ON_CLOUD_RUN else "1"
FINE_LOGS = (FINE_LOGS == "1")

# ─────────────────────────────────────────────────────────────────────
# 경로 유틸
# ─────────────────────────────────────────────────────────────────────
def _default_base_dir() -> Path:
    # PyInstaller 등
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    # Django 설정이 있으면 우선
    if BASE_DIR:
        try:
            return Path(BASE_DIR)
        except Exception:
            pass
    # 그 외: 현재 파일 기준 상위(프로젝트 루트 가정)
    return Path(__file__).resolve().parent.parent  # pdf_xlsx/..(project root)

def _determine_log_dir() -> Path:
    # 1) 명시적 환경변수
    env_dir = os.getenv("LOG_DIR")
    if env_dir:
        return Path(env_dir)
    # 2) Cloud Run → /tmp/logs
    if ON_CLOUD_RUN:
        return Path("/tmp/logs")
    # 3) 로컬 → <프로젝트>/logs
    return _default_base_dir() / "log_files"

def _ensure_dir(p: Path) -> Path:
    try:
        p.mkdir(parents=True, exist_ok=True)
        return p
    except Exception:
        # 읽기 전용 등 실패 시 /tmp/logs 시도
        fallback = Path("/tmp/logs")
        try:
            fallback.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass  # 그래도 실패하면 파일 로깅 비활성화
        return fallback

# ─────────────────────────────────────────────────────────────────────
# TRACE 필터: 메시지가 "TRACE[" 로 시작하면 APP_TRACE=1 일 때만 통과
# ─────────────────────────────────────────────────────────────────────
class _TraceFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        if isinstance(msg, str) and msg.startswith("TRACE["):
            return APP_TRACE == "1"  # 기본 차단
        return True

# ─────────────────────────────────────────────────────────────────────
# 로거 팩토리
# ─────────────────────────────────────────────────────────────────────
def get_logger(name: str = "app") -> logging.Logger:
    logger = logging.getLogger(name)

    # 이미 구성했으면 재사용(중복 핸들러 방지)
    if logger.handlers:
        return logger

    # 레벨 설정
    level = getattr(logging, APP_LOG_LEVEL, logging.INFO)
    logger.setLevel(level)

    # 공통 포맷터
    console_fmt = logging.Formatter("%(asctime)s %(levelname)s - %(message)s")
    file_fmt    = logging.Formatter("%(asctime)s %(levelname)s - %(name)s - %(message)s")

    # 콘솔 핸들러: 항상
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(console_fmt)
    ch.addFilter(_TraceFilter())           # 🔒 TRACE 차단
    logger.addHandler(ch)

    # 파일 핸들러: DEBUG=False 일 때만 (로컬 dev에서 파일이 과도하게 쌓이지 않도록)
    if not DEBUG:
        log_dir = _ensure_dir(_determine_log_dir())
        try:
            fh = TimedRotatingFileHandler(
                filename=str(log_dir / "debug.log"),
                when="midnight",
                backupCount=int(os.getenv("LOG_BACKUP_COUNT", "7")),
                encoding="utf-8",
                utc=os.getenv("LOG_USE_UTC", "false").lower() == "true",
            )
            fh.setLevel(level)
            fh.setFormatter(file_fmt)
            fh.addFilter(_TraceFilter())   # 🔒 TRACE 차단
            logger.addHandler(fh)
        except Exception as e:
            # 파일 로깅 실패해도 앱은 계속 동작
            err = logging.StreamHandler(sys.stdout)
            err.setFormatter(console_fmt)
            logger.addHandler(err)
            logger.warning(f"File logging disabled ({log_dir}): {e}")

    # 루트로 전파 막기(중복 출력 방지)
    logger.propagate = False
    return logger

# 기본 로거 (기존 import 호환)
logger = get_logger("app")
