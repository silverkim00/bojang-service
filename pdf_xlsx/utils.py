# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
import re
from typing import Tuple

__all__ = [
    "resource_path",
    "parse_amount", "format_amount_short",
    "_nz", "_nosp",
    "strip_exclusions",
    "is_inpatient_text", "is_outpatient_text",
]

# ---------------------------------------------------------------------
# 리소스 경로
# ---------------------------------------------------------------------
def resource_path(relative_path: str) -> str:
    """Get absolute path to resource (dev & PyInstaller)."""
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ---------------------------------------------------------------------
# 공통 문자열 유틸 (coverage_processor 분산)
# ---------------------------------------------------------------------
def _nz(s: object) -> str:
    """None/비문자 → 빈문자."""
    return s if isinstance(s, str) else ""

def _nosp(s: object) -> str:
    """공백 제거 문자열."""
    return re.sub(r"\s+", "", _nz(s))

# “(…제외)”, “유사암 제외/소액암 제외/4대유사암 제외” 제거
_RX_EXCL_PAREN  = re.compile(r"[\(\[\{][^)\]\}]*제외[^)\]\}]*[\)\]\}]")
_RX_EXCL_INLINE = re.compile(r"(유사암|소액암|4대유사암)\s*제외")

def strip_exclusions(text: str) -> str:
    """문장 내 '…제외' 표현을 제거하고 공백 정리."""
    t = _RX_EXCL_PAREN.sub("", _nz(text))
    t = _RX_EXCL_INLINE.sub("", t)
    return re.sub(r"\s+", " ", t).strip()

# 암 입·통원 판별(라벨링 보조)
def is_inpatient_text(text: str) -> bool:
    t = _nosp(text)
    return ("입원" in t) or ("입원의료비" in t) or ("입통원" in t)

def is_outpatient_text(text: str) -> bool:
    t = _nosp(text)
    return ("통원" in t) or ("외래" in t) or ("통원의료비" in t)

# ---------------------------------------------------------------------
# Amount parsing
# ---------------------------------------------------------------------
def _normalize_amount_text(s: str) -> str:
    """금액 문자열 정규화: 공백/콤마/원/부호 제거."""
    if not isinstance(s, str):
        return ""
    s = s.strip()
    s = s.replace(",", "")
    s = re.sub(r"[()\s]", "", s)
    s = s.replace("원", "")
    return s

def _parse_subunits_kr(s: str) -> int:
    """
    '천/백/십' 조합을 정수로 변환 (예: '2천5백' -> 2500, '2050' -> 2050).
    만-블록 내부 등에서 사용.
    """
    if not s:
        return 0
    i, n = 0, len(s)
    total = 0
    ones = 0
    unit_val = {"천": 1000, "백": 100, "십": 10}
    while i < n:
        if s[i].isdigit():
            j = i
            while j < n and s[j].isdigit():
                j += 1
            num = int(s[i:j])
            if j < n and s[j] in unit_val:
                total += num * unit_val[s[j]]
                j += 1
            else:
                ones = ones * 10 ** (j - i) + num
            i = j
        else:
            if s[i] in unit_val:
                total += unit_val[s[i]]
            i += 1
    return total + ones

def parse_amount(amount_str: str) -> int:
    """
    문자열 금액 → 원 단위 정수 변환.
    지원 예시:
      - '50만' -> 500000
      - '2천50만' -> 20500000
      - '1억2천5백만' -> 125000000
      - '1억' -> 100000000
      - '2050만' -> 20500000
      - '150000' -> 150000
    """
    if isinstance(amount_str, (int, float)):
        return int(amount_str)
    s = _normalize_amount_text(amount_str)
    if not s:
        return 0
    if s.isdigit():
        return int(s)

    total = 0

    # 억
    if "억" in s:
        left, s = s.split("억", 1)
        eok_num = _parse_subunits_kr(left) if left else 0
        total += eok_num * 100_000_000

    # 만
    if "만" in s:
        left, s = s.split("만", 1)
        man_num = _parse_subunits_kr(left) if left else 0
        total += man_num * 10_000

    # 잔여(원 단위)
    if s:
        if s.isdigit():
            total += int(s)
        else:
            total += _parse_subunits_kr(s)

    return total

# ---------------------------------------------------------------------
# Amount formatting
# ---------------------------------------------------------------------
def format_amount_short(amount: int) -> str:
    """
    원 단위 정수 → '1억2천5백만', '5백만', '25만', '1,234' 형식.
    """
    if not isinstance(amount, (int, float)) or amount <= 0:
        return "0"
    amount = int(amount)

    if amount < 10_000:
        return f"{amount:,}"

    eok, rem = divmod(amount, 100_000_000)
    man = rem // 10_000

    parts = []
    if eok:
        parts.append(f"{eok}억")

    if man:
        cheon, rem_man = divmod(man, 1000)   # 천만
        baek, rest     = divmod(rem_man, 100)  # 백만, 잔여(만)

        man_parts = []
        if cheon:
            man_parts.append(f"{cheon}천")
        if baek:  # ← 오탈자 수정: baек → baek
            man_parts.append(f"{baek}백")
        if rest:
            man_parts.append(str(rest))

        parts.append("".join(man_parts) + "만")

    return "".join(parts) if parts else "0"


# ─────────────────────────────────────────────────────────────
# Dict 기반 커버리지 헬퍼 (공통)
# ─────────────────────────────────────────────────────────────
from typing import Dict, List, Iterable

def name_assoc(c: Dict) -> str:
    """한 아이템의 name|association_name 합성(원문 유지)."""
    return f"{_nz(c.get('name'))}|{_nz(c.get('association_name'))}"

def name_assoc_ns(c: Dict) -> str:
    """합성 + 공백 제거."""
    return _nosp(name_assoc(c))

def parse_amount_from_item(c: Dict) -> int:
    """coverages dict에서 금액 정수 추출(파싱 실패 0)."""
    try:
        return parse_amount(c.get("amount"))
    except Exception:
        return 0

def amount_list(items: Iterable[Dict]) -> List[int]:
    """여러 dict에서 금액 정수 리스트 추출(>0만)."""
    out: List[int] = []
    for it in items or []:
        v = parse_amount_from_item(it)
        if isinstance(v, int) and v > 0:
            out.append(v)
    return out

def max_amount(items: Iterable[Dict]) -> int:
    """여러 dict에서 금액 최댓값(없으면 0)."""
    vals = amount_list(items)
    return max(vals) if vals else 0

def has_any_ns(text: str, keys: Iterable[str]) -> bool:
    """공백 제거 문자열에 키 중 하나라도 포함되면 True."""
    t = _nosp(text)
    return any(k in t for k in keys)