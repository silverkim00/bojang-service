# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

from .paths import ensure_dir
from .logger_setup import get_logger

logger = get_logger("app")


@dataclass
class SaveResult:
    backend: str
    filename: str
    path: Optional[str] = None
    signed_url: Optional[str] = None
    blob: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "filename": self.filename,
            "path": self.path,
            "signed_url": self.signed_url,
            "blob": self.blob,
        }


class LocalStore:
    """
    결과 파일을 로컬 파일시스템에 유지.
    Cloud Run에선 보통 임시(/tmp)에만 쓰기 가능하므로 다운로드 응답에 바로 사용하거나
    별도 GCS 업로드 전 중간 저장소로 사용.
    """
    def __init__(self, out_dir: str | Path):
        touch = ensure_dir(Path(out_dir) / ".touch")
        self.out_dir = touch.parent

    def save(self, result_path: Path) -> SaveResult:
        # 로컬은 이미 생성된 파일 경로를 그대로 노출
        p = Path(result_path)
        if not p.exists():
            raise FileNotFoundError(p)
        return SaveResult(
            backend="local",
            filename=p.name,
            path=str(p),
        )


class GcsStore:
    """
    google-cloud-storage 사용. 환경변수:
      - GCS_BUCKET (필수)
      - GCS_PREFIX (선택, 기본 'results/')
      - GCS_SIGNED_SECONDS (선택, 기본 3600)
    """
    def __init__(self, bucket: Optional[str] = None, prefix: Optional[str] = None):
        try:
            from google.cloud import storage  # type: ignore
        except Exception as e:
            raise RuntimeError("google-cloud-storage 미설치 혹은 가져오기 실패") from e

        self._storage_mod = storage
        self.client = storage.Client()
        self.bucket_name = bucket or os.getenv("GCS_BUCKET")
        if not self.bucket_name:
            raise RuntimeError("GCS_BUCKET 환경변수가 필요합니다.")
        self.bucket = self.client.bucket(self.bucket_name)
        self.prefix = (prefix or os.getenv("GCS_PREFIX") or "results/").rstrip("/") + "/"
        self.signed_secs = int(os.getenv("GCS_SIGNED_SECONDS", "3600"))

    def save(self, result_path: Path) -> SaveResult:
        p = Path(result_path)
        if not p.exists():
            raise FileNotFoundError(p)

        blob_name = self.prefix + p.name
        blob = self.bucket.blob(blob_name)
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        blob.upload_from_filename(str(p), content_type=content_type)

        try:
            url = blob.generate_signed_url(
                version="v4",
                expiration=self.signed_secs,
                method="GET",
            )
        except Exception as e:
            logger.warning(f"[GcsStore] 서명 URL 생성 실패: {e}")
            url = None

        return SaveResult(
            backend="gcs",
            filename=p.name,
            signed_url=url,
            blob=blob_name,
        )


def get_store(default_out_dir: Optional[str | Path] = None):
    """
    환경 변수 PDFX_STORAGE=local|gcs 에 맞는 저장소 인스턴스를 반환.
    - local(default): default_out_dir 필요
    - gcs: GCS_BUCKET 필요
    """
    backend = (os.getenv("PDFX_STORAGE") or "local").lower()
    if backend == "gcs":
        return GcsStore()
    # local
    out = default_out_dir or os.getenv("PDFX_OUT") or "/tmp/pdfx"
    return LocalStore(out)


def save_result(result_path: Path, default_out_dir: Optional[str | Path] = None) -> Dict[str, Any]:
    """
    결과 파일 저장(혹은 노출 메타 생성) 헬퍼.
    백엔드에서:
        meta = save_result(xlsx_path)
        # local: meta["path"] 로 FileResponse
        # gcs:   meta["signed_url"] 로 프론트에 URL 반환
    """
    store = get_store(default_out_dir)
    meta = store.save(Path(result_path))
    d = meta.as_dict()
    logger.info(f"[save_result] {d}")
    return d
