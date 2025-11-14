# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import json
import os
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Tuple, Union

from .core import analyze_pdf_bytes, _resolve_out_dir  # _resolve_out_dir은 내부에서만 쓰는 헬퍼
from .logger_setup import get_logger

logger = get_logger("app")


class UploadItem(NamedTuple):
    content: bytes
    name: str
    size: int


def _coerce_files(
    files: Iterable[Any],
) -> List[UploadItem]:
    """
    Django UploadedFile / Starlette UploadFile / (bytes, name) / (file-like, name)
    등 다양한 입력을 하나의 리스트로 정규화한다.
    """
    out: List[UploadItem] = []
    for f in files:
        # Django: InMemoryUploadedFile / TemporaryUploadedFile
        if hasattr(f, "read") and hasattr(f, "name"):
            try:
                # 일부 구현은 read가 소모성이므로 bytes로 보관
                b = f.read()
                name = getattr(f, "name", "upload.pdf") or "upload.pdf"
                size = getattr(f, "size", None) or len(b)
                out.append(UploadItem(b, name, size))
                continue
            except Exception as e:
                logger.error(f"[webapi._coerce_files] read error: {e}", exc_info=True)
                continue

        # (bytes, name)
        if isinstance(f, (tuple, list)) and len(f) >= 2 and isinstance(f[0], (bytes, bytearray)):
            b = bytes(f[0])
            name = str(f[1]) or "upload.pdf"
            size = len(b)
            out.append(UploadItem(b, name, size))
            continue

        # (file-like, name)
        if isinstance(f, (tuple, list)) and len(f) >= 2 and hasattr(f[0], "read"):
            b = f[0].read()
            name = str(f[1]) or "upload.pdf"
            size = len(b)
            out.append(UploadItem(b, name, size))
            continue

        logger.warning(f"[webapi._coerce_files] unsupported item ignored: {type(f)}")
    return out


def _limits() -> Tuple[int, int, int]:
    """
    업로드 제한을 환경변수로 가져온다.
      - MAX_FILES_PER_REQ: 요청당 파일 개수(기본 10)
      - MAX_FILE_BYTES:    파일당 최대 바이트(기본 50MB)
      - PDFX_WORKERS:      병렬 처리 쓰레드 수(기본 2; 1~4 권장)
    """
    max_files = int(os.getenv("MAX_FILES_PER_REQ", "10"))
    max_bytes = int(os.getenv("MAX_FILE_BYTES", str(50 * 1024 * 1024)))
    workers = max(1, min(8, int(os.getenv("PDFX_WORKERS", "2"))))
    return max_files, max_bytes, workers


def process_uploads_to_zip(
    files: Iterable[Any],
    out_dir: Optional[Union[str, Path]] = None,
    zip_name: str = "result.zip",
) -> Dict[str, Any]:
    """
    여러 업로드 PDF를 분석하여 ZIP 하나로 묶는다.
    - files: Django UploadedFile 리스트, 또는 [(bytes, filename), ...] 등 섞여도 됨
    - out_dir: 결과 경로(없으면 플랫폼 정책에 따라 /tmp 또는 config 경로)
    - zip_name: ZIP 파일명(내부 아카이브명, 디스크 상 파일명 모두)

    반환 예시:
    {
      "zip_path": "/tmp/pdfx/result.zip",
      "ok": [{"file":"a.pdf","result":"a_보장분석_결과.xlsx"}, ...],
      "fail": [{"file":"b.pdf","reason":"..."}],
      "elapsed_sec": 3.21
    }
    """
    t0 = time.time()
    base_out = _resolve_out_dir(out_dir)
    max_files, max_bytes, max_workers = _limits()

    items = _coerce_files(files)
    if not items:
        return {"zip_path": None, "ok": [], "fail": [{"file": "-", "reason": "NO_FILES"}], "elapsed_sec": 0.0}

    if len(items) > max_files:
        return {
            "zip_path": None,
            "ok": [],
            "fail": [{"file": "-", "reason": f"TOO_MANY_FILES(>{max_files})"}],
            "elapsed_sec": round(time.time() - t0, 2),
        }

    overs = [it.name for it in items if it.size and it.size > max_bytes]
    if overs:
        mb = max_bytes // (1024 * 1024)
        return {
            "zip_path": None,
            "ok": [],
            "fail": [{"file": n, "reason": f"FILE_TOO_LARGE(>{mb}MB)"} for n in overs],
            "elapsed_sec": round(time.time() - t0, 2),
        }

    # 분석 수행 (부분 실패 허용)
    results: List[Tuple[str, Path]] = []
    fails: List[Dict[str, str]] = []

    def work(it: UploadItem) -> Tuple[str, Optional[Path], Optional[str]]:
        try:
            xlsx_path = analyze_pdf_bytes(it.content, it.name, out_dir=base_out)
            return it.name, Path(xlsx_path), None
        except Exception as e:
            return it.name, None, str(e)

    if max_workers > 1 and len(items) > 1:
        # 병렬
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            fut = {ex.submit(work, it): it.name for it in items}
            for f in as_completed(fut):
                name, path, err = f.result()
                if path is not None:
                    results.append((name, path))
                else:
                    fails.append({"file": name, "reason": err or "UNKNOWN"})
    else:
        # 순차
        for it in items:
            name, path, err = work(it)
            if path is not None:
                results.append((name, path))
            else:
                fails.append({"file": name, "reason": err or "UNKNOWN"})

    # ZIP 생성 (메모리 폭주 방지를 위해 디스크에 작성)
    zip_path = base_out / zip_name
    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, xlsx in results:
                # 내부 파일명: 결과 파일 실제 이름
                zf.write(xlsx, arcname=xlsx.name)
            manifest = {
                "elapsed_sec": round(time.time() - t0, 2),
                "count": len(items),
                "ok": [{"file": n, "result": p.name} for n, p in results],
                "fail": fails,
            }
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.error(f"[webapi.process_uploads_to_zip] zip write error: {e}", exc_info=True)
        return {
            "zip_path": None,
            "ok": [{"file": n, "result": p.name} for n, p in results],
            "fail": fails + [{"file": "-", "reason": f"ZIP_WRITE_ERROR:{e}"}],
            "elapsed_sec": round(time.time() - t0, 2),
        }

    out = {
        "zip_path": str(zip_path),
        "ok": [{"file": n, "result": p.name} for n, p in results],
        "fail": fails,
        "elapsed_sec": round(time.time() - t0, 2),
    }
    logger.info(f"[webapi.process_uploads_to_zip] -> {out['zip_path']} (ok={len(results)}, fail={len(fails)})")
    return out
