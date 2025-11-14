# rules/dementia.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from typing import Dict, List, Optional

from ..utils import _nz, _nosp, parse_amount, format_amount_short

# ── 템플릿 라벨 키
LABEL_DEMENTIA = "치매"     # 38행
LABEL_CARE     = "요양급여" # 39행(신설)

# ── 패턴
RX = {
    # 치매 진단
    "base": re.compile(r"(치매진단|치매)", re.I),
    "sev":  re.compile(r"(중증\s*치매|중증치매|중증)", re.I),
    "mild": re.compile(r"(경증\s*치매|경증치매|경증)", re.I),
    "noise": re.compile(r"(위로금|납입\s*면제|면제)", re.I),

    # 요양급여
    "care_fac":  re.compile(r"(시설급여|장기요양시설)", re.I),
    "care_home": re.compile(r"(재가급여|장기요양재가)", re.I),
    # 주야간보호: 합본/단독/변형 모두 포착
    "care_dn_combo": re.compile(r"(주\s*야\s*간\s*보호|주야간보호)", re.I),
    "care_day":      re.compile(r"(주\s*간\s*보호)", re.I),
    "care_night":    re.compile(r"(야\s*간\s*보호)", re.I),
}

def _has(pat: re.Pattern, txt: str) -> bool:
    return bool(pat.search(txt))

def _t2(item: Dict) -> str:
    return _nosp(_nz(item.get("name", "")) + "|" + _nz(item.get("association_name", "")))

# ── 분류기
def classify(item: Dict) -> Optional[str]:
    """
    치매 진단 → '치매'
    요양급여(시설/재가/주·야간보호) → '요양급여'
    """
    t = _t2(item)

    # 잡음 컷
    if _has(RX["noise"], t):
        return None

    # 요양급여 먼저 태움(샘플 PDF가 전용 상품)
    if _has(RX["care_fac"], t) or _has(RX["care_home"], t) or \
       _has(RX["care_dn_combo"], t) or _has(RX["care_day"], t) or _has(RX["care_night"], t):

        # 세부 타입 태깅(집계에서 사용)
        if _has(RX["care_fac"], t):
            item["_care_sub"] = "시설급여"
        elif _has(RX["care_home"], t):
            item["_care_sub"] = "재가급여"
        else:
            # 주간/야간/합본 → 모두 '주야간보호'로 정규화
            item["_care_sub"] = "주야간보호"
        return LABEL_CARE

    # 치매 진단
    if _has(RX["base"], t):
        return LABEL_DEMENTIA

    return None

# ── 유틸
def _max_amt(items: List[Dict]) -> int:
    vals = []
    for it in items or []:
        try:
            v = int(parse_amount(it.get("amount", "0")))
        except Exception:
            v = 0
        if v > 0:
            vals.append(v)
    return max(vals) if vals else 0

def _is_sev(text: str) -> bool:  return _has(RX["sev"], text)
def _is_mild(text: str) -> bool: return _has(RX["mild"], text)

# ── 집계기
def aggregate(bucket: Dict[str, List[Dict]], out: Dict[str, str], scope: Dict | None = None) -> None:
    """
    치매: 중증/경증 최대값 병기, 둘 중 하나만 있으면 전체 최대 1건만.
    요양급여: 시설급여/재가급여/주야간보호 각각 '최대값'만 병기(합산 금지).
    """
    # 치매(진단)
    if LABEL_DEMENTIA in bucket:
        items = bucket[LABEL_DEMENTIA]
        def t(it: Dict) -> str: return _t2(it)

        sev_items  = [it for it in items if _is_sev(t(it))]
        mild_items = [it for it in items if _is_mild(t(it))]

        sev  = _max_amt(sev_items) if sev_items else 0
        mild = _max_amt(mild_items) if mild_items else 0

        if sev and mild:
            out[LABEL_DEMENTIA] = f"치매 중증 {format_amount_short(sev)}, 경증 {format_amount_short(mild)}"
        else:
            mv = _max_amt(items)
            if mv:
                out[LABEL_DEMENTIA] = f"치매 {format_amount_short(mv)}"

    # 요양급여
    if LABEL_CARE in bucket:
        items = bucket[LABEL_CARE]

        # 주간/야간이 따로 들어와도 분류 단계에서 이미 '주야간보호'로 정규화됨
        max_map = {"시설급여": 0, "재가급여": 0, "주야간보호": 0}

        for it in items:
            sub = it.get("_care_sub")
            if sub not in max_map:
                # 혹시 누락되면 텍스트로 재판정
                tt = _t2(it)
                if _has(RX["care_fac"], tt):  sub = "시설급여"
                elif _has(RX["care_home"], tt): sub = "재가급여"
                else: sub = "주야간보호"
            amt = int(parse_amount(it.get("amount", "0")) or 0)
            if amt > max_map[sub]:
                max_map[sub] = amt

        parts = []
        if max_map["시설급여"] > 0:
            parts.append(f"시설급여 {format_amount_short(max_map['시설급여'])}")
        if max_map["재가급여"] > 0:
            parts.append(f"재가급여 {format_amount_short(max_map['재가급여'])}")
        if max_map["주야간보호"] > 0:
            parts.append(f"주야간보호 {format_amount_short(max_map['주야간보호'])}")

        if parts:
            out[LABEL_CARE] = ", ".join(parts)
