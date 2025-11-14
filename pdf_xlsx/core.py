# pdf_xlsx/core.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .paths import ensure_dir  # 이미 생성한 paths.py 사용
from .logger_setup import get_logger

# 프로젝트 내부 엔진 구성요소
from .pdf_processor import extract_data_from_pdf
from .excel_handler import create_analysis_report
import pdf_xlsx.config as config

logger = get_logger("app")


def _default_out_dir() -> Path:
    """
    Cloud Run 고려:
    - CLOUD_RUN=1 이면 /tmp 우선
    - 그 외엔 config.OUTPUT_DIR 사용
    - 환경변수 PDFX_OUT 있으면 강제 덮어씀
    """
    env_out = os.getenv("PDFX_OUT")
    if env_out:
        return ensure_dir(Path(env_out) / ".touch").parent

    if os.getenv("CLOUD_RUN", "0") == "1":
        return ensure_dir(Path("/tmp/pdfx") / ".touch").parent

    return ensure_dir(Path(config.OUTPUT_DIR) / ".touch").parent


def _resolve_out_dir(out_dir: Optional[str | Path]) -> Path:
    if out_dir:
        return ensure_dir(Path(out_dir) / ".touch").parent
    return _default_out_dir()


def analyze_pdf_file(
    in_path: str | Path,
    out_dir: Optional[str | Path] = None,
    template_file: Optional[str | Path] = None,
) -> Path:
    """
    단일 PDF 경로 -> 결과 XLSX 경로 반환.
    - in_path: 절대/상대 모두 허용
    - out_dir: 없으면 Cloud Run은 /tmp, 로컬은 config.OUTPUT_DIR 등 정책 따름
    - template_file: 없으면 config.TEMPLATE_FILE 사용
    """
    src = Path(in_path)
    if not src.exists():
        raise FileNotFoundError(f"PDF not found: {src}")

    base_out = _resolve_out_dir(out_dir)
    tpl = str(template_file or config.TEMPLATE_FILE)

    logger.info(f"[analyze_pdf_file] src={src} tpl={tpl} out_dir={base_out}")
    data = extract_data_from_pdf(src)
    # excel_handler가 결과 파일을 생성하고 경로 반환하는 구조를 사용
    xlsx_path = create_analysis_report(
        data, template_path=tpl, out_dir=base_out
    )
    logger.info(f"[analyze_pdf_file] -> {xlsx_path}")
    return Path(xlsx_path)


def analyze_pdf_bytes(
    pdf_bytes: bytes,
    filename: str = "upload.pdf",
    out_dir: Optional[str | Path] = None,
    template_file: Optional[str | Path] = None,
) -> Path:
    """
    업로드 바이너리를 임시 PDF로 저장 후 analyze_pdf_file 실행.
    - 백엔드(React 업로드)에서 이 함수만 호출하면 됨.
    """
    base_out = _resolve_out_dir(out_dir)
    stem = Path(filename).stem or "upload"
    tmp_pdf = base_out / f"__in__{stem}.pdf"
    tmp_pdf.write_bytes(pdf_bytes)
    logger.info(f"[analyze_pdf_bytes] saved temp={tmp_pdf}")
    return analyze_pdf_file(tmp_pdf, out_dir=base_out, template_file=template_file)


def _collect_inputs(inputs: Optional[Iterable[str | Path]]) -> List[Path]:
    """
    폴더/글롭/파일 리스트 섞여 들어와도 모두 PDF 리스트로 정규화.
    """
    if not inputs:
        # 기본: config.INPUT_DIR 아래 모든 PDF
        root = Path(config.INPUT_DIR)
        return [p for p in root.glob("**/*.pdf") if p.is_file()]

    out: List[Path] = []
    for it in inputs:
        s = str(it)
        # 글롭 패턴
        if any(ch in s for ch in "*?[]"):
            out.extend([p for p in Path().glob(s) if p.suffix.lower() == ".pdf"])
            continue
        p = Path(s)
        if p.is_dir():
            out.extend([x for x in p.glob("**/*.pdf") if x.is_file()])
        elif p.is_file() and p.suffix.lower() == ".pdf":
            out.append(p)
    # 중복 제거(절대경로 기준)
    uniq, seen = [], set()
    for p in out:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            uniq.append(rp)
    return uniq


def analyze_many(
    inputs: Optional[Iterable[str | Path]] = None,
    out_dir: Optional[str | Path] = None,
    template_file: Optional[str | Path] = None,
) -> List[Path]:
    """
    여러 PDF 일괄 처리.
    - 터미널 배치나, 서버에서 다중 업로드를 받아 내부적으로 돌릴 때 사용.
    - 일부 실패해도 나머지는 계속 진행.
    """
    files = _collect_inputs(inputs)
    base_out = _resolve_out_dir(out_dir)
    tpl = str(template_file or config.TEMPLATE_FILE)

    results: List[Path] = []
    for pdf in files:
        try:
            logger.info(f"[analyze_many] processing: {pdf}")
            data = extract_data_from_pdf(pdf)
            xlsx = create_analysis_report(data, template_path=tpl, out_dir=base_out)
            results.append(Path(xlsx))
        except Exception as e:
            logger.error(f"[analyze_many] fail: {pdf} -> {e}", exc_info=True)
    logger.info(f"[analyze_many] done -> {len(results)} files")
    return results
