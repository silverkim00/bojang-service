# rules/death.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from typing import Dict, List, Optional
from ..utils import _nz, _nosp, parse_amount, format_amount_short

"""
목표
- 후유장해(상해/질병)를 퍼센트/범위 등 원문 수식 그대로 병기해서 출력
  예) "상해(20-100%) 1억", "상해80%이상 100만", "상해 1천만"
- '특정상해후유장해'는 이 레이어에서는 집계 대상에서 제외(상위 exclude가 1차 방어)
- 다른 엔진 영향 금지: 여기서는 out의 두 키만 덮어쓴다.
    · "상해후유장해"
    · "질병후유장해"
"""

LBL_I = "상해후유장해"
LBL_D = "질병후유장해"

# 퍼센트/범위 토큰 수집용 정규식들 (공백/기호 변형 허용)
RX_RANGE_1 = re.compile(r"(\d+)\s*~\s*(\d+)\s*%")
RX_RANGE_2 = re.compile(r"(\d+)\s*-\s*(\d+)\s*%")
RX_GTE     = re.compile(r"(\d+)\s*%\s*이상")
RX_LTE     = re.compile(r"(\d+)\s*%\s*이하")
RX_PLAIN   = re.compile(r"(\d+)\s*%")  # 범위/이상/이하가 없을 때만 사용

def _text(c: Dict) -> str:
    return _nosp(f"{_nz(c.get('name',''))}|{_nz(c.get('association_name',''))}")

def _amt(c: Dict) -> int:
    try:
        return int(parse_amount(c.get("amount", "0")))
    except Exception:
        return 0

def _extract_qualifier(s: str) -> Optional[str]:
    """
    원문에 있는 퍼센트/범위를 최대한 그대로 빼서 표시에 쓴다.
    우선순위: 범위(~, -) > 이상/이하 > 단일 %
    반환 예: "20-100%", "3~100%", "80%이상", "80%"  (내부 공백 제거)
    """
    s = _nosp(s)
    m = RX_RANGE_1.search(s)
    if m:
        return f"{m.group(1)}~{m.group(2)}%"
    m = RX_RANGE_2.search(s)
    if m:
        return f"{m.group(1)}-{m.group(2)}%"
    m = RX_GTE.search(s)
    if m:
        return f"{m.group(1)}%이상"
    m = RX_LTE.search(s)
    if m:
        return f"{m.group(1)}%이하"
    # 단일 %는 범위/이상/이하가 없을 때만
    m = RX_PLAIN.search(s)
    if m:
        return f"{m.group(1)}%"
    return None

def _pick_best(items: List[Dict]) -> Optional[Dict]:
    """
    같은 라벨 내에서 금액이 가장 큰 1건을 고른다.
    금액 동률이면 먼저 등장한 항목을 유지.
    """
    best = None
    best_v = 0
    for c in items or []:
        v = _amt(c)
        if v > best_v:
            best_v = v
            best = c
    return best

def _render(label_prefix: str, qualifier: Optional[str], value: int) -> str:
    """
    표기 규칙:
      - 범위(20-100%, 3~100%) → 접두어 뒤에 괄호로:  상해(20-100%) 1억
      - 이상/이하/단일% → 괄호 없이 붙여쓰기:      상해80%이상 1백만, 상해80% 1백만
      - qualifier 없으면:                          상해 1천만
    """
    if qualifier:
        if ("~" in qualifier) or ("-" in qualifier):
            return f"{label_prefix}({qualifier}) {format_amount_short(value)}"
        else:
            return f"{label_prefix}{qualifier} {format_amount_short(value)}"
    return f"{label_prefix} {format_amount_short(value)}"

def aggregate(bucket: Dict[str, List[Dict]], out: Dict[str, str], scope=None) -> None:
    """
    coverage_processor.process_coverages(...) 초반에 이미 기본 4행(사망/후유)을 채우지만,
    여기서 후유장해 2행만 '원문 수식 병기' 규칙으로 덮어쓴다.
    """
    # 1) 상해후유장해
    if LBL_I in bucket:
        # 특정상해후유장해 등은 (상단 exclude에서 컷되지만) 혹시 남아있다면 여기서도 제거
        items = [c for c in bucket[LBL_I] if "특정상해후유장해" not in _text(c)]
        if items:
            best = _pick_best(items)
            if best:
                q = _extract_qualifier(_text(best))
                v = _amt(best)
                if v > 0:
                    out[LBL_I] = _render("상해", q, v)

    # 2) 질병후유장해
    if LBL_D in bucket:
        items = bucket[LBL_D] or []
        if items:
            best = _pick_best(items)
            if best:
                q = _extract_qualifier(_text(best))
                v = _amt(best)
                if v > 0:
                    out[LBL_D] = _render("질병", q, v)
