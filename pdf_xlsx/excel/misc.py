# -*- coding: utf-8 -*-
"""
excel/misc.py — v2025-11-06
- 14행 텍스트(납입면제/납입지원) 생성
- unmapped/excluded 로그 정규화
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional

from pdf_xlsx.utils import _nz, format_amount_short


# 14행 텍스트용: 납입면제 / 납입지원 키워드
_WAIVER_RX  = re.compile(r"(보험료\s*납입\s*면제|납입\s*면제|보험료면제)", re.IGNORECASE)
_SUPPORT_RX = re.compile(r"(보험료\s*납입\s*지원|납입\s*지원|보험료\s*지원|납입지원금)", re.IGNORECASE)

# 부정(면제/지원 아님)
_NEG_WAIVER  = re.compile(r"(면책|예외|제외|비적용|유예|감면|인하|할인)", re.IGNORECASE)
_NEG_SUPPORT = re.compile(r"(면제|유예|감면)", re.IGNORECASE)


def _to_int_amount(x) -> Optional[int]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return int(x)
    m = re.findall(r"\d+", str(x))
    if not m:
        return None
    try:
        return int("".join(m))
    except Exception:
        return None


def _fmt_amount_short(n: int) -> str:
    try:
        # 외부 유틸이 한국식 축약(만/억 등)을 반환한다고 가정
        return format_amount_short(n)
    except Exception:
        return f"{n:,}"


def build_row14_text(product: dict, mapped: Dict[str, object]) -> Optional[str]:
    """
    납입면제/납입지원 신호를 모아 14행 '기타' 셀에 병기할 텍스트 생성.
    예) "납입면제, 납입지원 1천만"
    """
    raw_name = product.get("product_name", "") or ""
    covs = product.get("coverages") or []

    has_waiver = False
    support_amounts: List[int] = []

    for cov in covs:
        nm = _nz(cov.get("name"))
        assoc = _nz(cov.get("association_name"))
        s = f"{nm}|{assoc}"
        if _WAIVER_RX.search(s) and not _NEG_WAIVER.search(s):
            has_waiver = True
        if _SUPPORT_RX.search(s) and not _NEG_SUPPORT.search(s):
            amt = _to_int_amount(cov.get("amount"))
            support_amounts.append(amt or 0)

    # 상품명 자체에 면제 키워드가 있을 수도 있음
    if not has_waiver:
        if _WAIVER_RX.search(raw_name) and not _NEG_WAIVER.search(raw_name):
            has_waiver = True

    parts: List[str] = []
    if has_waiver:
        parts.append("납입면제")

    if support_amounts:
        mx = max(support_amounts)
        parts.append(f"납입지원 {_fmt_amount_short(mx)}만" if mx > 0 else "납입지원")

    return ", ".join(parts) if parts else None


def normalize_log_entries(seq: Iterable) -> List[str]:
    """
    unmapped/excluded 로그를 문자열로 정규화하고 중복 제거.
    포맷: name|association|amount|_reason|_hint
    """
    norm = []
    for x in (seq or []):
        if isinstance(x, dict):
            name = _nz(x.get("name"))
            assoc = _nz(x.get("association_name"))
            amount = _nz(x.get("amount"))
            reason = _nz(x.get("_reason"))
            hint = _nz(x.get("_hint"))
            norm.append(f"{name}|{assoc}|{amount}|{reason}|{hint}")
        else:
            norm.append(str(x))
    seen, out = set(), []
    for s in norm:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out
