# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from typing import Dict, List, Optional, Tuple

from ..utils import parse_amount, format_amount_short

# ───────── 내부 유틸 ─────────
def _nz(s: str) -> str: return s if isinstance(s, str) else ""
def _nosp(s: str) -> str: return re.sub(r"\s+", "", _nz(s))

def _name_assoc(c: Dict) -> str:
    return _nz(c.get("name", "")) + "|" + _nz(c.get("association_name", ""))

def _amt_list(items: List[Dict]) -> List[int]:
    out: List[int] = []
    for i in items or []:
        try:
            v = int(parse_amount(_nz(i.get("amount",""))))
        except Exception:
            v = 0
        if v > 0:
            out.append(v)
    return out

def _max_amt(items: List[Dict]) -> int:
    vals = _amt_list(items)
    return max(vals) if vals else 0

def _get_amt(item: Dict) -> int:
    try:
        return int(parse_amount(_nz(item.get("amount",""))))
    except Exception:
        return 0

def _has_any(s: str, keys) -> bool:
    s = _nosp(s)
    return any(k in s for k in keys)

# ───────── 키워드 ─────────
RT_LIKE = ("중입자","탄소이온","proton","양성자","imrt","세기조절","강도변조","방사선치료","항암방사선","방사선")
DRUG_LIKE = ("표적","고액항암약물","신정원","항암약물","호르몬","항호르몬","내분비","카티","car-t","cart")

# ───────── 분류기(수술 미개입 가드) ─────────
def classify(_: Dict) -> Optional[str]:
    """수술은 rules.surgery가 전담. 진단/치료 라벨은 상위 라우터에서 부여."""
    return None

# ───────── 집계기 ─────────
def aggregate(bucket: Dict[str, List[Dict]], out: Dict[str, str]) -> None:
    """
    HEART(진단5종 + 2대주요치료비)만 보수적으로 채움.
    - 이미 out에 값 있으면 덮어쓰지 않음.
    - 수술 라벨(2대수술/N대/5대기관)은 절대 터치하지 않음.
    """

    # ── 1) 뇌/심장 진단 5종(보수, 기존 유지)
    if ("뇌혈관질환진단비" in bucket) and ("뇌혈관질환진단비" not in out):
        v = _max_amt(bucket["뇌혈관질환진단비"])
        if v: out["뇌혈관질환진단비"] = f"뇌혈관 {format_amount_short(v)}"

    if ("뇌졸중" in bucket) and ("뇌졸중" not in out):
        v = _max_amt(bucket["뇌졸중"])
        if v: out["뇌졸중"] = f"뇌졸중 {format_amount_short(v)}"

    if ("뇌출혈" in bucket) and ("뇌출혈" not in out):
        v = _max_amt(bucket["뇌출혈"])
        if v: out["뇌출혈"] = f"뇌출혈 {format_amount_short(v)}"

    if ("허혈성심장질환진단비" in bucket) and ("허혈성심장질환진단비" not in out):
        v = _max_amt(bucket["허혈성심장질환진단비"])
        if v: out["허혈성심장질환진단비"] = f"허혈성 {format_amount_short(v)}"

    if ("급성심근경색" in bucket) and ("급성심근경색" not in out):
        v = _max_amt(bucket["급성심근경색"])
        if v: out["급성심근경색"] = f"심근경색 {format_amount_short(v)}"

    # ── 2) 2대주요치료비 (순환계 통합/주요)
    LBL = "2대주요치료비"
    if (LBL in bucket) and (LBL not in out):
        items = list(bucket[LBL] or [])

        # 2-1) 요양병원 vs 요양병원제외: 제외가 있으면 요양병원 항목은 드롭
        has_excl = any("요양병원제외" in _nosp(_name_assoc(c)) for c in items)
        if has_excl:
            items = [c for c in items if "요양병원" not in _nosp(_name_assoc(c)) or "요양병원제외" in _nosp(_name_assoc(c))]

        # 2-2) RT/DRUG 냄새나는 건 제외(해당 항목은 별도 행들에 맡김: 방사선/약물 아님)
        def _looks_main_treat(c: Dict) -> bool:
            s = _name_assoc(c)
            ns = _nosp(s)
            if not any(k in ns for k in ("순환계","특정순환계질환","2대주요","심뇌혈관","순환계질환")):
                return False
            if _has_any(ns, RT_LIKE) or _has_any(ns, DRUG_LIKE):
                return False
            return ("치료" in ns) or ("치료비" in ns) or ("치료지원" in ns)

        items = [c for c in items if _looks_main_treat(c)]

        if not items:
            # 폴백: 원래 로직 유지
            v = _max_amt(bucket[LBL])
            if v:
                out[LBL] = f"2대주요치료 {format_amount_short(v)}"
            return

        # 2-3) 그룹핑: 통합 vs 주요
        def _grp(c: Dict) -> str:
            ns = _nosp(_name_assoc(c))
            if ("통합치료" in ns) or ("통합치료비" in ns) or ("권역심뇌혈관질환센터" in ns) or ("상급종합병원" in ns):
                return "INTEG"  # 순환계통합
            return "MAIN"       # 순환계주요

        groups = {"INTEG": [], "MAIN": []}
        for it in items:
            g = _grp(it)
            groups[g].append(it)

        # 2-4) 보조: (N년) 추출 + 비례 판정
        def _max_with_years(arr: List[Dict]) -> Tuple[int, Optional[int], bool]:
            if not arr:
                return 0, None, False
            mv = _max_amt(arr)

            years: List[int] = []
            proportional = False
            for x in arr:
                s = _nosp(_name_assoc(x))
                # 연수 추출
                m = re.search(r"(진단후)?\s*(\d+)\s*년", s)
                if m:
                    try: years.append(int(m.group(2)))
                    except Exception: pass
                # 비례 힌트: 협회명 비어있거나 NULL, 혹은 '연간/진단후 N년' 기술
                assoc = _nosp(_nz(x.get("association_name","")))
                if (assoc == "" or assoc.lower() == "null") or ("연간" in s) or ("진단후" in s):
                    proportional = True
            return mv, (max(years) if years else None), proportional

        iv, iy, ip = _max_with_years(groups["INTEG"])
        mv, my, mp = _max_with_years(groups["MAIN"])

        parts: List[str] = []
        if iv:
            parts.append(f"순환계통합{f'({iy}년)' if iy else ''} {format_amount_short(iv)}")
        if mv:
            # 주요는 비례 표기
            tail = []
            if my: tail.append(f"{my}년")
            tail.append("비례") if mp else None
            suffix = f"({', '.join(tail)})" if tail else "(비례)" if mp else ""
            parts.append(f"순환계주요{suffix} {format_amount_short(mv)}")

        if parts:
            # 최대 2파트 병기
            out[LBL] = ", ".join(parts[:2])
        else:
            # 최종 폴백
            v = _max_amt(bucket[LBL])
            if v:
                out[LBL] = f"2대주요치료 {format_amount_short(v)}"
