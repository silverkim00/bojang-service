# -*- coding: utf-8 -*-
"""
로그 파일(예: unmapped/excluded 등) 중 보존기간 초과분을 삭제합니다.
- 기본 대상: settings.LOG_DIR 또는 'logs' 폴더
- Django default_storage(GCS 등) 지원
- 보존기간: env CLEANUP_RETENTION_DAYS(기본 14일)
"""
import os
import sys
from datetime import datetime, timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")  # 프로젝트 settings 모듈 경로에 맞추세요

import django  # noqa: E402
django.setup()  # noqa: E402

from django.conf import settings  # noqa: E402
from django.core.files.storage import default_storage  # noqa: E402
from django.utils.timezone import now  # noqa: E402


def _get_retention_days() -> int:
    try:
        return int(os.environ.get("CLEANUP_RETENTION_DAYS", "14"))
    except Exception:
        return 14


def _list_storage_recursive(prefix: str):
    """
    default_storage.listdir(prefix)를 재귀적으로 순회하여 파일 경로 리스트를 반환.
    """
    files_found = []
    try:
        dirs, files = default_storage.listdir(prefix)
    except Exception:
        return files_found

    for f in files:
        files_found.append(os.path.join(prefix, f).replace("\\", "/"))
    for d in dirs:
        sub_prefix = os.path.join(prefix, d).replace("\\", "/")
        files_found.extend(_list_storage_recursive(sub_prefix))
    return files_found


def _delete_old_files_on_storage(prefix: str, retention_days: int) -> int:
    """
    Django storage 기반(GCS 포함)에서 보존기간 초과 파일 삭제.
    modified_time() 지원 시 이를 사용.
    """
    deleted = 0
    cutoff = now() - timedelta(days=retention_days)
    file_paths = _list_storage_recursive(prefix)

    for path in file_paths:
        try:
            # 일부 스토리지는 modified_time 지원
            try:
                mtime = default_storage.modified_time(path)
                too_old = (mtime < cutoff)
            except Exception:
                # modified_time 미지원 시: 존재만 확인하고 생략(보수적)
                # 필요 시 파일명에 날짜를 포함하도록 파이프라인을 개선하세요.
                continue

            if too_old:
                default_storage.delete(path)
                deleted += 1
        except Exception:
            continue
    return deleted


def _delete_old_files_on_local(log_dir: str, retention_days: int) -> int:
    """
    로컬 파일시스템에서 보존기간 초과 파일 삭제.
    (Cloud Run의 경우 일반적으로 GCS 사용이므로 local은 보조용)
    """
    if not os.path.isdir(log_dir):
        return 0

    cutoff_ts = (datetime.utcnow() - timedelta(days=retention_days)).timestamp()
    deleted = 0

    for root, _, files in os.walk(log_dir):
        for name in files:
            path = os.path.join(root, name)
            try:
                mtime = os.path.getmtime(path)
                if mtime < cutoff_ts:
                    os.remove(path)
                    deleted += 1
            except Exception:
                continue
    return deleted


def main():
    retention_days = _get_retention_days()

    # 우선순위: settings.LOG_DIR > 'logs'
    log_dir = getattr(settings, "LOG_DIR", None) or "logs"

    # default_storage를 기본으로 시도(GCS 등 원격 저장소)
    deleted_storage = 0
    try:
        # prefix가 디렉토리 형식이도록 보정
        prefix = log_dir.strip("/").rstrip("/") + "/"
        deleted_storage = _delete_old_files_on_storage(prefix, retention_days)
    except Exception:
        deleted_storage = 0

    # 로컬 폴더도 보조적으로 정리
    deleted_local = _delete_old_files_on_local(log_dir, retention_days)

    print(f"[cleanup_logs] retention={retention_days}d, storage_deleted={deleted_storage}, local_deleted={deleted_local}")


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except Exception as e:
        print(f"[cleanup_logs] ERROR: {e}", file=sys.stderr)
        sys.exit(1)
