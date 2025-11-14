# rules/nursing.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from typing import Dict, List, Optional

from .. import config
from ..utils import _nz, _nosp, parse_amount, format_amount_short

# ───────────────── 라벨 존재/선택 ─────────────────
def _exists(label: str) -> bool:
    try:
        return label in config.HARDCODED_ROW_MAP
    except Exception:
        return False

LBL_MAIN    = "간병인/간호통합"          # 37행(표준)
LBL_SUPPORT = "간병인지원" if _exists("간병인지원") else LBL_MAIN  # 없으면 메인 행으로 병기

# ───────────────── 매칭 패턴 ─────────────────
# “지원”이 붙은 간병 계열 (우선 인식)
RX_CARE_SUPPORT = re.compile(
    r"(간병인?\s*지원|간병\s*지원|간병\s*비\s*지원|간병인지원|간병지원)",
    re.I,
)

# “지원”이 없는 일반 간병인/간병비
RX_CAREGIVER = re.compile(
    r"(간병인|간병\s*비|간병비)(?!\s*지원)",
    re.I,
)

# 간호·간병 통합 계열
RX_NURSING = re.compile(
    r"(간호\s*[·\.\-]?\s*간병통합|간호간병통합|간호간병)",
    re.I,
)

# 불요(오탐 방지) — 요양보호사는 제외
RX_EXCLUDE = re.compile(r"(요양보호사)", re.I)

def _ns(txt: str) -> str:
    return _nosp(_nz(txt))

def _txt(item: Dict) -> str:
    return _ns(item.get("name", "")) + "|" + _ns(item.get("association_name", ""))

# ───────────────── 분류 ─────────────────
def classify(item: Dict) -> Optional[str]:
    """
    버킷 분류:
      - 간병 ‘지원’ 계열 => LBL_SUPPORT (없으면 LBL_MAIN)
      - 일반 간병인/간병비 => LBL_MAIN
      - 간호·간병통합 => LBL_MAIN
    """
    t = _txt(item)
    if RX_EXCLUDE.search(t):
        return None

    if RX_CARE_SUPPORT.search(t):
        return LBL_SUPPORT
    if RX_CAREGIVER.search(t) or RX_NURSING.search(t):
        return LBL_MAIN
    return None

# ───────────────── 집계 유틸 ─────────────────
def _amt_list(items: List[dict]) -> List[int]:
    out: List[int] = []
    for c in items or []:
        v = None
        try:
            v = c.get("_parsed_amount")
            if isinstance(v, (int, float)) and v > 0:
                out.append(int(v)); continue
        except Exception:
            pass
        try:
            v = parse_amount(c.get("amount"))
            if v and v > 0:
                out.append(int(v))
        except Exception:
            pass
    return out

def _max_amt(items: List[dict]) -> int:
    vals = _amt_list(items)
    return max(vals) if vals else 0

def _mark_discards(group: List[dict], picked_value: int, tag: str):
    """최대값 1건만 남기고 나머지는 로그용 마킹."""
    if not group or picked_value <= 0:
        return
    for c in group:
        try:
            val = c.get("_parsed_amount")
            if not isinstance(val, (int, float)) or val <= 0:
                val = parse_amount(c.get("amount"))
            val = int(val) if val else 0
        except Exception:
            val = 0
        if val != picked_value and not c.get("_reason"):
            c["_reason"] = "AGG/SET_MAX_ONLY"
            c["_hint"]   = tag  # "간병" / "통합" / "지원"

# ───────────────── 집계 ─────────────────
def aggregate(bucket: Dict[str, List[dict]], out: Dict[str, str], scope: Dict | None = None) -> None:
    """
    집계 규칙
      - LBL_MAIN(간병인/간호통합) 버킷: 일반 간병인 최대 1건, 간호통합 최대 1건 → "간병인 X, 간호통합 Y"
      - LBL_SUPPORT(간병인지원) 버킷:
         • 라벨이 있으면 별도 행 "간병인지원 Z"
         • 라벨이 없으면 LBL_MAIN 행에 병기("간병인지원 Z")
      - 세트에서 탈락한 항목은 AGG/SET_MAX_ONLY 사유로 로그에 남김
    """
    main_items = bucket.get(LBL_MAIN) or []

    # 동일 버킷 폴백일 수도 있으므로, 서브셋은 반드시 '텍스트 기반'으로 분리한다.
    caregivers = [c for c in main_items if RX_CAREGIVER.search(_txt(c))]
    nursings   = [c for c in main_items if RX_NURSING.search(_txt(c))]
    supports_in_main = [c for c in main_items if RX_CARE_SUPPORT.search(_txt(c))]

    care_max = _max_amt(caregivers) if caregivers else 0
    nurs_max = _max_amt(nursings)   if nursings   else 0

    if caregivers:
        _mark_discards(caregivers, care_max, "간병")
    if nursings:
        _mark_discards(nursings, nurs_max, "통합")

    parts: List[str] = []
    # 표기 순서: 간병인 → 간병인지원 → 간호통합
    if care_max:
        parts.append(f"간병인 {format_amount_short(care_max)}")

    # 지원 항목 처리
    if LBL_SUPPORT != LBL_MAIN:
        support_items = bucket.get(LBL_SUPPORT) or []
        sup_max = _max_amt(support_items) if support_items else 0
        if support_items:
            _mark_discards(support_items, sup_max, "지원")
        if sup_max:
            out[LBL_SUPPORT] = f"간병인지원 {format_amount_short(sup_max)}"
    else:
        # 같은 버킷이므로 메인에서 지원 서브셋만 뽑아 집계
        sup_max = _max_amt(supports_in_main) if supports_in_main else 0
        if supports_in_main:
            _mark_discards(supports_in_main, sup_max, "지원")
        if sup_max:
            parts.append(f"간병인지원 {format_amount_short(sup_max)}")

    if nurs_max:
        parts.append(f"간호통합 {format_amount_short(nurs_max)}")

    if parts:
        out[LBL_MAIN] = ", ".join(parts)
