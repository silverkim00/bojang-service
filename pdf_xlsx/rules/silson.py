# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from typing import Dict, List, Optional, Tuple

from ..utils import parse_amount, format_amount_short

# ───────── 내부 유틸 ─────────
def _nz(s: str) -> str: return s if isinstance(s, str) else ""
def _nosp(s: str) -> str: return re.sub(r"\s+", "", _nz(s))

def _name(c: Dict) -> str: return _nz(c.get("name",""))
def _assoc(c: Dict) -> str: return _nz(c.get("association_name",""))
def _na(c: Dict) -> str:    return _nosp(_name(c) + "|" + _assoc(c))

def _amt(val) -> int:
    try:
        return int(parse_amount(val))
    except Exception:
        return 0

def _amt_list(items: List[Dict]) -> List[int]:
    out: List[int] = []
    for i in items or []:
        v = _amt(i.get("amount"))
        if v > 0: out.append(v)
    return out

def _max_amt(items: List[Dict]) -> int:
    vs = _amt_list(items)
    return max(vs) if vs else 0

# ───────── 토큰 정의 ─────────
# 블랙리스트(실손 제외): 일당/상급병실/ICU/암-일당/비의료(운전자류 등)
TOK_DAY = ("일당","입원일당","통원일당")
TOK_ROOM = ("상급병실","상급","특실","1인실","2인실","3인실")
TOK_ICU = ("중환자","ICU","집중치료실")
TOK_NON_MED = ("벌금","배상","변호사선임","방어비용","처리지원","교통사고처리","자동차부상","화재벌금")

# 화이트리스트(실손 의료비 확증)
TOK_MED_INP = ("입원의료비",)
TOK_MED_OUT= ("통원의료비","외래의료비","외래")
TOK_MED_BOTH=("의료비(입원+통원)","입원+통원")
TOK_MED_RX = ("처방조제","처방조제료","조제료","처방")
TOK_MED_DCP= ("비급여도수","도수","체외충격파","증식치료")
TOK_MED_INJ= ("비급여주사제","주사제","비급여주사")
TOK_MED_MRI= ("비급여MRI","비급여MRI검사","MRI검사","비급여 MRI 검사","비급여mri")

# ───────── 분류기 ─────────
def classify(item: Dict) -> Optional[str]:
    """
    실손 분류는 '의료비 화이트리스트'가 있을 때만 True.
    다음은 즉시 제외:
      - 일당/상급병실/ICU/암직접치료 일당/비의료
    반환 라벨:
      - "질병,상해 입원의료비" / "질병,상해 통원의료비" / "도수,체외충격파,증식" / "비급여주사료" / "비급여영상진단MRI"
    """
    s = _na(item)

    # 0) 블랙리스트 컷
    if any(k in s for k in TOK_DAY) or any(k in s for k in TOK_ROOM) or any(k in s for k in TOK_ICU):
        return None
    if ("암" in s) and any(k in s for k in TOK_DAY + ("입원","통원")):
        # 암직접치료 + 일당/입원/통원 냄새는 실손 금지
        return None
    if any(k in s for k in TOK_NON_MED):
        return None

    # 1) 화이트리스트로 의료비 확인
    has_inp   = any(k in s for k in TOK_MED_INP)
    has_out   = any(k in s for k in TOK_MED_OUT)
    has_both  = any(k in s for k in TOK_MED_BOTH)
    has_rx    = any(k in s for k in TOK_MED_RX)
    has_dcp   = any(k in s for k in TOK_MED_DCP)
    has_inj   = any(k in s for k in TOK_MED_INJ)
    has_mri   = any(k in s for k in TOK_MED_MRI)

    # 전문 세부담보
    if has_dcp:
        return "도수,체외충격파,증식"
    if has_inj:
        return "비급여주사료"
    if has_mri:
        return "비급여영상진단MRI"

    # 일반 의료비(입원/통원/입통원)
    if has_both or has_inp or has_out or has_rx:
        # 입통원/입원/통원 어느 쪽이든 의료비 성격이면 허용
        # 라벨은 집계에서 통합 출력 처리하므로, 여기선 대표 버킷 2개 중 하나로 귀속
        if has_inp or has_both:
            return "질병,상해 입원의료비"
        if has_out or has_rx:
            return "질병,상해 통원의료비"

    return None

