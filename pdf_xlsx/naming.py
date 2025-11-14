# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

_FORBIDDEN = r'[\\/:*?"<>|]'  # Windows/macOS 공통 금지문자

def _nfc(s: str) -> str:
    """유니코드 정규화(NFC)"""
    try:
        return unicodedata.normalize("NFC", s or "")
    except Exception:
        return s or ""

def safe_filename(stem: str, ext: str = ".xlsx", fallback: str = "결과") -> str:
    """
    사용자에게 내려갈 파일명을 안전하게 생성.
    - 금지문자 제거, 앞뒤 공백 제거, 너무 짧으면 fallback 사용
    - 길이 과도 시 앞부분만 남기고 접미사 유지
    """
    s = _nfc(stem)
    s = re.sub(_FORBIDDEN, "", s).strip()
    if not s:
        s = fallback
    # 파일명 너무 길어지면 120자로 컷(확장자 제외)
    if len(s) > 120:
        s = s[:120].rstrip()
    ext = ext if ext.startswith(".") else f".{ext}"
    return f"{s}{ext}"

def result_filename_from_pdf(pdf_filename: str) -> str:
    """
    원본 PDF 파일명에서 결과 엑셀 파일명을 생성.
    예) '박동숙.pdf' -> '박동숙_보장분석_결과.xlsx'
    """
    stem = Path(pdf_filename).stem or "분석"
    return safe_filename(f"{stem}_보장분석_결과", ".xlsx")