# ───────── 집계기 ─────────
def aggregate(bucket: Dict[str, List[Dict]], out: Dict[str, str]) -> None:
    """
    - 입원/통원 각각 질/상 금액 수집
    - 입통원(합본)만 있을 경우 "입통원의료비 X만"
    - 질/상 대칭이면 하나로, 비대칭이면 "입원 질X/상Y" 식으로 축약
    - 도수/주사/MRI는 최대값 단일 표기
    """
    # 세부담보: 도수/주사/MRI
    if "도수,체외충격파,증식" in bucket and "도수,체외충격파,증식" not in out:
        v = _max_amt(bucket["도수,체외충격파,증식"])
        if v: out["도수,체외충격파,증식"] = f"도수·체외·증식 {format_amount_short(v)}"

    if "비급여주사료" in bucket and "비급여주사료" not in out:
        v = _max_amt(bucket["비급여주사료"])
        if v: out["비급여주사료"] = f"비급여주사 {format_amount_short(v)}"

    if "비급여영상진단MRI" in bucket and "비급여영상진단MRI" not in out:
        v = _max_amt(bucket["비급여영상진단MRI"])
        if v: out["비급여영상진단MRI"] = f"MRI {format_amount_short(v)}"

    # 일반 의료비
    # 입원 버킷/통원 버킷에서 질병/상해/합본을 구분하여 금액 수집
    def split_domain(items: List[Dict]) -> Tuple[int, int, int]:
        """return (disease_max, injury_max, both_max)"""
        d, i, b = 0, 0, 0
        for x in items or []:
            s = _na(x)
            v = _amt(x.get("amount"))
            if v <= 0: continue
            if ("입원+통원" in s) or ("의료비(입원+통원)" in s):
                b = max(b, v)
                continue
            # 도메인 힌트
            is_dis = ("질병" in s)
            is_inj = ("상해" in s) or ("재해" in s)
            if is_dis and not is_inj:
                d = max(d, v); continue
            if is_inj and not is_dis:
                i = max(i, v); continue
            # 힌트 없으면 보수적으로 both로 올림
            b = max(b, v)
        return d, i, b

    if "질병,상해 입원의료비" in bucket:
        d, i, bmax = split_domain(bucket["질병,상해 입원의료비"])
        txt = None
        if bmax > 0 and (d == 0 and i == 0):
            txt = f"입통원의료비 {format_amount_short(bmax)}"
        else:
            if d and i and d == i:
                txt = f"입원의료비 {format_amount_short(d)}"
            elif d or i:
                parts = []
                if d: parts.append(f"질병{format_amount_short(d)}")
                if i: parts.append(f"상해{format_amount_short(i)}")
                txt = f"입원 {'/'.join(parts)}"
            elif bmax:
                txt = f"입통원의료비 {format_amount_short(bmax)}"
        if txt:
            out["질병,상해 입원의료비"] = txt

    if "질병,상해 통원의료비" in bucket:
        d, i, bmax = split_domain(bucket["질병,상해 통원의료비"])
        txt = None
        if bmax > 0 and (d == 0 and i == 0):
            txt = f"입통원의료비 {format_amount_short(bmax)}"
        else:
            if d and i and d == i:
                txt = f"통원의료비 {format_amount_short(d)}"
            elif d or i:
                parts = []
                if d: parts.append(f"질병{format_amount_short(d)}")
                if i: parts.append(f"상해{format_amount_short(i)}")
                txt = f"통원 {'/'.join(parts)}"
            elif bmax:
                txt = f"입통원의료비 {format_amount_short(bmax)}"
        if txt:
            out["질병,상해 통원의료비"] = txt
